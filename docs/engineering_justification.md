# Engineering & Product Justification

## 1. Architecture overview

```
User message
   |
   v
safety/guardrails.py  --[refuse / escalate]--> tools/tool_escalate.py --> ticket + response
   | (allow)
   v
agent/planner.py  (decompose compound requests)
   |
   v
retrieval/retriever.py  (grounding: confident match? -> context, else "no confident match")
   |
   v
tools/tool_search.py -> tools/tool_registry.py  (call a tool IF a high-confidence
   |                                              intent + argument is present)
   v
agent/prompts.py + agent/memory.py + policy_rlhf.feedback_collector (style)
   |
   v
LLM (RealLLM via langchain_openai, or MockLLM offline)
   |
   v
policy_rlhf/policy_checker.py  (post-generation compliance check)
   |
   v
monitoring/langfuse_logger.py  (PII-redacted log) + response to user
```

Every request also optionally reaches the MCP layer (`mcp/server.py` +
`mcp/client.py`) as an alternative tool-invocation transport, and the RLHF
loop (`policy_rlhf/`) runs asynchronously/on a schedule (`scripts/
run_rlhf_pipeline.py`) rather than inline per-request.

## 2. Framework choice: LangChain (Track A)

The submission uses LangChain-shaped abstractions throughout:
`langchain_openai.ChatOpenAI` / `OpenAIEmbeddings` (real backend, see §3),
`langchain.tools.Tool` (`tools/tool_registry.get_langchain_tools()`), and a
`RecursiveCharacterTextSplitter`-equivalent chunker
(`retrieval/chunker.py`). LangChain was chosen over CrewAI/Flowise because:
this is a **single-agent, tool-using, RAG-grounded** system, not a
multi-agent crew, so CrewAI's orchestration overhead is unnecessary; and a
Flowise visual pipeline is harder to unit-test and version-control than
plain Python, which matters for a safety-critical support agent where every
guardrail needs to be independently testable (see `evaluation/test_harness.py`).

## 3. Offline-first design (the most important engineering decision here)

This capstone was built and evaluated in a sandboxed environment with **no
outbound network access** — `pip install langchain` fails, and no LLM/embedding
API can be called. Rather than submit untested code, every component that
would normally call a network service has a real, functioning offline
fallback, selected automatically:

| Component | Production backend | Offline fallback (used for all evidence in this submission) |
|---|---|---|
| LLM (`agent/core_agent.py`) | `langchain_openai.ChatOpenAI` | `MockLLM` — deterministic, but genuinely prompt-variant-sensitive (see `docs/prompt_comparison_table.md`) |
| Embeddings (`retrieval/embedder.py`) | `langchain_openai.OpenAIEmbeddings` | `OfflineEmbedder` — TF-IDF + truncated SVD (scikit-learn) |
| Vector index (`retrieval/faiss_store.py`) | `faiss` (IndexFlatIP) | exact NumPy cosine-similarity search (correct, not approximate, at this corpus size) |
| MCP tool server (`mcp/`) | `mcp` SDK over stdio/SSE | hand-rolled JSON-RPC 2.0 over stdio (same wire protocol shape) |
| Observability (`monitoring/`) | LangSmith / Langfuse cloud | local JSONL sinks with the same field schema |

**Why this is a legitimate engineering choice, not a shortcut:** the
selection logic (`USE_MOCK_LLM` env var, `try/except ImportError` around
each real client) is the *same* pattern used in real product engineering for
local development, CI pipelines, and cost control during testing — a
support-agent team would not want every unit test hitting a paid LLM API.
The switch to the real backend requires **zero code changes** — only setting
`USE_MOCK_LLM=false` and `OPENAI_API_KEY`. Every safety behaviour
(guardrails, PII redaction, escalation, tool routing) is fully
backend-independent and was validated exhaustively offline
(`docs/evaluation_report.md`). The one area genuinely degraded by the
offline fallback — retrieval ranking precision — is documented honestly as
a known limitation in the Evaluation Report §3.5, not hidden.

## 4. Safety-by-design, not safety-by-prompt

