"""
Script to verify that SessionLocal is available in app.core.database.
"""
import sys
from pathlib import Path
from sqlalchemy.orm import Session

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_sync_db_availability():
    print("Checking app.core.database exports...")
    try:
        from app.core.database import SessionLocal, sync_engine, engine

        print(f"✅ Found SessionLocal: {SessionLocal}")
        print(f"✅ Found sync_engine: {sync_engine}")
        print(f"✅ Found async engine: {engine}")

        # Verify SessionLocal creates a session
        # We might fail to connect if Postgres is down, but we just want to see if it tries
        # and doesn't crash on instantiation.
        try:
            db = SessionLocal()
            print("✅ Successfully instantiated SessionLocal")
            assert isinstance(db, Session), "db is not a synchronous Session"
            db.close()
        except Exception as e:
            # If it fails due to connection refused, that's expected in this env
            if "connection refused" in str(e).lower() or "could not translate host" in str(e).lower():
                print("⚠️ DB Connection failed (expected), but SessionLocal works.")
            else:
                raise e

        return True
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if test_sync_db_availability():
        sys.exit(0)
    else:
        sys.exit(1)
