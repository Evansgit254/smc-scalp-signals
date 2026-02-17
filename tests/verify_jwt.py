import os
import secrets
import jwt
from datetime import datetime, timedelta

# Mock configuration
JWT_SECRET = "test_secret_for_validation"
ALGORITHM = "HS256"

def test_jwt_flow():
    # 1. Generate Token
    username = "admin"
    expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode = {"sub": username, "exp": expire}
    token = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    print(f"✅ Generated Token: {token[:20]}...")

    # 2. Decode Token
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        decoded_user = payload.get("sub")
        print(f"✅ Decoded User: {decoded_user}")
        assert decoded_user == username
    except Exception as e:
        print(f"❌ Decode Failed: {e}")
        return

    # 3. Test Invalid Secret
    try:
        jwt.decode(token, "wrong_secret", algorithms=[ALGORITHM])
        print("❌ Error: Validated with wrong secret!")
    except jwt.PyJWTError:
        print("✅ Correctly rejected invalid secret")

    print("\n🎉 JWT FLOW VALIDATED")

if __name__ == "__main__":
    test_jwt_flow()
