# Testing Documentation

The test suite is structured around validating core application features synchronously using `pytest`.

## Test Manifest

**1. `backend/tests/test_retriever.py`**
Validates the FAISS retrieval mechanics and Bloom filter boundary constraints.
*   **Domain Miss Checking**: Verifies that queries containing zero domain keywords bypass FAISS immediately yielding `domain_miss=True`.
*   **Confidence Thresholds**: Confirms that gibberish queries that manage to bypass the Bloom filter but lack semantically related content yield an empty results array when their score drops below the 0.55 confidence threshold.
*   **Top-K Ordering**: Ensures FAISS accurately returns an array of multiple results sorted chronologically descending by similarity score.
*   **Known Hits**: Checks a structured `how do I enroll`/`what is vendor services` lookup correctly retrieves identifying top matching FAQ cards (like `vs-1100`).
*   **Multi-result Constraints**: Examines whether broad keyword topics successfully map up to the 3 closest matches logically correctly.

**2. `backend/tests/test_responder.py`**
Ensures proper LLM mode transitions and Token allocations.
*   **Template Mode**: Mocks `openai.OpenAI` entirely confirming that deterministic template responses fire reliably without accessing any OpenRouter network connections.
*   **Token Budget**: Simulates incredibly dense conversational memory sessions with massive string contexts to verify that `build_prompt` strictly forces output length safety parameters under the `800` defined token threshold.
*   **LLM Params**: Evaluates OpenRouter integration kwargs to verify `enable_thinking=False` is injected into the `extra_body` payload structure natively.

**3. `backend/tests/test_domain_rules.py`**
Explicitly checks deterministic routing features catching precise substrings prior to retrieval phases.
*   Validates `"password"` correctly interrupts the workflow assigning the `admin_escalation` route.
*   Validates `"enroll"` flags correctly triggering the `enrollment` specific redirect.
*   Validates `"hipaa"` alerts accurately fire catching PHI data boundaries via the `hipaa` specific route.
*   Ensures that standard queries completely bypass this early intercept yielding `None`.

**4. `backend/tests/test_integration.py`**
Utilizes the `httpx.ASGITransport` handler asserting full stack functionality wrapping the `FastAPI` logic directly.
*   Validates HTTP 200 validations parsing complete responses accurately to end clients.
*   Checks HTTP 422 triggers explicitly across empty strings or payload spam.
*   Tests `/session/{id}/memory` state saves accurately reflecting dual user/assistant turns.
*   Confirms `/session/{id}` deletes gracefully resulting in a completely emptied state dict!
*   Validates that the extensive diagnostics structure deployed onto `/health` formats `retriever`, `memory`, and `provider` modes effectively.
