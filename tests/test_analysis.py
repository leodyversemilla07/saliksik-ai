import pytest
from app.models.user import User
from app.core.security import get_password_hash

@pytest.mark.asyncio
async def test_pre_review_submission(client, db_session):
    # Register and get token
    await client.post("/api/v1/auth/register", json={
        "username": "analysisuser",
        "email": "analysis@example.com",
        "password": "password123"
    })

    login_res = await client.post("/api/v1/auth/login", data={
        "username": "analysisuser",
        "password": "password123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Submit analysis (Form Data)
    response = await client.post(
        "/api/v1/analysis/pre-review",
        data={"manuscript_text": "This is a long enough text to pass validation for the manuscript analysis system test case."},
        headers=headers
    )

    assert response.status_code == 202
    data = response.json()
    # Either a new async task (PENDING) or a cache hit (has 'summary')
    assert "task_id" in data or "summary" in data
    if "status" in data:
        assert data["status"] == "PENDING"
