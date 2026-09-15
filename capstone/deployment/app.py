"""
app.py
Phase 8 (Deployment Readiness): Flask HTTP wrapper around SupportAgent.
Endpoints:
  GET  /health         -> liveness check
  POST /chat           -> {"session_id": "...", "message": "..."} -> agent response + trace
  POST /feedback        -> {"session_id": "...", "signal": "thumbs_up|thumbs_down|too_long|too_short"}
  GET  /tickets          -> list open escalation tickets (support-staff view)

Run:  python deployment/app.py
      (or: python scripts/run_agent.py --serve)
"""
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from flask import Flask, request, jsonify
from agent.core_agent import SupportAgent
from agent.memory import MemoryStore
from monitoring.langfuse_logger import log_interaction, _append, ERRORS_LOG
from policy_rlhf.feedback_collector import record_feedback
from policy_rlhf.policy_checker import check_response
from tools.tool_escalate import list_open_tickets
from deployment.config import Config

app = Flask(__name__)
memory_store = MemoryStore()
agent = SupportAgent(memory_store=memory_store)

for w in Config.validate():
    print(f"[config warning] {w}")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "mock_llm": Config.USE_MOCK_LLM})


@app.route("/chat", methods=["POST"])
def chat():
    start = time.time()
    try:
        payload = request.get_json(force=True) or {}
        session_id = payload.get("session_id", "anonymous")
        message = (payload.get("message") or "").strip()

        if not message:
            return jsonify({"error": "message is required"}), 400
        if len(message) > Config.MAX_REQUEST_CHARS:
            return jsonify({"error": f"message too long (max {Config.MAX_REQUEST_CHARS} chars)"}), 400

        result = agent.respond(message, session_id=session_id, mode="full")

        # Post-generation policy compliance check (independent of guardrails)
        pc = check_response(
            result.response,
            is_escalation=result.trace.escalation_ticket is not None,
            is_safety_critical=(result.trace.guardrail_verdict == "escalate_critical"),
        )
        if not pc.passed:
            _append(ERRORS_LOG, {"session_id": session_id, "policy_violations": pc.violations,
                                  "response": result.response})

        interaction_id = log_interaction(session_id, message, result.response, result.trace)

        return jsonify({
            "interaction_id": interaction_id,
            "response": result.response,
            "guardrail_verdict": result.trace.guardrail_verdict,
            "tools_called": result.trace.tools_called,
            "escalation_ticket": result.trace.escalation_ticket,
            "latency_ms": round((time.time() - start) * 1000, 1),
            "policy_check_passed": pc.passed,
        })

    except Exception as e:
        # Graceful failure handling (Phase 8 requirement)
        err_text = str(e)
        _append(ERRORS_LOG, {"session_id": payload.get("session_id", "unknown") if 'payload' in dir() else "unknown",
                              "error": err_text, "traceback": traceback.format_exc()})
        return jsonify({
            "response": ("Sorry, something went wrong on my end. I've logged the issue "
                         "for our engineering team. Please try again, or I can connect "
                         "you with a specialist."),
            "error": "internal_error",
            "latency_ms": round((time.time() - start) * 1000, 1),
        }), 500


@app.route("/feedback", methods=["POST"])
def feedback():
    payload = request.get_json(force=True) or {}
    session_id = payload.get("session_id", "anonymous")
    signal = payload.get("signal")
    if signal not in ("thumbs_up", "thumbs_down", "too_long", "too_short"):
        return jsonify({"error": "invalid signal"}), 400
    updated = record_feedback(session_id, signal)
    return jsonify({"session_id": session_id, "feedback_state": updated})


@app.route("/tickets", methods=["GET"])
def tickets():
    return jsonify({"open_tickets": list_open_tickets()})


if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=False)
