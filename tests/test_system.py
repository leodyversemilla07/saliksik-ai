"""
Simple test script to verify FastAPI migration.
"""
import asyncio
import sys
from pathlib import Path

# Add app to path
# Add app to path (project root)
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_imports():
    """Test that all modules can be imported."""
    print("🧪 Testing imports...")
    
    try:
        from app.core.config import settings
        print("✅ Config imported successfully")
        
        from app.core.database import Base, engine
        print("✅ Database imported successfully")
        
        from app.core.security import get_password_hash, verify_password
        print("✅ Security imported successfully")
        
        from app.models.user import User
        from app.models.analysis import ManuscriptAnalysis
        print("✅ Models imported successfully")
        
        from app.schemas.user import UserRegister
        from app.schemas.analysis import AnalysisRequest
        print("✅ Schemas imported successfully")
        
        from app.services.ai_processor import ManuscriptPreReviewer
        print("✅ AI Processor imported successfully")
        
        from main import app
        print("✅ Main app imported successfully")
        
        print("\n✨ All imports successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Import failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_password_hashing():
    """Test password hashing."""
    print("\n🧪 Testing password hashing...")
    
    try:
        from app.core.security import get_password_hash, verify_password
        
        password = "test123456"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed), "Password verification failed"
        assert not verify_password("wrong", hashed), "Wrong password accepted"
        
        print("✅ Password hashing works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Password hashing failed: {str(e)}")
        return False


async def test_jwt():
    """Test JWT token creation and decoding."""
    print("\n🧪 Testing JWT...")
    
    try:
        from app.core.security import create_access_token, decode_access_token
        
        token = create_access_token({"sub": "123"})
        payload = decode_access_token(token)
        
        assert payload is not None, "Token decoding failed"
        assert payload.get("sub") == "123", "Token payload incorrect"
        
        # Test invalid token
        invalid_payload = decode_access_token("invalid_token")
        assert invalid_payload is None, "Invalid token accepted"
        
        print("✅ JWT works correctly")
        return True
        
    except Exception as e:
        print(f"❌ JWT failed: {str(e)}")
        return False


async def test_ai_processor():
    """Test AI processor basic functionality."""
    print("\n🧪 Testing AI Processor...")
    
    try:
        from app.services.ai_processor import ManuscriptPreReviewer
        import os
        
        # Use light mode for testing
        os.environ["AI_LIGHT_MODE"] = "1"
        
        processor = ManuscriptPreReviewer()
        
        test_text = """
        This is a test manuscript for the AI processing system. 
        It contains multiple sentences to test the analysis capabilities.
        The system should be able to extract keywords and generate summaries.
        This text is long enough to pass the minimum length requirements.
        """
        
        # Test preprocessing
        cleaned = processor.preprocess_text(test_text)
        assert len(cleaned) > 0, "Preprocessing failed"
        
        # Test keyword extraction
        keywords = processor.extract_keywords(test_text, top_n=5)
        assert len(keywords) > 0, "Keyword extraction failed"
        
        # Test language quality
        quality = processor.assess_language_quality(test_text)
        assert 'word_count' in quality, "Language quality assessment failed"
        assert quality['word_count'] > 0, "Word count is zero"
        
        print("✅ AI Processor works correctly")
        return True
        
    except Exception as e:
        print(f"❌ AI Processor failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_cache():
    """Test cache functionality."""
    print("\n🧪 Testing Cache...")
    
    try:
        from app.core.cache import AIResultCache
        
        test_text = "This is a test text for caching"
        test_result = {"summary": "Test summary", "keywords": ["test"]}
        
        # Cache result
        success = AIResultCache.cache_result(test_text, test_result)
        assert success, "Cache storage failed"
        
        # Retrieve cached result
        cached = AIResultCache.get_cached_result(test_text)
        assert cached is not None, "Cache retrieval failed"
        assert cached["summary"] == test_result["summary"], "Cached data incorrect"
        
        # Get stats
        stats = AIResultCache.get_cache_stats()
        assert "backend" in stats, "Cache stats failed"
        
        print("✅ Cache works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Cache failed: {str(e)}")
        return False


async def test_database_connection():
    """Test database connection."""
    print("\n🧪 Testing Database Connection...")
    
    try:
        from app.core.database import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1, "Database query failed"
        
        print("✅ Database connection works")
        return True
        
    except Exception as e:
        print(f"⚠️ Database connection failed: {str(e)}")
        print("   (This is expected if PostgreSQL is not running)")
        return None  # Not a critical failure


async def main():
    """Run all tests."""
    print("=" * 60)
    print("FastAPI Migration Verification")
    print("=" * 60)
    
    results = []
    
    results.append(await test_imports())
    results.append(await test_password_hashing())
    results.append(await test_jwt())
    results.append(await test_ai_processor())
    results.append(await test_cache())
    db_result = await test_database_connection()
    
    # Don't count DB test in critical results
    critical_passed = sum(1 for r in results if r is True)
    critical_failed = sum(1 for r in results if r is False)
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"✅ Critical tests passed: {critical_passed}/{len(results)}")
    if critical_failed > 0:
        print(f"❌ Critical tests failed: {critical_failed}/{len(results)}")
    if db_result is None:
        print("⚠️ Database test skipped (optional)")
    
    if critical_failed == 0:
        print("\n🎉 FastAPI migration is ready to use!")
        print("\nNext steps:")
        print("1. Start PostgreSQL database")
        print("2. Run: uvicorn main:app --reload")
        print("3. Visit: http://localhost:8000/docs")
        return 0
    else:
        print("\n❌ Please fix the failing tests before using the application")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
