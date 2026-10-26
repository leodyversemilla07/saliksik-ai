#!/usr/bin/env python3
"""End-to-end smoke test for a running Saliksik AI stack.

The API, Celery worker, PostgreSQL, and Redis must already be running. The
script exercises the public demo, registration, authenticated submission,
status polling, history, and cache namespace isolation.

Usage:
    uv run python scripts/smoke_test.py
    uv run python scripts/smoke_test.py --base-url http://127.0.0.1:8000

The base URL can also be set with SALIKSIK_BASE_URL.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"

SAMPLE_TEXT = (
    "Machine learning has transformed the way researchers analyze large collections of academic manuscripts. "
    "This study evaluates a lightweight pre-review system that combines summarization, keyword extraction, "
    "and readability scoring. The results indicate that automated triage can reduce editorial workload while "
    "preserving transparency and reviewer oversight. Future work will evaluate the system on a larger corpus "
    "and compare its recommendations with decisions made by human editors. "
    f"Local verification run {uuid.uuid4().hex}."
)


class SmokeTestError(RuntimeError):
    """Raised when an end-to-end expectation is not met."""


def check(condition: bool, message: str) -> None:
    """Fail the smoke test with a readable message."""
    if not condition:
        raise SmokeTestError(message)


def check_health(client: httpx.Client) -> None:
    payload = client.get("/health").json()
    print(
        "health:",
        payload.get("status"),
        "database:",
        payload.get("services", {}).get("database", {}).get("status"),
        "redis:",
        payload.get("services", {}).get("redis", {}).get("status"),
    )
    check(payload.get("status") == "healthy", f"API health is {payload.get('status')!r}")
    check(
        payload.get("services", {}).get("database", {}).get("status") == "healthy",
        "database is not healthy",
    )
    check(
        payload.get("services", {}).get("redis", {}).get("status") == "healthy",
        "Redis is not healthy",
    )


def register_user(client: httpx.Client) -> tuple[str, int, dict[str, str]]:
    username = f"smoke_{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "Password123!",
        },
    )
    response.raise_for_status()
    payload = response.json()
    print(f"registered {username} (id={payload['user']['id']})")
    return username, payload["user"]["id"], {"Authorization": f"Bearer {payload['access_token']}"}


def demo_analysis(client: httpx.Client, manuscript_text: str, label: str) -> dict[str, Any]:
    response = client.post("/api/v1/analysis/demo", json={"manuscript_text": manuscript_text})
    response.raise_for_status()
    payload = response.json()

    check(bool(payload.get("summary")), f"{label}: demo response is missing a summary")
    check(bool(payload.get("keywords")), f"{label}: demo response is missing keywords")
    check(payload.get("metadata", {}).get("demo") is True, f"{label}: demo metadata flag is not set")
    print(
        f"{label}: summary={payload['summary'][:80]!r} "
        f"keywords={len(payload['keywords'])} words={payload['language_quality']['word_count']}"
    )
    return payload


def submit_analysis(client: httpx.Client, manuscript_text: str, headers: dict[str, str]) -> dict[str, Any]:
    response = client.post(
        "/api/v1/analysis/pre-review",
        data={"manuscript_text": manuscript_text},
        headers=headers,
    )
    response.raise_for_status()
    payload = response.json()

    check(response.status_code == 202, f"submission returned HTTP {response.status_code}, expected 202")
    check(payload.get("status") == "PENDING", f"submission status is {payload.get('status')!r}, expected PENDING")
    check(bool(payload.get("task_id")), "submission did not return a task_id")
    print(f"submitted analysis_id={payload.get('analysis_id')} task_id={payload['task_id']}")
    return payload


def poll_until_complete(
    client: httpx.Client,
    task_id: str,
    headers: dict[str, str],
    *,
    max_polls: int,
    poll_interval: float,
) -> dict[str, Any]:
    last_status = "UNKNOWN"
    for attempt in range(1, max_polls + 1):
        response = client.get(f"/api/v1/analysis/status/{task_id}", headers=headers)
        response.raise_for_status()
        payload = response.json()

        if "summary" in payload:
            check(bool(payload.get("summary")), "completed response is missing a summary")
            check("language_quality" in payload, "completed response is missing language_quality")
            print(f"poll {attempt}: COMPLETED")
            return payload

        last_status = payload.get("status", "UNKNOWN")
        print(f"poll {attempt}: {last_status}")
        check(
            last_status in {"PENDING", "PROCESSING"},
            f"unexpected status {last_status!r} for task {task_id}: {payload}",
        )
        if attempt < max_polls:
            time.sleep(poll_interval)

    raise SmokeTestError(f"task {task_id} did not complete after {max_polls} polls (last status: {last_status})")


def check_history(client: httpx.Client, analysis_id: int, headers: dict[str, str]) -> None:
    response = client.get("/api/v1/analysis/history", headers=headers)
    response.raise_for_status()
    payload = response.json()

    check(payload.get("pagination", {}).get("total_count", 0) >= 1, "history is empty")
    results = payload.get("results", [])
    check(bool(results), "history returned no results")
    visible_ids = {item["id"] for item in results}
    check(analysis_id in visible_ids, f"analysis {analysis_id} is missing from history")
    print(f"history: total_count={payload['pagination']['total_count']} latest_id={payload['results'][0]['id']}")


def check_cache_isolation(
    client: httpx.Client,
    headers: dict[str, str],
    username: str,
    *,
    demo_text: str,
    max_polls: int,
    poll_interval: float,
) -> None:
    # Demo first, then authenticated with identical text. The authenticated
    # submission must still start a real task instead of returning the demo
    # result.
    demo_analysis(client, demo_text, "isolation/demo-first")
    submission = submit_analysis(client, demo_text, headers)
    result = poll_until_complete(
        client,
        submission["task_id"],
        headers,
        max_polls=max_polls,
        poll_interval=poll_interval,
    )
    check(bool(result.get("summary")), "authenticated analysis after a demo cache entry is incomplete")
    print("isolation/demo-first: authenticated analysis completed")

    # Authenticated first, then demo with identical text. The demo response
    # must be generated in the demo namespace and must not expose the
    # authenticated user's metadata.
    private_text = f"{SAMPLE_TEXT}\n\nPrivacy probe {uuid.uuid4().hex}."
    submission = submit_analysis(client, private_text, headers)
    authenticated_result = poll_until_complete(
        client,
        submission["task_id"],
        headers,
        max_polls=max_polls,
        poll_interval=poll_interval,
    )
    check(
        authenticated_result.get("metadata", {}).get("user") == username,
        "authenticated result does not belong to the submitting user",
    )

    demo_result = demo_analysis(client, private_text, "isolation/authenticated-first")
    demo_user = demo_result.get("metadata", {}).get("user")
    check(demo_user in (None, ""), f"demo response leaked authenticated user metadata: {demo_user!r}")
    check(demo_result.get("metadata", {}).get("demo") is True, "demo response is not marked as demo data")
    print("isolation/authenticated-first: demo response does not expose authenticated metadata")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SALIKSIK_BASE_URL", DEFAULT_BASE_URL),
        help=f"API base URL (default: {DEFAULT_BASE_URL} or SALIKSIK_BASE_URL)",
    )
    parser.add_argument("--timeout", type=float, default=120.0, help="HTTP timeout in seconds (default: 120)")
    parser.add_argument("--max-polls", type=int, default=60, help="maximum status polls per analysis (default: 60)")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="seconds between status polls (default: 1.0)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(f"smoke test against {args.base_url}")

    try:
        with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
            check_health(client)

            print("\n== public demo ==")
            demo_analysis(client, SAMPLE_TEXT, "demo")

            print("\n== authenticated workflow ==")
            username, _, headers = register_user(client)
            submission = submit_analysis(client, f"{SAMPLE_TEXT}\n\nAnalysis-only note {uuid.uuid4().hex}.", headers)
            result = poll_until_complete(
                client,
                submission["task_id"],
                headers,
                max_polls=args.max_polls,
                poll_interval=args.poll_interval,
            )
            print(
                f"completed: summary={result['summary'][:80]!r} "
                f"processing_time={result['metadata']['processing_time']}s"
            )
            check_history(client, submission["analysis_id"], headers)

            print("\n== cache namespace isolation ==")
            check_cache_isolation(
                client,
                headers,
                username,
                demo_text=f"{SAMPLE_TEXT}\n\nCache isolation probe {uuid.uuid4().hex}.",
                max_polls=args.max_polls,
                poll_interval=args.poll_interval,
            )
    except httpx.HTTPStatusError as exc:
        body = exc.response.text
        print(
            f"\nFAILED: {exc.request.method} {exc.request.url} returned HTTP {exc.response.status_code}\n{body}",
            file=sys.stderr,
        )
        return 1
    except (httpx.HTTPError, SmokeTestError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1

    print("\nSMOKE_TEST_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
