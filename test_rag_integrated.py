import asyncio
import uuid
import logging

from src.database import AsyncSessionLocal
from src.services.knowledge_service import knowledge_service

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_rag():
    org_id = uuid.uuid4() # fake org
    
    # 1. Test Chunking
    test_text = """Заголовок документа

Это первый абзац с общим описанием нашей компании. Мы занимаемся ремонтом.

Тариф "Эконом": 1000 руб. Включает базовые услуги.
Тариф "Премиум": 5000 руб. Уникальный артикул для этого тарифа XQW-12345.
"""
    
    chunks = knowledge_service._recursive_text_split(test_text, max_chunk_size=100, overlap=10)
    print("CHUNKS:")
    for i, c in enumerate(chunks):
        print(f"[{i}]: {c}")
        
    async with AsyncSessionLocal() as db:
        try:
            from sqlalchemy import text
            res = await db.execute(text("SELECT id FROM organizations LIMIT 1"))
            real_org_raw = res.scalar()
            if not real_org_raw:
                print("No organization found in DB. Test query skipped.")
                return
                
            real_org_id = real_org_raw
            print(f"Using org_id: {real_org_id}")
            
            # Let's assume we search for the specific keyword
            print("Testing search_knowledge syntax...")
            
            # For testing without real API call, let's mock openrouter_service.generate_embeddings temporarily
            from src.services.openrouter_service import openrouter_service
            import uuid
            
            # Create a mock embedding vector (1536 dim)
            mock_emb = [0.1] * 1536
            
            async def mock_generate_embeddings(text, model=None):
                return mock_emb
                
            openrouter_service.generate_embeddings = mock_generate_embeddings
            
            docs = await knowledge_service.search_knowledge(
                db=db,
                org_id=real_org_id,
                query="уникальный артикул XQW-12345",
                limit=3
            )
            print(f"Tested query cleanly. Returned {len(docs)} docs.")
            for doc in docs:
                print(f" - Doc ID: {doc.id}, Title: {doc.title}")
                
        except Exception as e:
            print(f"Test query failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_rag())
