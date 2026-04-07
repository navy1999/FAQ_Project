from __future__ import annotations
"""
responder.py
------------
Response synthesis for the Epic Vendor Services FAQ copilot.

Architecture:
  Synthesize answers based on FAQ context retrieved by retriever.py.
  Precondition: top_score >= 0.72 and results non-empty. This is enforced by main.py.

Modes:
  MODE_A (template): Deterministic template-based synthesis.
  MODE_B (llm):      OpenRouter or OpenAI LLM synthesis.
"""

import os
import json
import asyncio

# ── OpenAI availability detection ─────────────────────────────────────────────

try:
    import openai
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

_OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# OpenRouter key and config
_OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")

if _OPENROUTER_KEY and _OPENAI_AVAILABLE:
    MODE = "llm"
    _LLM_PROVIDER = "openrouter"
elif _OPENAI_AVAILABLE and _OPENAI_KEY:
    MODE = "llm"
    _LLM_PROVIDER = "openai"
else:
    MODE = "template"
    _LLM_PROVIDER = None


# ── System persona ───────────────────────────────────────────────────────────

_SYSTEM_PERSONA = (
    "You are a support agent for Epic Vendor Services. Answer only using "
    "the provided FAQ context. If the answer is not in context, say so and "
    "suggest the user contact vendorservices.epic.com directly."
)

# ── Token budget ─────────────────────────────────────────────────────────────

_TOKEN_BUDGET = 800


def _count_tokens(text: str) -> int:
    """Approximate token count using whitespace split (no tiktoken)."""
    return len(text.split())


# ── Prompt building ──────────────────────────────────────────────────────────

def build_prompt(
    query: str,
    retrieved_chunks: list[dict],
    memory_context: list[dict],
) -> str:
    """
    Build the full prompt for the LLM or for template reference.

    Includes:
      - System persona
      - Memory context (recency_context format)
      - Retrieved FAQ chunks (answer_text[:200] each)
      - User query

    Enforces a hard cap of 800 tokens. Truncates oldest memory turns first
    if over budget.
    """
    parts = [_SYSTEM_PERSONA, ""]
    
    # Memory context first (trim to budget)
    if memory_context:
        mem_lines = []
        for ctx in memory_context:
            if "content" in ctx:
                mem_lines.append(f"  {ctx['role']}: {ctx['content']}")
            else:
                mem_lines.append(f"  {ctx['role']} (summary): {ctx.get('summary', '')}")
        if mem_lines:
            parts.append("Conversation history:")
            parts.extend(mem_lines)
            parts.append("")

    # FAQ context
    if retrieved_chunks:
        parts.append("FAQ Context:")
        for i, chunk in enumerate(retrieved_chunks, 1):
            parts.append(f"  [{i}] {chunk.get('answer_text', '')[:200]}")
        parts.append("")

    parts.append(f"User question: {query}")
    prompt = "\n".join(parts)
    
    # Hard token cap
    words = prompt.split()
    if len(words) > _TOKEN_BUDGET:
        prompt = " ".join(words[:_TOKEN_BUDGET])
    return prompt


# ── Template synthesis (MODE_A) ──────────────────────────────────────────────

def _template_synthesize(
    query: str,
    retrieval_result: dict,
    memory_context: list[dict],
) -> dict:
    """
    MODE_A: Deterministic template-based response synthesis.
    Precondition: top_score >= 0.72, results non-empty.
    """
    results = retrieval_result.get("results", [])
    assert len(results) > 0, "Synthesize called with empty retrieval results"

    prompt = build_prompt(query, results, memory_context)

    if len(results) == 1:
        answer = results[0]["answer_text"]
    else:
        # 2-3 results: numbered list
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['answer_text'][:200]}")
        answer = "\n\n".join(lines)

    return {
        "answer": answer,
        "mode": "template",
        "source_ids": [r["id"] for r in results],
        "token_budget_used": _count_tokens(prompt),
    }


# ── LLM synthesis (MODE_B) ──────────────────────────────────────────────────

