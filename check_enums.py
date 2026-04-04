import asyncio
from sqlalchemy import text
from src.database import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'message_status';"))
        print("message_status:", [r[0] for r in res.fetchall()])
        res2 = await db.execute(text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'message_direction';"))
        print("message_direction:", [r[0] for r in res2.fetchall()])

asyncio.run(check())
