"""
Tests for plagiarism detection endpoints.
"""
import pytest
from app.models.user import User
from app.core.security import get_password_hash


@pytest.mark.asyncio
async def test_plagiarism_check_requires_auth(client):
    """Test that plagiarism check requires authentication."""
    response = await client.post("/api/v1/plagiarism/check", json={
        "manuscript_text": "This is a test manuscript with enough text to pass validation for the plagiarism detection system."
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_plagiarism_check_authenticated(client, db_session):
    """Test plagiarism check with authenticated user."""
    # Register user
    await client.post("/api/v1/auth/register", json={
        "username": "plagiarismuser",
        "email": "plagiarism@example.com",
        "password": "password123"
    })
    
    # Login
    login_res = await client.post("/api/v1/auth/login", data={
        "username": "plagiarismuser",
        "password": "password123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Check plagiarism
    response = await client.post(
        "/api/v1/plagiarism/check",
        json={
            "manuscript_text": "This is a test manuscript with enough text to pass validation for the plagiarism detection system. " * 3
        },
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "is_plagiarized" in data
    assert "overall_similarity" in data
    assert "unique_content_percentage" in data


@pytest.mark.asyncio
async def test_plagiarism_stats(client):
    """Test plagiarism stats endpoint."""
    response = await client.get("/api/v1/plagiarism/stats")
    
    assert response.status_code == 200
    data = response.json()
    assert "documents_indexed" in data
    assert "threshold" in data


@pytest.mark.asyncio
async def test_plagiarism_check_text_too_short(client, db_session):
    """Test plagiarism check with text that is too short."""
    # Register and login
    await client.post("/api/v1/auth/register", json={
        "username": "shorttext",
        "email": "short@example.com",
        "password": "password123"
    })
    
    login_res = await client.post("/api/v1/auth/login", data={
        "username": "shorttext",
        "password": "password123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try with short text
    response = await client.post(
        "/api/v1/plagiarism/check",
        json={"manuscript_text": "Too short"},
        headers=headers
    )
    
    assert response.status_code == 422  # Validation error