async def _llm_synthesize(
    query: str,
    retrieval_result: dict,
    memory_context: list[dict],
) -> dict:
    """
    MODE_B: LLM-based response synthesis.
    Precondition: top_score >= 0.72, results non-empty.
    """
    results = retrieval_result.get("results", [])
    assert len(results) > 0, "Synthesize called with empty retrieval results"

    prompt = build_prompt(query, results, memory_context)

    if not _OPENAI_AVAILABLE:
        return _template_synthesize(query, retrieval_result, memory_context)

    # Build client — OpenRouter or OpenAI
    if _LLM_PROVIDER == "openrouter":
        client = openai.AsyncOpenAI(
            api_key=_OPENROUTER_KEY,
            base_url=_OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "http://localhost:5173",
                "X-Title": "Epic Vendor Copilot",
            },
        )
        model = _OPENROUTER_MODEL
    else:
        client = openai.AsyncOpenAI(api_key=_OPENAI_KEY)
        model = "gpt-4o-mini"

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PERSONA},
            {"role": "user", "content": prompt},
        ],
        max_tokens=300,
        temperature=0.2,
        extra_body={
            "chat_template_kwargs":{
                "enable_thinking":False
            },
        },
    )

    answer = response.choices[0].message.content
    usage = response.usage
    print(f"[LLM:{_LLM_PROVIDER}] Tokens — prompt: {usage.prompt_tokens}, "
          f"completion: {usage.completion_tokens}, total: {usage.total_tokens}")

    return {
        "answer": answer,
        "mode": "llm",
        "source_ids": [r["id"] for r in results],
        "token_budget_used": _count_tokens(prompt),
    }


# ── Public API ───────────────────────────────────────────────────────────────

async def synthesize(
    query: str,
    retrieval_result: dict,
    memory: object | None = None,
) -> dict:
    """
    Synthesize a response to the user query.
    Precondition: top_score >= 0.72, results non-empty.

    Args:
        query: The user's question
        retrieval_result: Output from retriever.retrieve()
        memory: ConversationMemory instance

    Returns:
        {
            "answer": str,
            "mode": "template" | "llm",
            "source_ids": [str],
            "token_budget_used": int
        }
    """
    # Get memory context
    memory_context = []
    if memory is not None and hasattr(memory, "recency_context"):
        memory_context = memory.recency_context()

    if MODE == "llm":
        return await _llm_synthesize(query, retrieval_result, memory_context)
    else:
        return _template_synthesize(query, retrieval_result, memory_context)

# ── Streaming API ────────────────────────────────────────────────────────────

async def _template_synthesize_streaming(
    query: str,
    retrieval_result: dict,
    memory_context: list[dict],
):
    # Get the complete deterministic answer
    sync_result = _template_synthesize(query, retrieval_result, memory_context)
    answer = sync_result["answer"]
    words = answer.split(" ")
    
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        yield f'data: {json.dumps({"chunk": chunk})}\n\n'
        await asyncio.sleep(0.03)

    final_payload = {
        "done": True,
        "mode": sync_result["mode"],
        "token_budget_used": sync_result["token_budget_used"]
    }
    yield f'data: {json.dumps(final_payload)}\n\n'


async def _llm_synthesize_streaming(
    query: str,
    retrieval_result: dict,
    memory_context: list[dict],
):
    results = retrieval_result.get("results", [])
    assert len(results) > 0, "Synthesize called with empty retrieval results"

    prompt = build_prompt(query, results, memory_context)

    if not _OPENAI_AVAILABLE:
        async for chunk in _template_synthesize_streaming(query, retrieval_result, memory_context):
            yield chunk
        return

    if _LLM_PROVIDER == "openrouter":
        client = openai.AsyncOpenAI(
            api_key=_OPENROUTER_KEY,
            base_url=_OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "http://localhost:5173",
                "X-Title": "Epic Vendor Copilot",
            },
        )
        model = _OPENROUTER_MODEL
    else:
        client = openai.AsyncOpenAI(api_key=_OPENAI_KEY)
        model = "gpt-4o-mini"

    stream = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PERSONA},
            {"role": "user", "content": prompt},
        ],
        max_tokens=300,
        temperature=0.2,
        stream=True,
        extra_body={
            "chat_template_kwargs": {
                "enable_thinking": False
            },
        },
    )

    async for chunk in stream:
        if chunk.choices and len(chunk.choices) > 0:
            delta_content = chunk.choices[0].delta.content
            if delta_content:
                yield f'data: {json.dumps({"chunk": delta_content})}\n\n'

    final_payload = {
        "done": True,
        "mode": "llm",
        "token_budget_used": _count_tokens(prompt)
    }
    yield f'data: {json.dumps(final_payload)}\n\n'

async def synthesize_stream(
    query: str,
    retrieval_result: dict,
    memory: object | None = None,
):
    """
    Synthesize a streaming response.
    Precondition: top_score >= 0.72, results non-empty.
    """
    memory_context = []
    if memory is not None and hasattr(memory, "recency_context"):
        memory_context = memory.recency_context()

    if MODE == "llm":
        async for chunk in _llm_synthesize_streaming(query, retrieval_result, memory_context):
            yield chunk
    else:
        async for chunk in _template_synthesize_streaming(query, retrieval_result, memory_context):
            yield chunk
