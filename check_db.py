import os
import sys
import asyncio

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy import select
from src.database import AsyncSessionLocal
from src.models import User, Organization

async def check_db():
    print("🔍 Diagnostic Check...")
    async with AsyncSessionLocal() as db:
        try:
            # Check Organizations
            res = await db.execute(select(Organization))
            orgs = res.scalars().all()
            print(f"\n--- Organizations ({len(orgs)}) ---")
            for o in orgs:
                print(f"ID: {o.id} | Name: {o.name}")
            
            # Check Users
            res = await db.execute(select(User))
            users = res.scalars().all()
            print(f"\n--- Users ({len(users)}) ---")
            for u in users:
                # Use sa.func.lower in your head as a reminder that login is case-insensitive now
                # but we show raw DB values here
                print(f"Email: '{u.email}' | Role: {u.role} | Org: {u.org_id} | Has Pwd: {bool(u.password_hash)}")
            
            if not users:
                print("⚠️  No users found in database!")
                
        except Exception as e:
            print(f"❌ Database error: {e}")

if __name__ == "__main__":
    asyncio.run(check_db())
