from __future__ import annotations

"""
main.py
-------
FastAPI application for the Epic Vendor Services FAQ copilot.

Endpoints:
  POST /chat         — Main chat endpoint
  GET  /session/{id}/memory — Session memory snapshot
  DELETE /session/{id}      — Delete session
  GET  /health              — Health check

Single file. Uses lifespan events for startup/shutdown.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Optional

import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from backend.domain_rules import check_domain_rules
from backend.memory import ConversationMemory, SessionStore, Turn
from backend.responder import MODE, _LLM_PROVIDER, _OPENROUTER_MODEL, synthesize

_STARTUP_TIME = time.time()

# ── Lazy-loaded retriever ────────────────────────────────────────────────────

_retriever_module = None
_entries_count = 0


def _get_retriever():
    global _retriever_module, _entries_count
    if _retriever_module is None:
        from backend import retriever as ret
        _retriever_module = ret
        _entries_count = len(ret._ENTRIES)
    return _retriever_module


# ── Session store singleton ──────────────────────────────────────────────────

session_store = SessionStore()


# ── Background task: periodic stale session eviction ─────────────────────────

async def _evict_stale_loop():
    """Evict stale sessions every 300 seconds."""
    while True:
        await asyncio.sleep(300)
        evicted = session_store.evict_stale()
        if evicted:
            print(f"[SessionStore] Evicted {evicted} stale sessions")


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: warm retriever and start background eviction task."""
    print("[Startup] Warming retriever (SBERT model + FAISS index)...")
    _get_retriever()
    print(f"[Startup] Retriever ready. {_entries_count} FAQ entries loaded.")
    print(f"[Startup] Response mode: {MODE}")

    # Start background eviction task
    evict_task = asyncio.create_task(_evict_stale_loop())

    yield

    # Shutdown
    evict_task.cancel()
    try:
        await evict_task
    except asyncio.CancelledError:
        pass


# ── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Epic Vendor Copilot",
    description="FAQ support copilot for Epic Vendor Services",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message must be non-empty")
        if len(v) > 500:
            raise ValueError("Message must be 500 characters or fewer")
        return v


class SourceResponse(BaseModel):
    id: Optional[str] = None
    section: Optional[str] = None
    question: Optional[str] = None
    url: Optional[str] = None
    confidence: Optional[float] = None


