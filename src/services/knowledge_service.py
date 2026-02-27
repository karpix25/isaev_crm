import uuid
import fitz
import io
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from src.models.knowledge import KnowledgeItem
from src.services.openrouter_service import openrouter_service

class KnowledgeService:
    """Service for managing the Knowledge Base and performing RAG"""
    
    @staticmethod
    async def add_knowledge_item(
        db: AsyncSession,
        org_id: uuid.UUID,
        content: str,
        category: Optional[str] = None,
        title: Optional[str] = None,
        lead_id: Optional[uuid.UUID] = None,
        metadata_json: Optional[dict] = None,
        embedding_model: Optional[str] = None
    ) -> KnowledgeItem:
        """Add an item to the knowledge base and generate its embedding"""
        embedding = await openrouter_service.generate_embeddings(content, model=embedding_model)
        
        item = KnowledgeItem(
            org_id=org_id,
            lead_id=lead_id,
            content=content,
            category=category,
            title=title,
            embedding=embedding,
            metadata_json=metadata_json
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item

    @staticmethod
    async def search_knowledge(
        db: AsyncSession,
        org_id: uuid.UUID,
        query: str,
        limit: int = 5,
        category: Optional[str] = None,
        lead_id: Optional[uuid.UUID] = None,
        embedding_model: Optional[str] = None,
        trace_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> List[KnowledgeItem]:
        """Perform semantic search in the knowledge base"""
        # Langfuse Tracing
        span = None
        if openrouter_service.langfuse and trace_id:
            trace = openrouter_service.langfuse.trace(id=trace_id, user_id=user_id)
            span = trace.span(name="knowledge-base-search", input=query)

        query_embedding = await openrouter_service.generate_embeddings(query, model=embedding_model)
        
        # 1. Vector Search
        # We search for items that:
        # a) Belong to the organization AND have NO lead_id (general knowledge)
        # b) OR belong to the organization AND match the specific lead_id (this lead's history)
        from sqlalchemy import or_
        vec_stmt = select(KnowledgeItem).where(
            KnowledgeItem.org_id == org_id
        )
        
        if lead_id:
            vec_stmt = vec_stmt.where(
                or_(
                    KnowledgeItem.lead_id == None,
                    KnowledgeItem.lead_id == lead_id
                )
            )
        else:
            vec_stmt = vec_stmt.where(KnowledgeItem.lead_id == None)

        if category:
            vec_stmt = vec_stmt.where(KnowledgeItem.category == category)
            
        vec_stmt = vec_stmt.order_by(KnowledgeItem.embedding.cosine_distance(query_embedding)).limit(limit * 2)
        vec_result = await db.execute(vec_stmt)
        vec_docs = list(vec_result.scalars().all())

        # 2. Full Text Search (FTS)
        from sqlalchemy import func
        ts_query = func.websearch_to_tsquery('russian', query)
        ts_vector = func.to_tsvector('russian', KnowledgeItem.content)
        
        fts_stmt = select(KnowledgeItem).where(
            KnowledgeItem.org_id == org_id,
            ts_vector.op('@@')(ts_query)
        )
        
        if lead_id:
            fts_stmt = fts_stmt.where(
                or_(
                    KnowledgeItem.lead_id == None,
                    KnowledgeItem.lead_id == lead_id
                )
            )
        else:
            fts_stmt = fts_stmt.where(KnowledgeItem.lead_id == None)

        if category:
            fts_stmt = fts_stmt.where(KnowledgeItem.category == category)
            
        fts_stmt = fts_stmt.order_by(func.ts_rank(ts_vector, ts_query).desc()).limit(limit * 2)
        
        try:
            fts_result = await db.execute(fts_stmt)
            fts_docs = list(fts_result.scalars().all())
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"FTS search failed (fallback to vector only): {e}")
            fts_docs = []
            
        # 3. Reciprocal Rank Fusion (RRF)
        k = 60
        scores = {}
        for rank, doc in enumerate(vec_docs):
            if doc.id not in scores:
                scores[doc.id] = {"doc": doc, "score": 0.0}
            scores[doc.id]["score"] += 1.0 / (k + rank + 1)
            
        for rank, doc in enumerate(fts_docs):
            if doc.id not in scores:
                scores[doc.id] = {"doc": doc, "score": 0.0}
            scores[doc.id]["score"] += 1.0 / (k + rank + 1)
            
        sorted_docs = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
        docs = [item["doc"] for item in sorted_docs[:limit]]

        if span:
            span.end(output=[{"id": str(d.id), "title": d.title} for d in docs])

        return docs

    @staticmethod
    def _recursive_text_split(text: str, max_chunk_size: int = 1200, overlap: int = 200) -> List[str]:
        separators = ["\n\n", "\n", ". ", " "]
        
        def get_splits(text, separators):
            if not text: return []
            if not separators: return [text]
            sep = separators[0]
            if sep not in text:
                return get_splits(text, separators[1:])
                
            parts = text.split(sep)
            res = []
            for i, p in enumerate(parts):
                sub_p = p + (sep if i < len(parts) - 1 else "")
                if len(sub_p) > max_chunk_size:
                    res.extend(get_splits(sub_p, separators[1:]))
                else:
                    res.append(sub_p)
            return res

        parts = get_splits(text, separators)
        
        chunks = []
        current_chunk = ""
        
        for part in parts:
            if len(current_chunk) + len(part) <= max_chunk_size:
                current_chunk += part
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                if current_chunk and overlap > 0:
                    overlap_start = max(0, len(current_chunk) - overlap)
                    overlap_text = current_chunk[overlap_start:]
                    safe_idx = overlap_text.find(" ")
                    if safe_idx != -1:
                        overlap_text = overlap_text[safe_idx:]
                    current_chunk = overlap_text + part
                else:
                    current_chunk = part
                    
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return [c for c in chunks if len(c) > 20]

    @staticmethod
    async def process_knowledge_file(
        db: AsyncSession,
        org_id: uuid.UUID,
        file_content: bytes,
        filename: str,
        category: str = "general",
        embedding_model: Optional[str] = None
    ) -> int:
        """Process an uploaded file, extract text, and add to knowledge base"""
        text = ""
        if filename.endswith(".pdf"):
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Processing PDF: {filename} ({len(file_content)} bytes)")
            try:
                pdf_doc = fitz.open(stream=file_content, filetype="pdf")
                text_blocks = []
                for page in pdf_doc:
                    # 'blocks' extraction preserves structural reading order
                    blocks = page.get_text("blocks")
                    # b[6] == 0 means it's a text block
                    page_text = "\n\n".join([b[4].strip() for b in blocks if b[6] == 0])
                    if page_text:
                        text_blocks.append(page_text)
                text = "\n\n".join(text_blocks)
                logger.info(f"Extracted {len(text)} characters from PDF")
            except Exception as e:
                logger.error(f"Failed to extract text from PDF: {e}")
                raise ValueError(f"Ошибка чтения PDF: {str(e)}")
        else:
            # Assume text/markdown
            text = file_content.decode("utf-8", errors="ignore")

        if not text.strip():
            import logging
            logging.getLogger(__name__).warning(f"Extracted text is empty for file {filename}")
            return 0

        # Smart Recursive Chunking
        chunks = KnowledgeService._recursive_text_split(text, max_chunk_size=1200, overlap=200)

        count = 0
        for i, chunk in enumerate(chunks):
            await KnowledgeService.add_knowledge_item(
                db=db,
                org_id=org_id,
                title=f"{filename} (Часть {i+1})",
                content=chunk,
                category=category,
                embedding_model=embedding_model
            )
            count += 1
        
        return count

    @staticmethod
    async def clear_knowledge(db: AsyncSession, org_id: uuid.UUID) -> int:
        """Delete all knowledge items for an organization"""
        from sqlalchemy import delete
        stmt = delete(KnowledgeItem).where(KnowledgeItem.org_id == org_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount

knowledge_service = KnowledgeService()
