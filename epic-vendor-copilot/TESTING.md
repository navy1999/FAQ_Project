# Testing Documentation

The test suite is structured in two layers: **pytest unit/integration tests** for backend correctness, and a **standalone end-to-end query test suite** for retrieval accuracy across the full FAQ corpus.

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
Validates the FAISS retrieval mechanics and Bloom filter boundary constraints.
- **Domain Miss Checking**: Verifies that queries with zero domain keywords bypass FAISS immediately, yielding `domain_miss=True`.
- **Confidence Thresholds**: Confirms that gibberish queries which pass the Bloom filter but lack semantic content yield an empty results array below the 0.55 confidence floor.
- **Top-K Ordering**: Ensures FAISS returns results sorted descending by similarity score.
- **Known Hits**: Checks that `"how do I enroll"` / `"what is vendor services"` correctly retrieve their canonical FAQ entries.
- **Multi-result Constraints**: Validates broad keyword topics map to up to 3 closest matches.

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

**`backend/tests/test_integration.py`**
Uses `httpx.ASGITransport` to test full-stack request/response flows against the live FastAPI app.
- HTTP 200 on valid queries with correctly structured response bodies.
- HTTP 422 on empty strings or malformed payloads.
- `/session/{id}/memory` correctly reflects dual user/assistant turns.
- `/session/{id}` DELETE results in a fully cleared state.
- `/health` returns `retriever`, `memory`, and `provider` fields in the expected format.

---

## Layer 2 — End-to-End Query Test Suite

`tests/run_query_tests.py` is a standalone 120+ case integration harness that tests the full retrieval pipeline (domain rules → FAISS → confidence gate) against every FAQ topic area, out-of-domain refusals, and ambiguous/clarification edge cases.

### Run it

```powershell
# Windows — from epic-vendor-copilot\
.\.venv\Scripts\python.exe tests\run_query_tests.py
```

```bash
# macOS / Linux
.venv/bin/python tests/run_query_tests.py
```

### What each result code means

| Code | Meaning | Action |
|---|---|---|
| `PASS` (green) | Correct outcome + correct FAQ id returned | ✅ Nothing |
| `WARN` (yellow) | Right outcome (ANSWER/REFUSE/CLARIFY), but wrong FAQ entry ranked first | Fix scoring / embedding boost |
| `FAIL` (red) | Entirely wrong outcome — refused an answerable query, answered an OOD query, etc. | Fix domain rules, retriever thresholds, or clarify logic |

### Test coverage by category

| Category | Cases | Expected outcome |
|---|---|---|
| Enroll / sign up / register | 15 | ANSWER → `vs-1075` |
| Cost / pricing / fees | 12 | ANSWER → `vs-1076` |
| Trial / cancel / refund | 7 | ANSWER → `vs-1078` |
| What is Vendor Services | 6 | ANSWER → `vs-1072` |
| Who uses it | 3 | ANSWER → `vs-1073` |
| Account setup timing | 5 | ANSWER → `vs-1278` |
| Login / password | 8 | ANSWER → `vs-1120/1121` |
| FHIR / APIs / standards | 11 | ANSWER → various |
| open.epic / Epic on FHIR | 4 | ANSWER → `vs-1085/1086/5800` |
| Learning / networking | 7 | ANSWER → `vs-1100` |
| Testing tools | 5 | ANSWER → `vs-1240` |
| Implementation | 3 | ANSWER → `vs-9797` |
| Design / tech support | 3 | ANSWER → `vs-1265` |
| Marketing / sales / Connection Hub | 5 | ANSWER → `vs-1112/3516` |
| Showroom tiers | 6 | ANSWER → `vs-5797/5798/5815` |
| Contact | 5 | ANSWER → `vs-1125/1126` |
| Analytics / ML / Caboodle | 5 | ANSWER → `vs-1097` |
| Clinical content | 2 | ANSWER → `vs-1096` |
| Out-of-domain (OOD) | 10 | REFUSE |
| Ambiguous / greeting / vague | 5 | CLARIFY |

### Adjusting the score threshold

The constant `SCORE_THRESHOLD = 0.30` at the top of `tests/run_query_tests.py` controls the minimum FAISS score required to classify a retriever result as an ANSWER. Adjust this to match your retriever's actual score distribution if needed.

### CI integration

The script exits with code `1` if any FAILs exist and `0` if all tests pass or only WARNs remain:

```yaml
# Example GitHub Actions step
- name: Run query test suite
  run: python tests/run_query_tests.py
```
