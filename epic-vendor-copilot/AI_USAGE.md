# AI Usage Document

## What AI Assisted With
AI was used to structure and generate boilerplate code for the project, including dependency management (`requirements.txt`, `package.json`), initial scaffolding of the FastAPI server, building the React user interface, and implementing the `pybloom_live` domain guard and FAISS retrieval setup. The AI also generated our test suites using `pytest`.

## What Was Candidate-Authored
The candidate actively directed the agent workflows, managed state preservation constraints across sub-agents, fixed dependency resolution (e.g. `faiss-cpu` incompatibility, `pytest-asyncio` versions), refined the Bloom filter thresholds to accurately meet the testing spec requirements, and performed end-to-end integration verifications.

## Endpoint Discovery
FAQ content is loaded dynamically by FaqViewModel.js via GET /FAQ/GetAllFaqItemDocuments. Discovered by reading the JS bundle. No auth required when correct XHR headers are sent.

## Seed Data Sourcing
Instead of hardcoding a massive block of FAQ entries or manually copying them from the website, we created a single `scrape_faq.py` capable of reliably fetching from the aforementioned endpoint. The seed data is persisted to `SEED_DATA/epic_vendor_faq.json` enabling the offline capability and standardizing the schema without manual transcription faults.
