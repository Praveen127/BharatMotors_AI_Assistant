# Bharat Motors Customer Support Agent
### Capstone Project — Design, Build, Evaluate an AI Agent
**Track:** A (Framework-Based, LangChain) · **Scenario:** 3 (Customer Support — AI Support Resolution Agent)

An AI customer-support agent for a fictional Indian passenger-vehicle
manufacturer ("Bharat Motors"), handling warranty questions, service
booking guidance, recall checks, and roadside-assistance FAQs — with
retrieval-grounded answers, tool calling, multi-turn memory, adaptive
response style, and hard safety guardrails for refusal and escalation.

**Start here for grading:** `docs/problem_framing.md`, `docs/demo_script.md`,
`docs/prompt_comparison_table.md`, `docs/evaluation_report.md`,
`docs/engineering_justification.md`.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env        # defaults to USE_MOCK_LLM=true (offline mode)

# 1. Build the knowledge base (Phase 4)
python scripts/ingest_documents.py
python scripts/build_faiss_index.py

# 2a. Backend API (FastAPI, via uvicorn)
python scripts/run_agent.py --serve          # or: uvicorn deployment.app:app --port 8080
# -> http://localhost:8080/docs for interactive API docs

# 2b. Web UI (Streamlit) -- run in a second terminal, with the API already up
streamlit run deployment/streamlit_app.py
# -> http://localhost:8501

# 2c. Or just talk to the agent from the CLI, no servers needed
python scripts/run_agent.py                 # interactive CLI
python scripts/run_agent.py --demo          # forced 5-turn demo (docs/demo_script.md evidence)

# 3. Evaluate
python scripts/run_evaluation.py            # Phase 9 test harness (12 cases)
python scripts/run_rlhf_pipeline.py         # Phase 7 adaptive-behaviour evidence

# 4. MCP tool server (optional, standalone; uses fastmcp if installed,
#    otherwise an offline fallback with the same interface)
python scripts/start_mcp_server.py
python mcp/client.py                        # example client round trip
```

## Web UI

`deployment/streamlit_app.py` is a Streamlit chat interface that talks to
the FastAPI backend over HTTP (`API_BASE_URL`, default
`http://localhost:8080`) — it does not import the agent directly, so the UI
and the agent backend are independently deployable services. The
conversation renders as a "service docket" rather than generic chat
bubbles: each agent reply carries a colored left border and a verdict badge
(ALLOW / ESCALATE · CRITICAL / ESCALATE · HIGH / ESCALATE · MEDIUM /
REFUSE) reflecting the actual `safety/guardrails.py` decision behind that
reply, plus a sidebar showing live guardrail/retrieval/escalation status,
open tickets, and feedback controls wired to `/feedback`.

## Deploying to the cloud

```bash
# Cloud Run (simplest) -- API, then UI pointed at it
gcloud run deploy bharat-motors-support-api --source . --allow-unauthenticated
gcloud run deploy bharat-motors-support-ui --source . --allow-unauthenticated \
  --command streamlit --args="run,deployment/streamlit_app.py,--server.port=8080,--server.address=0.0.0.0" \
  --set-env-vars API_BASE_URL=<api-url-from-previous-command>

# App Engine Flexible for the API (uses app.yaml + Dockerfile together)
gcloud app deploy app.yaml

# Any Docker host / VM -- both services in one command
docker compose up --build -d
```
Full instructions, secrets handling, and a known limitation around
multi-instance session state: **`docs/deployment_guide.md`**.

## Offline mode (important — read this first)

This project was built and fully evaluated in a **network-restricted
sandbox**. Every component that would normally call an external service
(LLM, embeddings, FAISS, MCP SDK, LangSmith/Langfuse) has a real, working
offline fallback that activates automatically via `USE_MOCK_LLM=true`
(the default). **All evidence in `docs/` and `logs/` was generated this
way.** To run against real Google Gemini/LangChain:

