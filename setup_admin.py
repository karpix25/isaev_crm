import os
import sys
import asyncio

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy import select
from src.database import AsyncSessionLocal
from src.models import User, UserRole, Organization
from src.services.auth import auth_service

async def setup():
    print("🚀 Starting Admin Setup...")
    async with AsyncSessionLocal() as db:
        try:
            # 1. Ensure Organization exists
            res = await db.execute(select(Organization).limit(1))
            org = res.scalar_one_or_none()
            if not org:
                print("⚠️ No organization found. Creating 'Default Organization'...")
                org = Organization(name="Default Organization")
                db.add(org)
                await db.flush()
                print(f"✅ Created organization: {org.name}")
            else:
                print(f"✅ Using organization: {org.name} ({org.id})")

            # 2. Setup admin@test.com
            email = "admin@test.com"
            password = "admin123"
            pwd_hash = auth_service.hash_password(password)
            
            res = await db.execute(select(User).where(User.email == email))
            user = res.scalar_one_or_none()
            
            if user:
                print(f"🔄 Updating existing user: {email}")
                user.password_hash = pwd_hash
                user.role = UserRole.ADMIN
                user.org_id = org.id
            else:
                print(f"✨ Creating new user: {email}")
                user = User(
                    org_id=org.id,
                    email=email,
                    password_hash=pwd_hash,
                    full_name="Administrator",
                    role=UserRole.ADMIN
                )
                db.add(user)
            
            await db.commit()
            print(f"\n✅ SUCCESS!")
            print(f"Login: {email}")
            print(f"Password: {password}")
            
            # Diagnostic
            print("\n--- Current Users in DB ---")
            result = await db.execute(select(User))
            users = result.scalars().all()
            for u in users:
                print(f"Email: {u.email} | Role: {u.role} | Org: {u.org_id}")
            print("---------------------------\n")
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(setup())
