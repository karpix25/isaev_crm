import os
import sys

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy import select
from src.database import AsyncSessionLocal
from src.models import User, UserRole, Organization
from src.services.auth import auth_service

async def fix_admin():
    async with AsyncSessionLocal() as db:
        # Get first org
        res = await db.execute(select(Organization).limit(1))
        org = res.scalar_one_or_none()
        if not org:
            print("No org")
            return
            
        # Check admin@test.com
        res = await db.execute(select(User).where(User.email == "admin@test.com"))
        user = res.scalar_one_or_none()
        
        pwd_hash = auth_service.hash_password("admin123")
        
        if user:
            print(f"Updating existing user admin@test.com")
            user.password_hash = pwd_hash
            user.role = UserRole.ADMIN
        else:
            print(f"Creating new user admin@test.com")
            user = User(
                org_id=org.id,
                email="admin@test.com",
                password_hash=pwd_hash,
                full_name="Admin",
                role=UserRole.ADMIN
            )
            db.add(user)
            
        # Diagnostic: list all users
        print("\n--- Diagnostic: All Users ---")
        result = await db.execute(select(User))
        users = result.scalars().all()
        for u in users:
            print(f"User: {u.email}, Role: {u.role}, Has Password: {bool(u.password_hash)}")
        print("-----------------------------\n")
        
        await db.commit()
        print("✅ Done! Login: admin@test.com / admin123")

if __name__ == "__main__":
    asyncio.run(fix_admin())
