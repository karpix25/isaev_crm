import os
import sys

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy import select
from src.database import AsyncSessionLocal
from src.models import User, UserRole, Organization
from src.services.auth import auth_service


async def create_admin_user():
    """Create a test admin user"""
    
    async with AsyncSessionLocal() as db:
        # Get the first organization
        result = await db.execute(select(Organization).limit(1))
        org = result.scalar_one_or_none()
        
        if not org:
            print("❌ No organization found! Please create an organization first.")
            return
        
        print(f"✅ Found organization: {org.name} ({org.id})")
        
        # Check if admin already exists
        result = await db.execute(
            select(User).where(User.email == "admin@example.com")
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print(f"✅ Admin user already exists: {existing_user.email}")
            print(f"   ID: {existing_user.id}")
            print(f"   Role: {existing_user.role}")
            return
        
        # Create admin user
        auth_service = AuthService()
        hashed_password = auth_service.hash_password("admin123")
        
        user = User(
            org_id=org.id,
            email="admin@example.com",
            password_hash=hashed_password,
            full_name="Admin User",
            role=UserRole.ADMIN
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        print("\n" + "=" * 60)
        print("✅ Admin user created successfully!")
        print("=" * 60)
        print(f"\n📧 Email: admin@example.com")
        print(f"🔑 Password: admin123")
        print(f"👤 Name: Admin User")
        print(f"🏢 Organization: {org.name}")
        print(f"🎭 Role: ADMIN")
        print(f"\n🌐 Login at: http://localhost:5173/login")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(create_admin_user())
