import pytest
from app.models.user import User
from app.core.security import get_password_hash

@pytest.mark.asyncio
async def test_register_user(client, db_session):
    response = await client.post("/api/v1/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123"
    })

    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["username"] == "testuser"

@pytest.mark.asyncio
async def test_login_user(client, db_session):
    # Create user first directly in DB
    user = User(
        username="loginuser",
        email="login@example.com",
        hashed_password=get_password_hash("password123")
    )
    db_session.add(user)
    await db_session.commit()

    # Login with Form Data (OAuth2 standard)
    response = await client.post("/api/v1/auth/login", data={
        "username": "loginuser",
        "password": "password123"
    })

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["username"] == "loginuser"
