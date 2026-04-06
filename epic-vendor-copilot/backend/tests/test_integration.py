import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
class TestIntegration:
    async def test_chat_returns_200_with_answer(self, client):
        response = await client.post("/chat", json={
            "session_id": "test_session_1",
            "message": "What is Vendor Services?"
        })
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert len(data["answer"]) > 0

    async def test_chat_empty_message_returns_422(self, client):
        response = await client.post("/chat", json={
            "session_id": "test_session_1",
            "message": "   "
        })
        assert response.status_code == 422

    async def test_chat_message_over_500_chars_returns_422(self, client):
        response = await client.post("/chat", json={
            "session_id": "test_session_1",
            "message": "a" * 501     # one over the 500-char limit in the validator
        })
        assert response.status_code == 422

    async def test_memory_endpoint_returns_turns(self, client):
        # First send a message
        await client.post("/chat", json={
            "session_id": "test_mem_session",
            "message": "What is Vendor Services?"
        })
        # Then check memory
        response = await client.get("/session/test_mem_session/memory")
        assert response.status_code == 200
        data = response.json()
        assert "turns" in data
        assert len(data["turns"]) == 2  # user turn + assistant turn

    async def test_session_delete_clears_memory(self, client):
        await client.post("/chat", json={
            "session_id": "test_del_session",
            "message": "hello"
        })
        response = await client.delete("/session/test_del_session")
        assert response.status_code == 204
        
        response = await client.get("/session/test_del_session/memory")
        data = response.json()
        assert len(data["turns"]) == 0

    async def test_health_returns_all_fields(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "entries_loaded" in data
        assert "mode" in data
        assert "provider" in data
        assert "model" in data
        assert "retriever" in data
        assert "memory" in data
        assert "uptime_seconds" in data
        assert data["status"] == "ok"

    async def test_memory_used_is_true_on_second_turn(self, client):
        """Turn 2 should detect memory overlap with turn 1's retrieved FAQ IDs."""
        # Turn 1: ask about enrollment
        r1 = await client.post("/chat", json={
            "session_id": "mem-fix-test",
            "message": "What is Vendor Services?"
        })
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["memory_used"] is False  # first turn, no prior context

        # Turn 2: related follow-up in same session
        r2 = await client.post("/chat", json={
            "session_id": "mem-fix-test",
            "message": "Can you explain Vendor Services again?"
        })
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["memory_used"] is True
        assert isinstance(d2["memory_turn_refs"], list)
        assert len(d2["memory_turn_refs"]) > 0
