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
from typing import Optional, Literal

import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
import nltk
for _corpus in ("wordnet", "omw-1.4"):
    try:
        nltk.data.find(f"corpora/{_corpus}")
    except LookupError:
        nltk.download(_corpus, quiet=True)

from backend.memory import ConversationMemory, SessionStore, Turn
from backend.responder import MODE, _LLM_PROVIDER, _OPENROUTER_MODEL, synthesize
from backend.domain_rules import check_domain_rules
from backend.context_utils import _extract_user_context, _is_intro_only

_STARTUP_TIME = time.time()

DOMAIN_MISS_RESPONSE = (
    "I can only answer questions about Epic Vendor Services. "
    "For other topics, please visit vendorservices.epic.com."
)
CLARIFICATION_RESPONSE = (
    "Could you clarify what you'd like to know about Epic Vendor Services? "
    "For example, are you asking about enrollment, pricing, APIs, or something else?"
)

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
    print(f"[Startup] Response mode: {MODE}" + (f" ({_LLM_PROVIDER})" if _LLM_PROVIDER else ""))

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

import os
_CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:5174"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
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


ResponseType = Literal["answer", "clarification", "domain_miss"]

class ChatResponse(BaseModel):
    answer: str
    source: SourceResponse
    memory_used: bool
    memory_turn_refs: list[int]
    response_type: ResponseType
    mode: str  # "template" | "llm"


