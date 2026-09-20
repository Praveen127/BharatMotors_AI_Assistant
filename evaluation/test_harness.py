"""
test_harness.py
Phase 9: loads data/evaluation/test_cases.json, runs each case through the
full agent (mode="full"), logs every interaction (PII-redacted) via
monitoring/langfuse_logger, and returns per-case + summary results for
docs/evaluation_report.md and scripts/run_evaluation.py.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agent.core_agent import SupportAgent
from agent.memory import MemoryStore
from monitoring.langfuse_logger import log_interaction
from evaluation import metrics

TEST_CASES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "data", "evaluation", "test_cases.json")


def run(agent: SupportAgent = None) -> dict:
    with open(TEST_CASES_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    agent = agent or SupportAgent(memory_store=MemoryStore())
    results = []

    for case in cases:
        result = agent.respond(case["input"], session_id=case["session_id"], mode="full")
        interaction_id = log_interaction(case["session_id"], case["input"],
                                          result.response, result.trace)

        results.append({
            "id": case["id"],
            "category": case["category"],
            "input": case["input"],
            "response": result.response,
            "interaction_id": interaction_id,
            "expected_verdict": case.get("expected_verdict"),
            "actual_verdict": result.trace.guardrail_verdict,
            "expect_tool": case.get("expect_tool"),
            "tools_called": result.trace.tools_called,
            "expect_grounded": case.get("expect_grounded"),
            "retrieval_confident": result.trace.retrieval_confident,
            "expect_keyword": case.get("expect_keyword"),
            "latency_ms": result.trace.latency_ms,
            "error": result.trace.error,
        })

    summary = metrics.summarize(results)
    return {"results": results, "summary": summary}


if __name__ == "__main__":
    out = run()
    print(json.dumps(out["summary"], indent=2))
    for r in out["results"]:
        status = "PASS" if (
            (r["expected_verdict"] is None or r["actual_verdict"] == r["expected_verdict"])
        ) else "FAIL"
        print(f"[{status}] {r['id']:6s} {r['category']:28s} verdict={r['actual_verdict']}")
