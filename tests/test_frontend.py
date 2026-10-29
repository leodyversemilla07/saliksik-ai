"""
Tests for the bundled web interface:

- The landing page and the dashboard are served.
- The static assets are reachable.
- The dashboard script is served as JavaScript.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_landing_page_is_served(client: AsyncClient):
    response = await client.get("/")

    assert response.status_code == 200
    assert "Saliksik AI" in response.text


@pytest.mark.asyncio
async def test_dashboard_is_served(client: AsyncClient):
    response = await client.get("/dashboard")

    assert response.status_code == 200
    assert "Dashboard" in response.text
    assert "/static/app.js" in response.text


@pytest.mark.asyncio
async def test_static_assets_are_served(client: AsyncClient):
    css = await client.get("/static/style.css")
    js = await client.get("/static/app.js")

    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]
    assert js.status_code == 200
    assert "javascript" in js.headers["content-type"]


@pytest.mark.asyncio
async def test_dashboard_script_calls_the_documented_endpoints(client: AsyncClient):
    js = await client.get("/static/app.js")

    body = js.text
    assert "/api/v1/auth/login" in body
    assert "/api/v1/auth/register" in body
    assert "/api/v1/auth/logout" in body
    assert "/api/v1/analysis/pre-review" in body
    assert "/api/v1/analysis/status/" in body
    assert "/api/v1/analysis/history" in body
    assert "/api/v1/citations/analyze" in body
    assert "/api/v1/plagiarism/check" in body
    assert "/api/v1/reviewers/me" in body
    assert "/api/v1/admin/stats" in body
    assert "/api/v1/admin/users" in body
