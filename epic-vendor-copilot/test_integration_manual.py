import asyncio
from httpx import AsyncClient, ASGITransport
from backend.main import app

async def run():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.post("/chat", json={
            "session_id": "mem-fix-test",
            "message": "What is Vendor Services?"
        })
        d1 = r1.json()
        print("T1 results:", d1.get("source", {}).get("id"))
        
        r2 = await client.post("/chat", json={
            "session_id": "mem-fix-test",
            "message": "Can you explain Vendor Services again?"
        })
        d2 = r2.json()
        print("T2 results:", d2.get("source", {}).get("id"))
        print("Memory used:", d2.get("memory_used"))
        print("Memory refs:", d2.get("memory_turn_refs"))

asyncio.run(run())
