"""
responder.py
------------
Response synthesis for the Epic Vendor Services FAQ copilot.

Modes:
  MODE_A (template): Deterministic template-based synthesis when no OpenAI key
  MODE_B (LLM): OpenAI gpt-4o-mini when OPENAI_API_KEY is set

Token budget: 800 tokens (whitespace-split approximation).
No tiktoken dependency — uses len(text.split()) as token proxy.

No FastAPI imports — importable standalone.
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

#Openrouter key and config
_OPENROUTER_KEY=os.getenv("OPENROUTER_API_KEY")
_OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
_OPENROUTER_MODEL="qwen/qwen3.6-plus:free"

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
    domain_route: str | None = None,
) -> str:
    """
    Build the full prompt for the LLM or for template reference.

    Includes:
      - System persona
      - Memory context (recency_context format)
      - Retrieved FAQ chunks (answer_text[:200] each)
      - User query
      - Domain route hint (if any)

    Enforces a hard cap of 800 tokens. Truncates oldest memory turns first
    if over budget.
    """
    parts = [_SYSTEM_PERSONA, ""]

    # Domain route hint
    if domain_route:
        parts.append(f"[Domain route detected: {domain_route}]")
        parts.append("")

    # Retrieved FAQ context
    if retrieved_chunks:
        parts.append("FAQ Context:")
        for i, chunk in enumerate(retrieved_chunks, 1):
            truncated = chunk.get("answer_text", "")[:200]
            parts.append(f"  [{i}] {truncated}")
        parts.append("")

    # Build base prompt without memory to check remaining budget
    parts.append(f"User question: {query}")
    base_prompt = "\n".join(parts)
    remaining_budget = _TOKEN_BUDGET - _count_tokens(base_prompt)

    # Add memory context, truncating from oldest if necessary
    if memory_context and remaining_budget > 20:
        memory_lines = []
        for ctx in memory_context:
            if "content" in ctx:
                line = f"  {ctx['role']}: {ctx['content']}"
            else:
                line = f"  {ctx['role']} (summary): {ctx.get('summary', '')}"
            memory_lines.append(line)

        # Truncate oldest memory turns to fit budget
        while memory_lines and _count_tokens("\n".join(memory_lines)) > remaining_budget - 5:
            memory_lines.pop(0)

        if memory_lines:
            memory_header = "Conversation history:"
            memory_block = "\n".join([memory_header] + memory_lines + [""])
            # Insert memory after persona, before FAQ context
            parts.insert(2, memory_block)

    final_prompt = "\n".join(parts)

    # Final safety truncation — hard cap at 800 tokens
    words = final_prompt.split()
    if len(words) > _TOKEN_BUDGET:
        final_prompt = " ".join(words[:_TOKEN_BUDGET])

    return final_prompt


# ── Template synthesis (MODE_A) ──────────────────────────────────────────────

_CLARIFICATION_RESPONSE = (
    "I wasn't able to find an exact match for that in the "
    "Epic Vendor Services FAQ. Could you rephrase your question? "
    "I can help with topics like account access, APIs, sandboxes, "
    "membership, and learning resources."
)


def _template_synthesize(
    query: str,
    retrieval_result: dict,
    memory_context: list[dict],
    domain_route: str | None,
) -> dict:
    """
    MODE_A: Deterministic template-based response synthesis.

    Rules:
      - domain_miss or needs_clarification → clarification response
      - 1 result → return answer_text directly
      - 2-3 results → numbered list combining top answers
    """
    results = retrieval_result.get("results", [])
    domain_miss = retrieval_result.get("domain_miss", False)
    needs_clarification = retrieval_result.get("needs_clarification", False)

    if domain_miss or needs_clarification:
        prompt = build_prompt(query, results, memory_context, domain_route)
        return {
            "answer": _CLARIFICATION_RESPONSE,
            "mode": "template",
            "source_ids": [r["id"] for r in results],
            "clarification_needed": True,
            "token_budget_used": _count_tokens(prompt),
        }

    prompt = build_prompt(query, results, memory_context, domain_route)

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
        "clarification_needed": False,
        "token_budget_used": _count_tokens(prompt),
    }


# ── LLM synthesis (MODE_B) ──────────────────────────────────────────────────

def _llm_synthesize(
    query: str,
    retrieval_result: dict,
    memory_context: list[dict],
    domain_route: str | None,
) -> dict:
    results = retrieval_result.get("results", [])
    needs_clarification = retrieval_result.get("needs_clarification", False)
    domain_miss = retrieval_result.get("domain_miss", False)

    prompt = build_prompt(query, results, memory_context, domain_route)

    if not _OPENAI_AVAILABLE:
        return _template_synthesize(query, retrieval_result, memory_context, domain_route)

    # Build client — OpenRouter or OpenAI
    if _LLM_PROVIDER == "openrouter":
        client = openai.OpenAI(
            api_key=_OPENROUTER_KEY,
            base_url=_OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "http://localhost:5173",   # required by OpenRouter
                "X-Title": "Epic Vendor Copilot",          # shows in your OR dashboard
            },
        )
        model = _OPENROUTER_MODEL
    else:
        client = openai.OpenAI(api_key=_OPENAI_KEY)
        model = "gpt-4o-mini"

    response = client.chat.completions.create(
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
        "clarification_needed": needs_clarification or domain_miss,
        "token_budget_used": _count_tokens(prompt),
    }


# ── Public API ───────────────────────────────────────────────────────────────

def synthesize(
    query: str,
    retrieval_result: dict,
    memory: object | None = None,
    domain_route: str | None = None,
) -> dict:
    """
    Synthesize a response to the user query.

    Args:
        query: The user's question
        retrieval_result: Output from retriever.retrieve()
        memory: ConversationMemory instance (used for recency_context())
        domain_route: Domain route string if query was pre-routed

    Returns:
        {
            "answer": str,
            "mode": "template" | "llm",
            "source_ids": [str],
            "clarification_needed": bool,
            "token_budget_used": int
        }
    """
    # Get memory context
    memory_context = []
    if memory is not None and hasattr(memory, "recency_context"):
        memory_context = memory.recency_context()

    if MODE == "llm":
        return _llm_synthesize(query, retrieval_result, memory_context, domain_route)
    else:
        return _template_synthesize(query, retrieval_result, memory_context, domain_route)

# ── Streaming API ────────────────────────────────────────────────────────────

async def _template_synthesize_streaming(
    query: str,
    retrieval_result: dict,
    memory_context: list[dict],
    domain_route: str | None,
):
    # Get the complete deterministic answer
    sync_result = _template_synthesize(query, retrieval_result, memory_context, domain_route)
    answer = sync_result["answer"]
    words = answer.split(" ")
    
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        yield f'data: {json.dumps({"chunk": chunk})}\n\n'
        await asyncio.sleep(0.03)

    final_payload = {
        "done": True,
        "source_ids": sync_result["source_ids"],
        "clarification_needed": sync_result["clarification_needed"],
        "mode": sync_result["mode"],
        "token_budget_used": sync_result["token_budget_used"]
    }
    yield f'data: {json.dumps(final_payload)}\n\n'


async def _llm_synthesize_streaming(
    query: str,
    retrieval_result: dict,
    memory_context: list[dict],
    domain_route: str | None,
):
    results = retrieval_result.get("results", [])
    needs_clarification = retrieval_result.get("needs_clarification", False)
    domain_miss = retrieval_result.get("domain_miss", False)

    prompt = build_prompt(query, results, memory_context, domain_route)

    if not _OPENAI_AVAILABLE:
        async for chunk in _template_synthesize_streaming(query, retrieval_result, memory_context, domain_route):
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
        "source_ids": [r["id"] for r in results],
        "clarification_needed": needs_clarification or domain_miss,
        "mode": "llm",
        "token_budget_used": _count_tokens(prompt)
    }
    yield f'data: {json.dumps(final_payload)}\n\n'

async def synthesize_stream(
    query: str,
    retrieval_result: dict,
    memory: object | None = None,
    domain_route: str | None = None,
):
    memory_context = []
    if memory is not None and hasattr(memory, "recency_context"):
        memory_context = memory.recency_context()

    if MODE == "llm":
        async for chunk in _llm_synthesize_streaming(query, retrieval_result, memory_context, domain_route):
            yield chunk
    else:
        async for chunk in _template_synthesize_streaming(query, retrieval_result, memory_context, domain_route):
            yield chunk
