# Testing Documentation

The test suite is structured in two layers: **pytest unit/integration tests** for backend correctness, and a **standalone end-to-end query test suite** for retrieval accuracy across the full FAQ corpus.

**Current result: 61 passed, 0 failed.**

(Note: The post-review spec referenced a target of 74 tests, but the conversational-intelligence-layer changes were delivered without expanding the test suite per the "no new test files" directive. A later revision removed the hardcoded `_is_conversational_meta` / `_is_capability_query` handlers in favor of LLM-driven handling via an enriched system prompt; this removal did not change the test count because those handlers had no dedicated tests.)

---

## Layer 1 — pytest Unit & Integration Tests

Run from the project root:

```bash
# macOS / Linux
pytest backend/tests/ -v

# Windows
pytest backend/tests/ -v
```

### Test Manifest

**`backend/tests/test_retriever.py`**
Validates the FAISS retrieval mechanics, Bloom filter boundary constraints, query normalization, and cache behaviour.
- **Domain Miss Checking**: Verifies that queries with zero domain keywords bypass FAISS immediately, yielding `domain_miss=True`.
- **Confidence Thresholds**: Confirms that gibberish queries which pass the Bloom filter but lack semantic content yield an empty results array below the 0.55 confidence floor.
- **Top-K Ordering**: Ensures FAISS returns results sorted descending by similarity score.
- **Known Hits**: Checks that `"how do I enroll"` / `"what is vendor services"` correctly retrieve their canonical FAQ entries.
- **Multi-result Constraints**: Validates broad keyword topics map to up to 3 closest matches.
- **Query Normalization** (`TestNormalization`): `test_normalize_query_logic` confirms NFKC normalization, lowercasing, whitespace collapse, and punctuation stripping. `test_cache_hit_after_normalization` confirms `"How do I enroll?"` and `"how do i enroll"` share a single LRU cache entry.
- **Query Variants** (`TestQueryVariants`): `test_enrollment_variants` and `test_cost_variants` confirm phrasing variants resolve to the correct canonical FAQ id.

**`backend/tests/test_responder.py`**
Ensures correct LLM mode transitions and token budget enforcement.
- **Template Mode**: Mocks `openai.OpenAI` entirely, confirming deterministic template responses fire without hitting OpenRouter.
- **Token Budget**: Simulates dense memory sessions with large string contexts to verify `build_prompt` enforces the 800-token output safety limit.
- **LLM Params**: Validates `enable_thinking=False` is injected into the `extra_body` payload for OpenRouter calls.

**`backend/tests/test_domain_rules.py`**
Checks deterministic routing rules that fire before retrieval.
- `"password"` → `admin_escalation` route.
- `"enroll"` → `enrollment` redirect.
- `"hipaa"` → `hipaa` boundary route.
- Standard queries → `None` (no intercept).
- **Trie Matching**: `test_trie_matches_password_variants` — confirms multi-word prefix variants (e.g., `"reset my password"`, `"forgot password"`) all hit the correct `admin_escalation` route via the Trie. `test_trie_does_not_match_unrelated` — confirms clean separation: unrelated queries return `None` and are not incorrectly intercepted.

**`backend/tests/test_memory.py`**
Validates session memory correctness, eviction, and heap-based session store behaviour.
- **Eviction** (`TestConversationMemoryEviction`): Confirms oldest turns are dropped when the context window is full; single turns are preserved; empty memory returns an empty window.
- **Used FAQ IDs** (`TestUsedFaqIds`): Confirms `used_faq_ids()` unions retrieved IDs across turns correctly.
- **Recency Context** (`TestRecencyContext`): Validates full/summary split at the context window boundary.
- **Session Store Eviction** (`TestSessionStoreEviction`): Confirms stale sessions are removed, fresh sessions are preserved, `get_or_create` returns the same object, and `touch()` updates the last-access timestamp.
- **Heap Eviction** (`TestHeapEviction`): `test_heap_eviction_removes_expired_sessions` — confirms the min-heap correctly identifies and removes expired sessions in O(k log n). `test_heap_does_not_evict_fresh_sessions` — confirms sessions within TTL are untouched.
- **Serialization** (`TestToDict`): Validates `to_dict()` output structure for memory snapshots returned by `/session/{id}/memory`.

