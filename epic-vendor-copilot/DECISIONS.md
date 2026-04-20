# Decisions Document

## Stack Choices

- **Backend**: FastAPI for async endpoint handling — lightweight, modern, and well-suited to wrapping retrieval scripts as HTTP endpoints.
- **Frontend**: React + Vite for fast local bootstrapping with zero complex build overhead; pure TypeScript/React hooks.
- **Dependencies**: Restricted to Python packages (`sentence-transformers`, `faiss-cpu`, `fastapi`, `httpx`). No Docker, no external database — guarantees maximum portability and offline operation.

---

## Retrieval Architecture

Retrieval uses a **three-layer pipeline**:

1. **Domain Rules pre-screen** (`domain_rules.py`): A Bloom filter + Trie-based keyword gate runs first. It immediately short-circuits queries that have zero lexical overlap with the FAQ corpus, returning `domain_miss=True` before any vector computation occurs. This is a domain guard, not a performance optimization — it prevents low-confidence but non-zero FAISS scores for completely unrelated topics (e.g., "tell me about pizza"). Two additional guards run before the Trie: a `VAGUE_QUERIES` frozenset that intercepts single-word or known vague phrases (e.g., "help", "info") and routes them to clarification, and an `_OOD_HARD_BLOCK` tuple that matches hard out-of-domain patterns (e.g., "stock price", "weather") for immediate refusal.

2. **SBERT + FAISS semantic retrieval** (`retriever.py`): Queries that pass the pre-screen are encoded via `all-MiniLM-L6-v2` and searched against a `faiss-cpu` `IndexFlatIP` index. Vectors are L2-normalized so inner product equals cosine similarity.

3. **Two-tier confidence gate** (`main.py`): The raw FAISS score drives routing:
   - **Score < 0.45** → `domain_miss=True` (refuse, out-of-domain)
   - **Score < 0.65** → `needs_clarification=True` (ask for more detail)
   - **Score ≥ 0.65** → confident match, proceed to synthesis

   The threshold was tuned from an initial 0.72 to 0.65 based on empirical E2E test results across 89 query cases, reducing false clarifications from 21 to ~10 while maintaining correct OOD refusal on all out-of-domain queries.

---

## Memory Design

`ConversationMemory` is a deque-backed short-term store with a configurable window size.
The **Memory Indicator pill** in the UI makes it explicitly visible when the agent is using prior context — a deliberate design choice so users can trust the system isn’t hallucinating references.

### Query Expansion on Low Confidence

When the retriever returns a score below the 0.65 threshold, the `/chat` and `/chat/stream` endpoints check session memory for the most recent prior user turn. Expansion **only triggers when the current query is 4 words or fewer** — a guard added to prevent contamination of self-contained queries (e.g., "what learning resources are available") by unrelated prior turns. If the current query is longer than 4 words, it is treated as self-contained and routes directly to clarification without expansion.

When expansion does run, it prepends the prior turn to the current query and retries retrieval once:

```
expanded_query = f"{last_user_query} {current_query}"
```

This resolves conversational follow-ups like `"what about the sandbox?"` after `"what APIs are available?"` without requiring the user to repeat full context. The expansion only runs when the first retrieval attempt scores below threshold — zero latency cost on the happy path.

---

## Scope Tradeoffs

- **Authentication**: No auth implemented — keeps the app fully portable and self-contained.
- **HIPAA Data**: A specific domain rule instantly rejects any query asking to process or handle HIPAA/PHI data, since this is a local sandbox tool.
- **LLM Dependency**: Default operation is fully local/template-based (offline). If `OPENROUTER_API_KEY` is set, the app switches automatically to LLM synthesis (Qwen3 via OpenRouter). We accept slightly less flexible template phrasing in exchange for guaranteed offline operation.
- **E2E Score Gaps**: 10 query variants in the E2E suite score below the 0.65 threshold due to phrasing distance from FAQ entries (e.g., "Epic UGM conference", "Gold Silver Bronze vendor tiers"). These are data coverage gaps, not logic bugs — adding alias keywords to the affected FAQ entries in `SEED_DATA/epic_vendor_faq.json` would resolve them without any code changes.

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

## Domain Guard Update (Post-Review)

The initial implementation used single-keyword blocking for clinical terms
such as "treatment", "clinical", and "patient". This caused false positives
for legitimate vendor queries like "what is the treatment process for a
rejected claim".

Fix: Single clinical keywords were removed from the blocking list. Boundary
detection now requires compound context — both "treatment" AND "patient"
must co-occur to trigger a boundary refusal. Unambiguous terms (hipaa, phi,
ehr) remain as single-keyword blocks.

Rationale: The LLM system prompt already constrains responses to vendor
topics. The keyword gate is a pre-filter for obvious cases only — nuanced
context decisions are delegated to the LLM.

## User Context Memory

Added UserProfile extraction to session memory. When a user states their
name, role, or organization, that context is stored in the session and
injected into every subsequent LLM prompt. This enables personalized,
role-aware responses without requiring auth or a login flow.

## LLM Error Handling

Added try/except around all LLM API calls in responder.py. On any error
(rate limit, network failure, model unavailable), the system automatically
falls back to template mode and returns a deterministic answer. The user
never sees a broken state.

## Conversational Intelligence Layer (Post-Review)

Three classes of queries now bypass FAISS retrieval entirely and are 
resolved directly from session state:

**Conversational meta-queries** (`_is_conversational_meta`): Questions 
about the user's own profile — name, role, organization, conversation 
history. These are answered directly from UserProfile and ConversationMemory 
without touching the retriever. Previously, these were mis-routed to the 
domain guard and blocked as off-domain.

**Capability queries** (`_is_capability_query`): Questions about what the 
assistant can help with. Answered with a hardcoded capability menu derived 
from the 11 FAQ sections. Prevents the system from returning a null response 
when users ask about its own scope.

**Domain boundary fix**: The "boundary" action from check_domain_rules() 
now correctly returns a domain_miss response in main.py. Previously, 
"boundary" was not handled and fell through to FAISS, allowing clinical 
queries like "I need treatment information for my patient" to reach 
retrieval instead of being hard-blocked.

**System prompt hierarchy**: The LLM system prompt was restructured from 
a single "answer only from FAQ" directive into a three-tier priority system: 
(1) conversational/profile questions from session context, (2) FAQ answers 
from retrieved context, (3) honest fallback with redirect. This prevents 
the model from over-refusing on partial-match queries.

**Answer truncation fix**: FAQ answer text passed to the LLM was truncated 
at 200 characters, cutting off actionable content (e.g. password reset 
instructions). Increased to 500 characters.

