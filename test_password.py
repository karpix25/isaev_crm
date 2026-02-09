"""
Test password hashing and create admin user with working hash
"""
import sys
sys.path.insert(0, '/Users/nadaraya/Desktop/Расул СРМ')

# Test bcrypt directly
try:
    import bcrypt
    password = b"secret123"
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password, salt)
    print(f"✅ bcrypt hash created: {hashed.decode()}")
    
    # Verify
    if bcrypt.checkpw(password, hashed):
        print("✅ bcrypt verification works!")
    else:
        print("❌ bcrypt verification failed!")
        
except Exception as e:
    print(f"❌ bcrypt error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)

# Test passlib
try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    password = "secret123"
    hashed = pwd_context.hash(password)
    print(f"✅ passlib hash created: {hashed}")
    
    # Verify
    if pwd_context.verify(password, hashed):
        print("✅ passlib verification works!")
    else:
        print("❌ passlib verification failed!")
        
except Exception as e:
    print(f"❌ passlib error: {e}")
    import traceback
    traceback.print_exc()
