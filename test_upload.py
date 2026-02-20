import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.config import settings
from src.services.knowledge_service import knowledge_service
from src.services.openrouter_service import openrouter_service

async def test():
    try:
        print("Processing fake content...")
        file_content = b"This is a test document to index into the RAG database."
        res = await openrouter_service.generate_embeddings("test text", model=None)
        print(f"Success! Generated embedding of length {len(res)}.")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
