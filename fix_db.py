import asyncio
from sqlalchemy import text
from src.database import AsyncSessionLocal, init_db

async def fix_db():
    print("Starting database fix...")
    async with AsyncSessionLocal() as db:
        try:
            # 1. Enable pgvector
            print("Enabling vector extension...")
            await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await db.commit()
            
            # 2. Add missing columns to leads
            print("Checking/Adding columns to leads...")
            cols_leads = [
                ("ai_qualification_status", "VARCHAR(50) DEFAULT 'in_progress' NOT NULL"),
                ("extracted_data", "TEXT"),
                ("ai_summary", "TEXT")
            ]
            for col, type_info in cols_leads:
                try:
                    await db.execute(text(f"ALTER TABLE leads ADD COLUMN {col} {type_info}"))
                    await db.commit()
                    print(f"Added {col} to leads")
                except Exception as e:
                    await db.rollback()
                    if "already exists" in str(e):
                        print(f"Column {col} already exists in leads")
                    else:
                        print(f"Error adding {col} to leads: {e}")

            # 3. Add missing columns to chat_messages
            print("Checking/Adding columns to chat_messages...")
            cols_chat = [
                ("ai_metadata", "JSONB"),
                ("sender_name", "VARCHAR(255)")
            ]
            for col, type_info in cols_chat:
                try:
                    await db.execute(text(f"ALTER TABLE chat_messages ADD COLUMN {col} {type_info}"))
                    await db.commit()
                    print(f"Added {col} to chat_messages")
                except Exception as e:
                    await db.rollback()
                    if "already exists" in str(e):
                        print(f"Column {col} already exists in chat_messages")
                    else:
                        print(f"Error adding {col} to chat_messages: {e}")

            print("Database schema updated.")
        except Exception as e:
            print(f"General error during schema update: {e}")

    # 4. Create missing tables (knowledge_base, etc)
    print("Creating missing tables...")
    await init_db()
    print("Database fix completed.")

if __name__ == "__main__":
    asyncio.run(fix_db())