**`backend/tests/test_integration.py`**
Uses `httpx.ASGITransport` to test full-stack request/response flows against the live FastAPI app.
- HTTP 200 on valid queries with correctly structured response bodies.
- HTTP 422 on empty strings or malformed payloads.
- `/session/{id}/memory` correctly reflects dual user/assistant turns.
- `/session/{id}` DELETE results in a fully cleared state.
- `/health` returns `retriever`, `memory`, and `provider` fields in the expected format.
- `memory_used=True` on the second turn of a conversation using a repeated FAQ topic.

**`backend/tests/test_chat.py`**
Unit-level tests for the `/chat` and `/chat/stream` routing logic with mocked retriever and synthesizer.
- High-score retrieval → calls `synthesize` and returns `response_type="answer"`.
- Low-score retrieval → returns `response_type="domain_miss"` without calling `synthesize`.
- Mid-score retrieval → returns `response_type="clarification"`.
- Invalid/empty query → returns 422 without touching the retriever.
- Stream endpoint → off-topic query bypasses `synthesize` and streams a canned domain-miss response.

---

## Layer 2 — Known Score Gaps

10 query variants in the E2E harness score below the 0.65 confidence threshold, resulting in a `CLARIFY` response where `ANSWER` is expected. These are **data coverage gaps**, not logic bugs — the retriever correctly scores these queries as uncertain given the current FAQ phrasing.

Affected queries and their root cause:

| Query | Score | Expected FAQ | Gap |
|---|---|---|---|
| `"can I cancel my subscription"` | 0.6417 | vs-1078 | Missing alias: "cancel subscription" |
| `"who manages user access"` | 0.6373 | vs-1119 | Missing alias: "user management" |
| `"when will my account be ready"` | 0.5998 | vs-1278 | Missing alias: "account activation timeline" |
| `"how long until I can log in after enrolling"` | 0.5939 | vs-1120 | Missing alias: "wait time after enrolling" |
| `"REST API documentation"` | 0.6190 | vs-1125 | Missing alias: "API docs" |
| `"Epic UGM conference"` | 0.6234 | vs-1100 | Missing alias: "UGM", "user group meeting" |
| `"online learning portal"` | 0.5889 | vs-1100 | Missing alias: "e-learning", "learning portal" |
| `"test my integration with Epic"` | 0.5707 | vs-1072 | Missing alias: "integration testing" |
| `"Gold Silver Bronze vendor tiers"` | 0.6151 | vs-5798 | Missing alias: "tier comparison" |
| `"something is wrong"` | 0.6521 | — | Should route to CLARIFY — add to `VAGUE_QUERIES` |

The fix for all 9 ANSWER gaps is adding alias keywords to the relevant entries in `SEED_DATA/epic_vendor_faq.json`. The fix for `"something is wrong"` is adding it to `VAGUE_QUERIES` in `domain_rules.py`. No threshold or logic changes are needed.

## Test Changes (UserProfile + qwen3 Guard Update)

Two sets of existing tests were updated in place when the underlying
contracts they targeted changed. The behavior under test still matters —
only the contract moved.

- `backend/tests/test_memory.py` — three tests (`test_evict_stale_removes_old_sessions`,
  `test_touch_updates_timestamp`, `test_heap_eviction_removes_expired_sessions`)
  previously wrote 2-tuples into `SessionStore._store`. After the UserProfile
  change, `_store` holds `(memory, profile, timestamp)` 3-tuples, so those
  writes now include `UserProfile()` and the unpack in `test_touch_updates_timestamp`
  became `_, _, ts = ...`.

- `backend/tests/test_responder.py` — the single
  `test_enable_thinking_false_in_extra_body` test asserted `extra_body` is
  always set for OpenRouter. After the qwen3-only guard was added (sending
  `chat_template_kwargs={"enable_thinking": False}` to Gemma/Llama/GPT
  errors out), that assertion was no longer correct. It was split into two
  explicit branch tests:
  - `test_extra_body_set_for_qwen3_model` — asserts `extra_body` IS sent
    when `_OPENROUTER_MODEL` contains `qwen3`.
  - `test_extra_body_omitted_for_non_qwen3_model` — asserts `extra_body`
    is NOT sent for a Llama model.

  The old single test was deleted because its premise (always-on
  `extra_body`) no longer reflects the implementation.
