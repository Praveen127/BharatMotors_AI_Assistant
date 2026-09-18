"""
langfuse_logger.py
Phase 8 (Deployment Readiness): writes one PII-redacted JSON line per
interaction to logs/interactions.log, and errors to logs/errors.log.

Named after Langfuse (a popular open-source LLM observability platform)
because the schema below (trace-id, latency, tool calls, scores) mirrors
what you'd export from Langfuse. Real Langfuse export requires a network
call to a Langfuse project; this local JSONL sink is the offline-safe
equivalent used in this sandbox, and is the file scripts/run_evaluation.py
and evaluation/metrics.py read back for grading evidence. Swapping in the
real `langfuse` SDK client is a small, isolated change (see
docs/engineering_justification.md, "Observability").
"""
import json
import os
import uuid
from datetime import datetime, timezone
from safety.pii_filter import redact

INTERACTIONS_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "..", "logs", "interactions.log")
ERRORS_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "logs", "errors.log")


def _append(path: str, record: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def log_interaction(session_id: str, user_message: str, agent_response: str,
                     trace) -> str:
    """`trace` is an agent.core_agent.AgentTrace. Returns the generated
    interaction id."""
    interaction_id = uuid.uuid4().hex[:12]
    record = {
        "interaction_id": interaction_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "mode": trace.mode,
        "user_message": redact(user_message),
        "agent_response": redact(agent_response),
        "guardrail_verdict": trace.guardrail_verdict,
        "tools_called": trace.tools_called,
        "retrieved_sources": trace.retrieved_sources,
        "retrieval_confident": trace.retrieval_confident,
        "escalation_ticket_id": trace.escalation_ticket["ticket_id"] if trace.escalation_ticket else None,
        "prompt_variant": trace.prompt_variant,
        "latency_ms": round(trace.latency_ms, 1),
        "error": trace.error,
    }
    _append(INTERACTIONS_LOG, record)
    if trace.error:
        _append(ERRORS_LOG, {"interaction_id": interaction_id, "ts": record["ts"],
                              "session_id": session_id, "error": trace.error,
                              "latency_ms": record["latency_ms"]})
    return interaction_id


def read_interactions():
    if not os.path.exists(INTERACTIONS_LOG):
        return []
    with open(INTERACTIONS_LOG, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