class ChatResponse(BaseModel):
    answer: str
    source: SourceResponse
    memory_used: bool
    memory_turn_refs: list[int]
    domain_route: Optional[str]
    clarification_needed: bool
    mode: str  # "template" | "llm"


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Main chat endpoint. Processing order:
    1. check_domain_rules()
    2. If route matched → return canned response
    3. retriever.retrieve()
    4. Check memory for previously seen FAQ IDs
    5. responder.synthesize()
    6. Record turns in session memory
    7. Return full response
    """
    memory = session_store.get_or_create(req.session_id)
    retriever = _get_retriever()

    # Track turn index
    current_turn_index = len(memory.context_window())

    # Step 1: Domain rules check
    route_result = check_domain_rules(req.message)

    if route_result:
        # Step 2: Routed response
        user_turn = Turn(
            role="user",
            content=req.message,
            retrieved_ids=[],
            turn_index=current_turn_index,
            timestamp=time.time(),
        )
        memory.add(user_turn)

        assistant_turn = Turn(
            role="assistant",
            content=route_result["response"],
            retrieved_ids=[],
            turn_index=current_turn_index + 1,
            timestamp=time.time(),
        )
        memory.add(assistant_turn)

        return ChatResponse(
            answer=route_result["response"],
            source=SourceResponse(),
            memory_used=False,
            memory_turn_refs=[],
            domain_route=route_result["route"],
            clarification_needed=False,
            mode=MODE,
        )

    # Step 3: Retrieval
    retrieval_result = retriever.retrieve(req.message)

    if retrieval_result.get("domain_miss") or retrieval_result.get("needs_clarification"):
        context_window = memory.context_window()
        last_user_query = None
        for turn in reversed(context_window):
            if turn.role == "user":
                last_user_query = turn.content
                break
        
        if last_user_query:
            expanded_query = f"{last_user_query} {req.message}"
            expanded_result = retriever.retrieve(expanded_query)
            if not expanded_result.get("domain_miss") and not expanded_result.get("needs_clarification"):
                retrieval_result = expanded_result

    retrieved_ids = [r["id"] for r in retrieval_result.get("results", [])]

    # Step 4: Memory overlap check
    previously_used = memory.used_faq_ids()
    overlapping_ids = set(retrieved_ids) & previously_used
    memory_used = len(overlapping_ids) > 0

    memory_turn_refs = []
    if memory_used:
        for turn in memory.context_window():
            if set(turn.retrieved_ids) & overlapping_ids:
                memory_turn_refs.append(turn.turn_index)

    # Step 5: Synthesize response
    synth = synthesize(
        query=req.message,
        retrieval_result=retrieval_result,
        memory=memory,
        domain_route=None,
    )

    # Step 6: Record turns
    user_turn = Turn(
        role="user",
        content=req.message,
        retrieved_ids=retrieved_ids,
        turn_index=current_turn_index,
        timestamp=time.time(),
    )
    memory.add(user_turn)

    assistant_turn = Turn(
        role="assistant",
        content=synth["answer"],
        retrieved_ids=retrieved_ids,
        turn_index=current_turn_index + 1,
        timestamp=time.time(),
    )
    memory.add(assistant_turn)

    # Step 7: Build response
    source = SourceResponse()
    if retrieval_result.get("results"):
        top = retrieval_result["results"][0]
        source = SourceResponse(
            id=top["id"],
            section=top["section"],
            question=top["question"],
            url=top["source_url"],
            confidence=top["score"],
        )

    return ChatResponse(
        answer=synth["answer"],
        source=source,
        memory_used=memory_used,
        memory_turn_refs=memory_turn_refs,
        domain_route=None,
        clarification_needed=synth["clarification_needed"],
        mode=synth["mode"],
    )


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Streaming version of the chat endpoint.
    Returns SSE stream with data: {"chunk": "..."} and finally data: {"done": true, ...}.
    """
    memory = session_store.get_or_create(req.session_id)
    retriever = _get_retriever()
    current_turn_index = len(memory.context_window())

    # Step 1: Domain rules check
    route_result = check_domain_rules(req.message)

    if route_result:
        async def mock_stream():
            words = route_result["response"].split(" ")
            assistant_content = ""
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                assistant_content += chunk
                yield f'data: {json.dumps({"chunk": chunk})}\n\n'
                await asyncio.sleep(0.03)
            
            final_payload = {
                "done": True,
                "source": None,
                "memory_used": False,
                "memory_turn_refs": [],
                "domain_route": route_result["route"],
                "clarification_needed": False,
                "mode": MODE
            }
            yield f'data: {json.dumps(final_payload)}\n\n'

            user_turn = Turn(role="user", content=req.message, retrieved_ids=[], turn_index=current_turn_index, timestamp=time.time())
            memory.add(user_turn)
            assistant_turn = Turn(role="assistant", content=assistant_content, retrieved_ids=[], turn_index=current_turn_index + 1, timestamp=time.time())
            memory.add(assistant_turn)

        return StreamingResponse(mock_stream(), media_type="text/event-stream")

    # Step 3: Retrieval
    retrieval_result = retriever.retrieve(req.message)

    if retrieval_result.get("domain_miss") or retrieval_result.get("needs_clarification"):
        context_window = memory.context_window()
        last_user_query = None
        for turn in reversed(context_window):
            if turn.role == "user":
                last_user_query = turn.content
                break
        
        if last_user_query:
            expanded_query = f"{last_user_query} {req.message}"
            expanded_result = retriever.retrieve(expanded_query)
            if not expanded_result.get("domain_miss") and not expanded_result.get("needs_clarification"):
                retrieval_result = expanded_result

    retrieved_ids = [r["id"] for r in retrieval_result.get("results", [])]

    previously_used = memory.used_faq_ids()
    overlapping_ids = set(retrieved_ids) & previously_used
    memory_used = len(overlapping_ids) > 0

    memory_turn_refs = []
    if memory_used:
        for turn in memory.context_window():
            if set(turn.retrieved_ids) & overlapping_ids:
                memory_turn_refs.append(turn.turn_index)

    # Step 4: Stream Synthesis Interception
    from backend.responder import synthesize_stream

    async def response_generator():
        assistant_content = ""
        stream_gen = synthesize_stream(
            query=req.message,
            retrieval_result=retrieval_result,
            memory=memory,
            domain_route=None,
        )

        async for sse_message in stream_gen:
            if not sse_message.startswith("data: "):
                continue
            data_str = sse_message.replace("data: ", "").strip()
            try:
                payload = json.loads(data_str)
                if "chunk" in payload:
                    assistant_content += payload["chunk"]
                    yield sse_message
                elif "done" in payload:
                    payload["memory_used"] = memory_used
                    payload["memory_turn_refs"] = memory_turn_refs
                    source = None
                    if retrieval_result.get("results"):
                        top = retrieval_result["results"][0]
                        source = {
                            "id": top["id"], "section": top["section"], "question": top["question"],
                            "url": top["source_url"], "confidence": top["score"]
                        }
                    payload["source"] = source
                    if "source_ids" in payload:
                        del payload["source_ids"]
                    yield f"data: {json.dumps(payload)}\n\n"
            except json.JSONDecodeError:
                yield sse_message

        user_turn = Turn(
            role="user",
            content=req.message,
            retrieved_ids=retrieved_ids,
            turn_index=current_turn_index,
            timestamp=time.time(),
        )
        memory.add(user_turn)

        assistant_turn = Turn(
            role="assistant",
            content=assistant_content,
            retrieved_ids=retrieved_ids,
            turn_index=current_turn_index + 1,
            timestamp=time.time(),
        )
        memory.add(assistant_turn)

    return StreamingResponse(response_generator(), media_type="text/event-stream")


@app.get("/session/{session_id}/memory")
async def get_memory(session_id: str):
    """Return the session's memory snapshot."""
    memory = session_store.get_or_create(session_id)
    return memory.to_dict()


@app.delete("/session/{session_id}", status_code=204)
async def delete_session(session_id: str):
    """Remove a session from the store."""
    session_store.remove(session_id)
    return None


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "entries_loaded": _entries_count,
        "mode": MODE,
        "provider": _LLM_PROVIDER or "none",
        "model": _OPENROUTER_MODEL if MODE == "llm" else "n/a",
        "retriever": {
            "type": "bloom+faiss",
            "index_size": _entries_count,
            "embedding_model": "all-MiniLM-L6-v2"
        },
        "memory": {
            "active_sessions": session_store.active_count(),
            "max_turns_per_session": 6
        },
        "cache": _retriever_module._CACHE_STATS if _retriever_module else {"hits": 0, "misses": 0, "size": 0},
        "uptime_seconds": round(time.time() - _STARTUP_TIME, 2)
    }