def _is_valid_query(query: str) -> bool:
    q = query.strip()
    return 3 <= len(q) <= 500 and any(c.isalpha() for c in q)


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Main chat endpoint. 
    1. Validate query
    2. Retrieve top matches
    3. Route based on top_score threshold
    4. Call synthesize if OK
    """
    if not _is_valid_query(req.message):
        return ChatResponse(
            answer="Please enter a valid question.",
            source=SourceResponse(),
            memory_used=False,
            memory_turn_refs=[],
            response_type="clarification",
            mode="template"
        )

    memory = session_store.get_or_create(req.session_id)
    profile = session_store.get_profile(req.session_id)
    _extract_user_context(req.message, profile)

    if _is_intro_only(req.message) and not profile.is_empty():
        greeting = f"Hi {profile.name}! " if profile.name else "Hi! "
        role_ack = f"I'll keep in mind that you're a {profile.role}. " if profile.role else ""
        return ChatResponse(
            answer=f"{greeting}{role_ack}How can I help you with Epic Vendor Services today?",
            source=SourceResponse(),
            memory_used=False,
            memory_turn_refs=[],
            response_type="answer",
            mode=MODE
        )

    # Pre-retrieval domain guard
    _pre_action = check_domain_rules(req.message)
    if _pre_action == "vague":
        return ChatResponse(
            answer=CLARIFICATION_RESPONSE,
            source=SourceResponse(),
            memory_used=False,
            memory_turn_refs=[],
            response_type="clarification",
            mode="template"
        )
    elif _pre_action == "ood_hard_block":
        return ChatResponse(
            answer=DOMAIN_MISS_RESPONSE,
            source=SourceResponse(),
            memory_used=False,
            memory_turn_refs=[],
            response_type="domain_miss",
            mode="template"
        )

    retriever = _get_retriever()
    current_turn_index = len(memory.context_window())

    # Step 1: Retrieval
    retrieval_result = retriever.retrieve(req.message)
    top_score = retrieval_result.get("top_score")

    # Step 2: Routing logic
    response_type: ResponseType = "answer"
    answer = ""
    
    if top_score is None or top_score < 0.45:
        response_type = "domain_miss"
        answer = DOMAIN_MISS_RESPONSE
    elif top_score < 0.65:
        # Check memory expansion before committing to clarification
        context_window = memory.context_window()
        last_user_query = None
        for turn in reversed(context_window):
            if turn.role == "user":
                last_user_query = turn.content
                break
        
        if last_user_query and len(req.message.split()) <= 4:
            expanded_query = f"{last_user_query} {req.message}"
            expanded_result = retriever.retrieve(expanded_query)
            ex_score = expanded_result.get("top_score")
            if ex_score and ex_score >= 0.65:
                retrieval_result = expanded_result
                top_score = ex_score
            else:
                response_type = "clarification"
                answer = CLARIFICATION_RESPONSE
        else:
            # Self-contained query that scored low → clarify, don't memory-expand
            # First-turn fallback: try domain-boosted query before giving up
            domain_boosted = f"Epic Vendor Services {req.message}"
            boosted_result = retriever.retrieve(domain_boosted)
            b_score = boosted_result.get("top_score")
            if b_score and b_score >= 0.65:
                retrieval_result = boosted_result
                top_score = b_score
            else:
                response_type = "clarification"
                answer = CLARIFICATION_RESPONSE

    # Step 3: Handle Non-Answer routes
    if response_type != "answer":
        user_turn = Turn(role="user", content=req.message, retrieved_ids=[], turn_index=current_turn_index, timestamp=time.time())
        memory.add(user_turn)
        assistant_turn = Turn(role="assistant", content=answer, retrieved_ids=[], turn_index=current_turn_index + 1, timestamp=time.time())
        memory.add(assistant_turn)
        
        return ChatResponse(
            answer=answer,
            source=SourceResponse(),
            memory_used=False,
            memory_turn_refs=[],
            response_type=response_type,
            mode=MODE
        )

    # Step 4: Answer route
    if not retrieval_result.get("results"):
        return ChatResponse(
            answer=DOMAIN_MISS_RESPONSE,
            source=SourceResponse(),
            memory_used=False,
            memory_turn_refs=[],
            response_type="domain_miss",
            mode=MODE
        )

    retrieved_ids = [r["id"] for r in retrieval_result.get("results", [])]
    prior_ids = memory.used_faq_ids()
    memory_used = bool(prior_ids & set(retrieved_ids))
    memory_turn_refs = [
        t.turn_index for t in memory.context_window()
        if t.role == "user" and any(fid in prior_ids for fid in t.retrieved_ids)
    ]

    user_turn = Turn(role="user", content=req.message, retrieved_ids=retrieved_ids, turn_index=current_turn_index, timestamp=time.time())
    memory.add(user_turn)

    synth = await synthesize(
        query=req.message,
        retrieval_result=retrieval_result,
        memory=memory,
        profile=profile,
    )

    assistant_turn = Turn(role="assistant", content=synth["answer"], retrieved_ids=retrieved_ids, turn_index=current_turn_index + 1, timestamp=time.time())
    memory.add(assistant_turn)

    top = retrieval_result["results"][0]
    return ChatResponse(
        answer=synth["answer"],
        source=SourceResponse(id=top["id"], section=top["section"], question=top["question"], url=top["source_url"], confidence=top["score"]),
        memory_used=memory_used,
        memory_turn_refs=memory_turn_refs,
        response_type="answer",
        mode=synth["mode"]
    )


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Streaming version of the chat endpoint.
    """
    if not _is_valid_query(req.message):
        async def err_stream():
            yield f'data: {json.dumps({"chunk": "Please enter a valid question."})}\n\n'
            yield f'data: {json.dumps({"done": True, "response_type": "clarification", "mode": "template", "source": None})}\n\n'
        return StreamingResponse(err_stream(), media_type="text/event-stream")

    memory = session_store.get_or_create(req.session_id)
    profile = session_store.get_profile(req.session_id)
    _extract_user_context(req.message, profile)

    if _is_intro_only(req.message) and not profile.is_empty():
        async def intro_stream():
            greeting = f"Hi {profile.name}! " if profile.name else "Hi! "
            role_ack = f"I'll keep in mind that you're a {profile.role}. " if profile.role else ""
            full = f"{greeting}{role_ack}How can I help you with Epic Vendor Services today?"
            words = full.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f'data: {json.dumps({"chunk": chunk})}\n\n'
                await asyncio.sleep(0.03)
            yield f'data: {json.dumps({"done": True, "response_type": "answer", "mode": MODE, "source": None, "memory_used": False, "memory_turn_refs": []})}\n\n'
        return StreamingResponse(intro_stream(), media_type="text/event-stream")

    # Pre-retrieval domain guard
    _pre_action = check_domain_rules(req.message)
    if _pre_action == "vague":
        async def vague_stream():
            words = CLARIFICATION_RESPONSE.split(" ")
            content = ""
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                content += chunk
                yield f'data: {json.dumps({"chunk": chunk})}\n\n'
                await asyncio.sleep(0.03)
            yield f'data: {json.dumps({"done": True, "response_type": "clarification", "mode": "template", "source": None, "memory_used": False, "memory_turn_refs": []})}\n\n'
        return StreamingResponse(vague_stream(), media_type="text/event-stream")
    elif _pre_action == "ood_hard_block":
        async def ood_stream():
            words = DOMAIN_MISS_RESPONSE.split(" ")
            content = ""
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                content += chunk
                yield f'data: {json.dumps({"chunk": chunk})}\n\n'
                await asyncio.sleep(0.03)
            yield f'data: {json.dumps({"done": True, "response_type": "domain_miss", "mode": "template", "source": None, "memory_used": False, "memory_turn_refs": []})}\n\n'
        return StreamingResponse(ood_stream(), media_type="text/event-stream")

    retriever = _get_retriever()
    current_turn_index = len(memory.context_window())

    # Step 1: Retrieval
    retrieval_result = retriever.retrieve(req.message)
    top_score = retrieval_result.get("top_score")

    # Step 2: Routing logic
    response_type: ResponseType = "answer"
    answer = ""
    
    if top_score is None or top_score < 0.45:
        response_type = "domain_miss"
        answer = DOMAIN_MISS_RESPONSE
    elif top_score < 0.65:
        context_window = memory.context_window()
        last_user_query = None
        for turn in reversed(context_window):
            if turn.role == "user":
                last_user_query = turn.content
                break
        
        if last_user_query and len(req.message.split()) <= 4:
            expanded_query = f"{last_user_query} {req.message}"
            expanded_result = retriever.retrieve(expanded_query)
            ex_score = expanded_result.get("top_score")
            if ex_score and ex_score >= 0.65:
                retrieval_result = expanded_result
                top_score = ex_score
            else:
                response_type = "clarification"
                answer = CLARIFICATION_RESPONSE
        else:
            # Self-contained query that scored low → clarify, don't memory-expand
            # First-turn fallback: try domain-boosted query before giving up
            domain_boosted = f"Epic Vendor Services {req.message}"
            boosted_result = retriever.retrieve(domain_boosted)
            b_score = boosted_result.get("top_score")
            if b_score and b_score >= 0.65:
                retrieval_result = boosted_result
                top_score = b_score
            else:
                response_type = "clarification"
                answer = CLARIFICATION_RESPONSE

    # Step 3: Handle Non-Answer routes (Canned responses)
    if response_type != "answer":
        async def canned_stream():
            words = answer.split(" ")
            content = ""
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                content += chunk
                yield f'data: {json.dumps({"chunk": chunk})}\n\n'
                await asyncio.sleep(0.03)
            
            yield f'data: {json.dumps({"done": True, "response_type": response_type, "mode": "template", "source": None, "memory_used": False, "memory_turn_refs": []})}\n\n'
            
            memory.add(Turn(role="user", content=req.message, retrieved_ids=[], turn_index=current_turn_index, timestamp=time.time()))
            memory.add(Turn(role="assistant", content=content, retrieved_ids=[], turn_index=current_turn_index + 1, timestamp=time.time()))

        return StreamingResponse(canned_stream(), media_type="text/event-stream")

    # Step 4: Answer route (Streaming Synthesis)
    if not retrieval_result.get("results"):
        async def err_stream():
            yield f'data: {json.dumps({"chunk": DOMAIN_MISS_RESPONSE})}\n\n'
            yield f'data: {json.dumps({"done": True, "response_type": "domain_miss", "mode": MODE, "source": None})}\n\n'
        return StreamingResponse(err_stream(), media_type="text/event-stream")

    retrieved_ids = [r["id"] for r in retrieval_result.get("results", [])]
    prior_ids = memory.used_faq_ids()
    memory_used = bool(prior_ids & set(retrieved_ids))
    memory_turn_refs = [
        t.turn_index for t in memory.context_window()
        if t.role == "user" and any(fid in prior_ids for fid in t.retrieved_ids)
    ]

    memory.add(Turn(role="user", content=req.message, retrieved_ids=retrieved_ids, turn_index=current_turn_index, timestamp=time.time()))

    from backend.responder import synthesize_stream

    async def response_generator():
        assistant_content = ""
        stream_gen = synthesize_stream(
            query=req.message,
            retrieval_result=retrieval_result,
            memory=memory,
            profile=profile,
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
                    payload["response_type"] = "answer"
                    payload["memory_used"] = memory_used
                    payload["memory_turn_refs"] = memory_turn_refs
                    top = retrieval_result["results"][0]
                    payload["source"] = {
                        "id": top["id"], "section": top["section"], "question": top["question"],
                        "url": top["source_url"], "confidence": top["score"]
                    }
                    if "clarification_needed" in payload:
                        del payload["clarification_needed"]
                    if "source_ids" in payload:
                        del payload["source_ids"]
                    yield f"data: {json.dumps(payload)}\n\n"
            except json.JSONDecodeError:
                yield sse_message

        memory.add(Turn(role="assistant", content=assistant_content, retrieved_ids=retrieved_ids, turn_index=current_turn_index + 1, timestamp=time.time()))

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
            "type": "semantic-faiss",
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
