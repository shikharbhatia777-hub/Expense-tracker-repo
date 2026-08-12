import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to path
sys.path.insert(0, os.getcwd())

# Import the registration function
from main import register_user, init_db, _ensure_db_initialized

async def test_registration():
    try:
        print("Initializing database...")
        await _ensure_db_initialized()
        print("✓ Database initialized successfully")

        print("\nAttempting registration...")
        result = await register_user(
            username="Shikhar",
            password="Shikhar@777",
            email="shikharbhatia@gmail.com"
        )

        print(f"\nRegistration Result:")
        print(f"  Status: {result.get('status')}")
        print(f"  Message: {result.get('message')}")
        if result.get('user_id'):
            print(f"  User ID: {result.get('user_id')}")

        return result

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_registration())
