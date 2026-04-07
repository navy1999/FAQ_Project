# Decisions Document

## Stack Choices

- **Backend**: FastAPI for async endpoint handling — lightweight, modern, and well-suited to wrapping retrieval scripts as HTTP endpoints.
- **Frontend**: React + Vite for fast local bootstrapping with zero complex build overhead; pure TypeScript/React hooks.
- **Dependencies**: Restricted to Python packages (`sentence-transformers`, `faiss-cpu`, `fastapi`, `httpx`). No Docker, no external database — guarantees maximum portability and offline operation.

---

## Retrieval Architecture

Retrieval uses a **three-layer pipeline**:

1. **Domain Rules pre-screen** (`domain_rules.py`): A Bloom filter + Trie-based keyword gate runs first. It immediately short-circuits queries that have zero lexical overlap with the FAQ corpus, returning `domain_miss=True` before any vector computation occurs. This is a domain guard, not a performance optimization — it prevents low-confidence but non-zero FAISS scores for completely unrelated topics (e.g., "tell me about pizza").

2. **SBERT + FAISS semantic retrieval** (`retriever.py`): Queries that pass the pre-screen are encoded via `all-MiniLM-L6-v2` and searched against a `faiss-cpu` `IndexFlatIP` index. Vectors are L2-normalized so inner product equals cosine similarity.

3. **Two-tier confidence gate** (`main.py`): The raw FAISS score drives routing:
   - **Score < 0.45** → `domain_miss=True` (refuse, out-of-domain)
   - **Score < 0.72** → `needs_clarification=True` (ask for more detail)
   - **Score ≥ 0.72** → confident match, proceed to synthesis

---

## Memory Design

`ConversationMemory` is a deque-backed short-term store with a configurable window size.
The **Memory Indicator pill** in the UI makes it explicitly visible when the agent is using prior context — a deliberate design choice so users can trust the system isn't hallucinating references.

### Query Expansion on Low Confidence

When the retriever returns `domain_miss=True` or `needs_clarification=True`, the `/chat` and `/chat/stream` endpoints check session memory for the most recent prior user turn. If found, it prepends that turn to the current query and retries retrieval once:

```
expanded_query = f"{last_user_query} {current_query}"
```

This resolves conversational follow-ups like `"what about the sandbox?"` after `"what APIs are available?"` without requiring the user to repeat full context. The expansion only runs when the first retrieval attempt fails — zero latency cost on the happy path.

---

## Scope Tradeoffs

- **Authentication**: No auth implemented — keeps the app fully portable and self-contained.
- **HIPAA Data**: A specific domain rule instantly rejects any query asking to process or handle HIPAA/PHI data, since this is a local sandbox tool.
- **LLM Dependency**: Default operation is fully local/template-based (offline). If `OPENROUTER_API_KEY` is set, the app switches automatically to LLM synthesis (Qwen3 via OpenRouter). We accept slightly less flexible template phrasing in exchange for guaranteed offline operation.

---

## DSA Design Decisions

### Bloom Filter — Domain Guard, Not Speed Optimization

The Bloom filter (`pybloom_live`, capacity=500, error_rate=0.01) is **not** a performance optimization — FAISS `IndexFlatIP` over 32 entries is already sub-millisecond. Instead it serves as a **domain guard** that deterministically rejects queries with zero lexical overlap with the FAQ corpus, preventing semantically noisy-but-non-zero FAISS scores for off-topic queries. We trade a small amount of memory for deterministic rejection without any vector computation.

### Trie-Based Domain Rule Matching — O(k) Prefix Match

`check_domain_rules()` uses a word-level Trie built at module load time from the trigger phrases in `_RULES`. For each query the Trie performs O(k) prefix matching where k = number of words in the query. This scales to thousands of routing rules without per-query cost growth, unlike the previous O(n × k) linear substring scan over all triggers.

### LRU Cache + Query Normalization — Cache Hit Rate

`_normalize_query()` applies NFKC unicode normalization, lowercasing, whitespace collapsing, and punctuation stripping before the LRU cache lookup. This ensures trivially different queries like `"How do I enroll?"` and `"how do i enroll"` map to the same cache key, improving the hit rate of the 128-entry LRU cache and avoiding redundant 22ms SBERT forward passes for equivalent queries. Cache stats are exposed via `/health`.

### Heap-Based Session Eviction — O(k log n) vs O(n)

`SessionStore.evict_stale()` uses a min-heap (`heapq`) keyed on session creation time. When evicting, we pop only the oldest entries until we reach a non-expired timestamp, giving O(k log n) where k = expired sessions. The alternative linear scan is O(n) over all sessions. At current scale both are equivalent, but the heap documents the correct pattern for horizontal scaling where session counts grow to O(10⁴+).
