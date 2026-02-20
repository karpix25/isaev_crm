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
        metadata_json: Optional[dict] = None,
        embedding_model: Optional[str] = None
    ) -> KnowledgeItem:
        """Add an item to the knowledge base and generate its embedding"""
        embedding = await openrouter_service.generate_embeddings(content, model=embedding_model)
        
        item = KnowledgeItem(
            org_id=org_id,
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
        
        # Use pgvector's <-> operator (L2 distance) or <=> (cosine distance)
        # Cosine distance (1 - cosine similarity) is usually better for embeddings
        stmt = select(KnowledgeItem).where(KnowledgeItem.org_id == org_id)
        
        if category:
            stmt = stmt.where(KnowledgeItem.category == category)
            
        # Order by distance to query embedding
        stmt = stmt.order_by(KnowledgeItem.embedding.cosine_distance(query_embedding)).limit(limit)
        
        result = await db.execute(stmt)
        docs = list(result.scalars().all())

        if span:
            span.end(output=[{"id": str(d.id), "title": d.title} for d in docs])

        return docs

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
            pdf_doc = fitz.open(stream=file_content, filetype="pdf")
            for page in pdf_doc:
                text += page.get_text()
        else:
            # Assume text/markdown
            text = file_content.decode("utf-8", errors="ignore")

        if not text.strip():
            return 0

        # Robust chunking: fixed size with overlap
        max_chunk_size = 1200  # characters (~300-400 tokens)
        overlap = 200
        
        chunks = []
        if len(text) <= max_chunk_size:
            chunks = [text.strip()]
        else:
            start = 0
            while start < len(text):
                end = start + max_chunk_size
                # Try to find a natural break (newline or space) near the end
                if end < len(text):
                    # Look back up to 200 chars for a newline
                    last_newline = text.rfind('\n', end - 200, end)
                    if last_newline != -1:
                        end = last_newline
                    else:
                        # Look for a space
                        last_space = text.rfind(' ', end - 50, end)
                        if last_space != -1:
                            end = last_space
                
                chunk = text[start:end].strip()
                if len(chunk) > 20: # Skip tiny fragments
                    chunks.append(chunk)
                
                start = end - overlap
                if start >= len(text) - overlap:
                    break

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

knowledge_service = KnowledgeService()