```bash
# in .env
USE_MOCK_LLM=false
GOOGLE_API_KEY=AIza...
```

No code changes are required to switch — see
`docs/engineering_justification.md` §3 for the full backend/fallback table
and rationale.

## Project structure

```
capstone_agent/
├── Dockerfile              # container image (Cloud Run / App Engine Flex / any Docker host)
├── docker-compose.yml       # local dev + simple VM deployment: api + ui services
├── app.yaml                 # Google App Engine Flexible config for the API (pairs with the Dockerfile)
├── docs/                  # the 5 required deliverables + generated evidence JSON
│   └── deployment_guide.md  # cloud deployment walkthrough (Cloud Run / App Engine / Docker)
├── knowledge/
│   ├── raw/                # source PDFs (product catalog, company policy, FAQ, escalation guidelines)
│   ├── processed/          # chunks.json (Phase 4 ingestion output)
│   └── faiss_index/        # vector index + fitted embedder state
├── skills/SKILL.md         # domain rules as a reusable skill definition
├── data/
│   ├── policy/policy.json         # non-safety response policy (RLHF-adjustable)
│   ├── rlhf/feedback_store.json   # per-session feedback signals
│   └── evaluation/test_cases.json # Phase 9 test set (12 cases)
├── mcp/                    # fastmcp server + client exposing agent tools (offline fallback included)
├── policy_rlhf/            # post-generation policy check, feedback collection, policy updates
├── agent/                  # core_agent.py (5 modes), prompts.py, memory.py, planner.py
├── retrieval/              # document loader, chunker, embedder, FAISS store, retriever
├── tools/                  # tool registry, routing/selection, escalation
├── safety/                 # guardrails (refuse/escalate), PII redaction
├── monitoring/             # PII-safe interaction logging, structured tracing
├── evaluation/             # test harness + metrics
├── logs/                   # interactions.log, mcp_events.log, policy_change.log, errors.log
├── deployment/              # FastAPI backend (app.py), Streamlit UI (streamlit_app.py), config
└── scripts/                # all runnable entrypoints
```

## The 9 capstone phases, mapped to this codebase

| Phase | Where |
|---|---|
| 1. Problem framing | `docs/problem_framing.md` |
| 2. Basic working agent | `agent/core_agent.py::baseline_respond()` (`mode="baseline"`) |
| 3. LLM + prompt engineering | `agent/prompts.py` (3 variants), `docs/prompt_comparison_table.md` |
| 4. Knowledge & retrieval | `retrieval/`, `knowledge/`, `scripts/ingest_documents.py`, `scripts/build_faiss_index.py` |
| 5. Tool usage | `tools/`, `mcp/` |
| 6. Planning, memory & context | `agent/planner.py`, `agent/memory.py` |
| 7. Adaptive behaviour | `policy_rlhf/`, `scripts/run_rlhf_pipeline.py`, `docs/adaptive_behaviour_evidence.json` |
| 8. Deployment readiness | `deployment/`, `monitoring/` |
| 9. Evaluation & engineering review | `evaluation/`, `scripts/run_evaluation.py`, `docs/evaluation_report.md` |

## Safety requirements (Scenario 3) — where each is enforced

- **Must refuse unsafe or policy-violating requests** → `safety/guardrails.py::REFUSAL_PATTERNS`
- **Must not fabricate policies** → `retrieval/retriever.py::retrieve_grounded()` (confidence gate) + `agent/prompts.py` V3
- **Must escalate sensitive or unresolved cases** → `safety/guardrails.py` (CRITICAL/HIGH/MEDIUM triggers) + `tools/tool_escalate.py`
- **Must not store personal data in logs** → `safety/pii_filter.py`, applied in `monitoring/langfuse_logger.py` (verified: 0 leaks across all logged interactions, see `docs/evaluation_report.md` §4)

## Known limitations
See `docs/evaluation_report.md` §3.5 (retrieval ranking precision with the
offline embedder) and `docs/engineering_justification.md` §7.
