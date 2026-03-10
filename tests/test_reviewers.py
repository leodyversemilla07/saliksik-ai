"""
Tests for reviewer management and matching endpoints.
"""
import pytest
from app.models.user import User
from app.core.security import get_password_hash


async def get_auth_headers(client, username: str, email: str):
    """Helper to register, login, and get auth headers."""
    await client.post("/api/v1/auth/register", json={
        "username": username,
        "email": email,
        "password": "password123"
    })
    
    login_res = await client.post("/api/v1/auth/login", data={
        "username": username,
        "password": "password123"
    })
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_reviewer_profile(client, db_session):
    """Test creating a reviewer profile."""
    headers = await get_auth_headers(client, "reviewer1", "reviewer1@example.com")
    
    response = await client.post(
        "/api/v1/reviewers/",
        json={
            "expertise_keywords": ["machine learning", "natural language processing"],
            "expertise_description": "Expert in ML and NLP",
            "institution": "Test University",
            "department": "Computer Science",
            "max_assignments": 5
        },
        headers=headers
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["expertise_keywords"] == ["machine learning", "natural language processing"]
    assert data["institution"] == "Test University"


@pytest.mark.asyncio
async def test_create_duplicate_reviewer_profile(client, db_session):
    """Test that a user cannot create multiple reviewer profiles."""
    headers = await get_auth_headers(client, "reviewer2", "reviewer2@example.com")
    
    # Create first profile
    await client.post(
        "/api/v1/reviewers/",
        json={
            "expertise_keywords": ["data science"],
            "max_assignments": 3
        },
        headers=headers
    )
    
    # Try to create second profile
    response = await client.post(
        "/api/v1/reviewers/",
        json={
            "expertise_keywords": ["statistics"],
            "max_assignments": 2
        },
        headers=headers
    )
    
    assert response.status_code == 400
    # Check response - may be in "detail" (HTTPException) or "error.message" (custom handler)
    data = response.json()
    error_msg = data.get("detail") or data.get("error", {}).get("message", "")
    assert "already has a reviewer profile" in error_msg


@pytest.mark.asyncio
async def test_get_my_reviewer_profile(client, db_session):
    """Test getting current user's reviewer profile."""
    headers = await get_auth_headers(client, "reviewer3", "reviewer3@example.com")
    
    # Create profile
    await client.post(
        "/api/v1/reviewers/",
        json={
            "expertise_keywords": ["bioinformatics"],
            "institution": "Research Institute"
        },
        headers=headers
    )
    
    # Get profile
    response = await client.get("/api/v1/reviewers/me", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["expertise_keywords"] == ["bioinformatics"]


@pytest.mark.asyncio
async def test_get_profile_not_found(client, db_session):
    """Test getting profile when none exists."""
    headers = await get_auth_headers(client, "noprofile", "noprofile@example.com")
    
    response = await client.get("/api/v1/reviewers/me", headers=headers)
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_reviewer_profile(client, db_session):
    """Test updating reviewer profile."""
    headers = await get_auth_headers(client, "reviewer4", "reviewer4@example.com")
    
    # Create profile
    await client.post(
        "/api/v1/reviewers/",
        json={
            "expertise_keywords": ["chemistry"],
            "is_available": True
        },
        headers=headers
    )
    
    # Update profile
    response = await client.put(
        "/api/v1/reviewers/me",
        json={
            "expertise_keywords": ["chemistry", "biochemistry"],
            "is_available": False,
            "institution": "Updated Institution"
        },
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "biochemistry" in data["expertise_keywords"]
    assert data["is_available"] == False
    assert data["institution"] == "Updated Institution"


@pytest.mark.asyncio
async def test_list_reviewers(client, db_session):
    """Test listing reviewers."""
    headers = await get_auth_headers(client, "lister", "lister@example.com")
    
    # Create a reviewer profile first
    await client.post(
        "/api/v1/reviewers/",
        json={"expertise_keywords": ["physics"]},
        headers=headers
    )
    
    response = await client.get("/api/v1/reviewers/", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total_count" in data


@pytest.mark.asyncio
async def test_reviewers_requires_auth(client):
    """Test that reviewer endpoints require authentication."""
    response = await client.get("/api/v1/reviewers/me")
    assert response.status_code == 401
    
    response = await client.post("/api/v1/reviewers/", json={
        "expertise_keywords": ["test"]
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_does_not_expose_email(client, db_session):
    """Reviewer list must NOT expose email or user_id (IDOR prevention)."""
    # Create a reviewer (user A)
    headers_a = await get_auth_headers(client, "idor_reviewer", "idor_reviewer@secret.com")
    await client.post(
        "/api/v1/reviewers/",
        json={"expertise_keywords": ["security", "privacy"]},
        headers=headers_a,
    )

    # User B lists reviewers
    headers_b = await get_auth_headers(client, "idor_viewer", "idor_viewer@example.com")
    response = await client.get("/api/v1/reviewers/", headers=headers_b)

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) >= 1

    for reviewer in results:
        assert "email" not in reviewer, "email must not be in public reviewer list"
        assert "user_id" not in reviewer, "user_id must not be in public reviewer list"


@pytest.mark.asyncio
async def test_own_profile_exposes_full_details(client, db_session):
    """Owner's /me endpoint should still expose email and user_id."""
    headers = await get_auth_headers(client, "idor_owner", "idor_owner@example.com")
    await client.post(
        "/api/v1/reviewers/",
        json={"expertise_keywords": ["mathematics"]},
        headers=headers,
    )

    response = await client.get("/api/v1/reviewers/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "email" in data
    assert "user_id" in data
