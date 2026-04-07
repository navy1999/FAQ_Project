"""
test_chat.py
------------
Integration tests for the /chat and /chat/stream endpoints.
Verifies that the new semantic thresholding logic in main.py correctly 
routes queries and bypasses synthesis for off-topic/vague queries.
"""

import pytest
from httpx import AsyncClient
from backend.main import app, DOMAIN_MISS_RESPONSE, CLARIFICATION_RESPONSE

@pytest.mark.asyncio
async def test_chat_high_score_calls_synthesize():
    """A clear FAQ query should return an 'answer' response_type."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/chat", json={
            "session_id": "test-session",
            "message": "how do I enroll in vendor services"
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["response_type"] == "answer"
    assert "Enrolling in Vendor Services" in data["answer"] or len(data["answer"]) > 20
    assert data["source"]["id"] is not None

@pytest.mark.asyncio
async def test_chat_low_score_returns_domain_miss():
    """An off-topic query should return 'domain_miss' without calling synthesize."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/chat", json={
            "session_id": "test-session",
            "message": "what is the capital of France"
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["response_type"] == "domain_miss"
    assert data["answer"] == DOMAIN_MISS_RESPONSE
    assert data["source"]["id"] is None

@pytest.mark.asyncio
async def test_chat_mid_score_returns_clarification():
    """A vague query should return 'clarification' without calling synthesize."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/chat", json={
            "session_id": "test-session",
            "message": "technical issues"
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["response_type"] == "clarification"
    assert data["answer"] == CLARIFICATION_RESPONSE
    assert data["source"]["id"] is None

@pytest.mark.asyncio
async def test_chat_invalid_query():
    """Extremely short queries should be rejected with clarification."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/chat", json={
            "session_id": "test-session",
            "message": "hi"
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["response_type"] == "clarification"
    assert "enter a valid question" in data["answer"]

@pytest.mark.asyncio
async def test_chat_stream_off_topic_bypasses_synthesize():
    """Streaming off-topic queries should return domain_miss immediately."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        async with ac.stream("POST", "/chat/stream", json={
            "session_id": "test-session-stream",
            "message": "tell me about pizza"
        }) as resp:
            lines = [line async for line in resp.aiter_lines()]
    
    # Check that we got the domain_miss response
    found_done = False
    for line in lines:
        if line.startswith("data: "):
            import json
            payload = json.loads(line[6:])
            if payload.get("done"):
                assert payload["response_type"] == "domain_miss"
                found_done = True
    assert found_done
