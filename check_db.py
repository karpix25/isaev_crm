import asyncio
from src.database import AsyncSessionLocal
from sqlalchemy import text

async def check_db():
    print("Checking database connection and enabling vector extension...")
    try:
        async with AsyncSessionLocal() as db:
            # Enable pgvector
            await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await db.commit()
            print("Vector extension enabled or already exists.")
            
            result = await db.execute(text("SELECT 1"))
            print(f"Database connection successful: {result.scalar()}")
    except Exception as e:
        print(f"Database operation failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_db())
