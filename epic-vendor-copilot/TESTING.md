# Testing Strategy

The backend logic is covered by a suite of Pytest unit tests, specifically avoiding the need for a live server connection wherever possible.

## How To Run
```bash
pytest backend/tests/ -v
```

## What Each Test File Covers

1. **`test_memory.py`**:
   - Deque eviction when the window size (`max_turns`) is exceeded.
   - Verification that `used_faq_ids()` produces a proper union.
   - Testing recency context splits (summarizing older contexts vs giving full for recent contexts).
   - Validation of `SessionStore.evict_stale()`.

2. **`test_retriever.py`**:
   - Verifies the semantic retriever triggers on highly confident known FAQs.
   - Specifically validates that the PyBloom domain guard properly rejects completely off-topic queries (like pizza-related inquiries).
   - Ensures paraphrased domain-accurate queries (like asking about joining despite "enroll" being the actual answer subset keyword) bypass the Bloom filter reliably.
   - Evaluates that low-scoring results correctly toggle the clarification flag.

3. **`test_responder.py`**:
   - Ensures the deterministic `MODE_A` template synthesis functions correctly when returning one or multiple lists.
   - Tests that clarification prompts surface up into the standard answer string without fail.
   - Uses extreme token/query limits to ensure `build_prompt()` aggressively truncates to fit perfectly within the 800-token budget restriction, regardless of memory history depth.
