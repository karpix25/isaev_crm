import asyncio
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.models import Lead

engine = create_async_engine("postgresql+asyncpg://postgres:carlo1822@162.244.24.212:5435/wordpress")
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession)

async def check():
    # 1. Get latest lead from DB
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Lead).order_by(Lead.created_at.desc()).limit(1))
        lead = result.scalar_one_or_none()
        if not lead:
            print("No leads found")
            return
    
    print(f"Testing direct send_message for org: {lead.org_id} to tg: {lead.telegram_id}")
    
    from src.services.user_bot_service import user_bot_service
    
    try:
        await user_bot_service.send_message(db, lead.org_id, lead.telegram_id, "Test message from debug script")
        print("Success!")
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(check())