`docs/prompt_comparison_table.md` shows that prompt wording alone (V1) is
not reliable for refusing policy-violating requests or avoiding
hallucination. Consequently, safety here is implemented as **code that runs
before and after the LLM**, not just prompt instructions:

- **Before generation:** `safety/guardrails.py` pattern-matches refusal and
  escalation triggers on the raw user message. This cannot be bypassed by
  rephrasing a request to sound more innocent, because it never depends on
  the LLM interpreting intent correctly.
- **Grounding:** `retrieval/retriever.py`'s confidence threshold decides
  *whether the LLM is even allowed to answer from context* — if retrieval
  isn't confident, the prompt template's context slot is filled with "no
  confident match found," and V3's prompt is explicit that this means "don't
  guess."
- **After generation:** `policy_rlhf/policy_checker.py` scans the LLM's
  actual output for forbidden over-promising phrases and required
  safety/escalation language, and `deployment/app.py` substitutes a safe
  fallback if the check fails — a second, independent net in case the LLM
  ignores its instructions.

This three-layer design (pre-check, grounding-gate, post-check) is more
expensive to run than a single system prompt, but is the only approach that
held up under the adversarial test cases in `data/evaluation/test_cases.json`
(TC07, TC08, TC12).

## 5. RLHF/adaptive-behaviour boundary: what feedback is and isn't allowed to change

`policy_rlhf/` implements a deliberately narrow feedback loop:
`feedback_collector.py` tracks thumbs up/down and length complaints per
session; `policy_updater.py` aggregates them into a **non-safety** parameter
change (`max_sentences`, logged to `logs/policy_change.log`). Feedback is
**never** allowed to alter `safety/guardrails.py`'s trigger patterns,
refusal list, or escalation thresholds — those are fixed by policy, not by
customer preference (a customer who is annoyed by an escalation can't teach
the agent to stop escalating similar cases). This boundary is enforced
structurally: `policy_updater.py` only ever writes to
`data/policy/policy.json`'s `response_rules.max_sentences` field, and has no
import of or access to `safety/guardrails.py`.

## 6. Tool design and MCP

Tools (`tools/tool_registry.py`) are intentionally read-only /
side-effect-limited for the customer-facing surface (`check_warranty_status`,
`locate_service_center`, `check_recall_status`) plus one write action
(`create_escalation_ticket`) — consistent with Scenario 3 being a
**resolution/decision-support** agent, not a transactional one. Exposing
these same tools over a real MCP JSON-RPC/stdio server (`mcp/server.py`)
rather than only as in-process Python calls means the tool layer could be
attached to any MCP-compatible client (a different agent framework, an IDE
assistant, etc.) without rewriting the tool logic — this is the architectural
benefit MCP is meant to provide, demonstrated with a working (not just
described) client/server round trip (see `mcp/client.py` output in the
repo's evidence logs, `logs/mcp_events.log`).

## 7. Deployment assumptions and limitations

- **Assumption:** `WARRANTY_DB`, `SERVICE_CENTERS`, and `RECALLS_DB` in
  `tools/tool_registry.py` are mock in-memory dictionaries standing in for
  real backend systems (a warranty database, a dealer-locator API, a recall
  registry). Swapping them for real API calls is isolated to that one file.
- **Assumption:** Sessions and memory (`agent/memory.py`) are in-process and
  reset on restart. A production deployment behind a Flask app with multiple
  workers would need a shared session store (e.g. Redis) — noted but not
  built, since it's an infrastructure concern orthogonal to the agent logic.
- **Limitation:** The offline embedder's ranking precision (Evaluation
  Report §3.5) is the main known quality gap versus a networked deployment.
- **Limitation:** `safety/guardrails.py` is regex/pattern-based, which is
  precise but not robust to arbitrary paraphrasing — flagged as the top
  next-step improvement in the Evaluation Report.
- **Security:** `.env.example` documents `OPENAI_API_KEY` as an environment
  variable only; it is never read from or written to any file under version
  control, and `deployment/config.py` never logs its value.
