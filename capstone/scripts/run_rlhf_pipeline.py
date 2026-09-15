"""
scripts/run_rlhf_pipeline.py
Phase 7 (Adaptive Behaviour) evidence generator:
  1. Simulate a customer giving "too long" feedback on a verbose session.
  2. Show the agent's response getting more concise within the SAME session
     once the adaptive threshold is crossed (before/after proof).
  3. Run policy_rlhf.policy_updater to aggregate feedback into a (non-safety)
     policy change, logged to logs/policy_change.log.
"""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agent.core_agent import SupportAgent
from agent.memory import MemoryStore
from policy_rlhf.feedback_collector import record_feedback, get_response_style
from policy_rlhf.policy_updater import run_policy_update_cycle
from monitoring.langfuse_logger import log_interaction

SESSION = "rlhf_demo_session"


def main():
    memory_store = MemoryStore()
    agent = SupportAgent(memory_store=memory_store)

    print("=== BEFORE feedback (default 'normal' style) ===")
    before = agent.respond("What is covered under my car's warranty?",
                             session_id=SESSION, mode="full")
    log_interaction(SESSION, "What is covered under my car's warranty?", before.response, before.trace)
    print("Agent:", before.response)
    print("style:", get_response_style(SESSION))

    print("\n=== Customer reports the response is too long (x2) ===")
    record_feedback(SESSION, "too_long")
    state = record_feedback(SESSION, "too_long")
    print("feedback state:", state)

    print("\n=== AFTER feedback (adapted style) ===")
    after = agent.respond("What is covered under my car's warranty?",
                            session_id=SESSION, mode="full")
    log_interaction(SESSION, "What is covered under my car's warranty?", after.response, after.trace)
    print("Agent:", after.response)
    print("style:", get_response_style(SESSION))

    print("\n=== Running policy update cycle (aggregate feedback -> policy.json) ===")
    result = run_policy_update_cycle()
    print(json.dumps(result, indent=2))

    evidence = {
        "before_response": before.response,
        "before_style": "normal",
        "after_response": after.response,
        "after_style": get_response_style(SESSION),
        "policy_update_result": result,
        "explanation": (
            "After 2 'too_long' feedback signals in the same session, "
            "core_agent.py's mode='full' path calls "
            "policy_rlhf.feedback_collector.get_response_style(session_id), "
            "which returns 'concise' once too_long_reports >= 2. This is "
            "passed to MockLLM.generate(..., style='concise'), which "
            "truncates/shortens the answer. Separately, "
            "policy_updater.run_policy_update_cycle() aggregates feedback "
            "across ALL sessions and, once too-long reports dominate, "
            "permanently lowers the global max_sentences policy parameter "
            "in data/policy/policy.json -- a slower, more conservative "
            "adaptation than the per-session style switch."
        ),
    }
    out_path = os.path.join(os.path.dirname(__file__), "..", "docs", "adaptive_behaviour_evidence.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)
    print(f"\nSaved before/after adaptive-behaviour evidence to {out_path}")


if __name__ == "__main__":
    main()
