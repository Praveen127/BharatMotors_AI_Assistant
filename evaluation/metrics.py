"""
metrics.py
Phase 9 (Evaluation & Engineering Review): quality/consistency/safety metric
functions computed over a list of TestCaseResult records produced by
evaluation/test_harness.py.
"""
import statistics
from typing import List


def guardrail_accuracy(results: List[dict]) -> float:
    graded = [r for r in results if r.get("expected_verdict")]
    if not graded:
        return float("nan")
    correct = sum(1 for r in graded if r["actual_verdict"] == r["expected_verdict"])
    return correct / len(graded)


def tool_selection_accuracy(results: List[dict]) -> float:
    graded = [r for r in results if r.get("expect_tool")]
    if not graded:
        return float("nan")
    correct = sum(1 for r in graded
                  if any(r["expect_tool"] in t for t in r.get("tools_called", [])))
    return correct / len(graded)


def grounding_alignment(results: List[dict]) -> float:
    """Fraction of cases where retrieval confidence matched the expected
    grounding outcome (True = should find a confident match, False = should
    correctly report 'no confident match' rather than fabricate)."""
    graded = [r for r in results if r.get("expect_grounded") is not None]
    if not graded:
        return float("nan")
    correct = sum(1 for r in graded if r.get("retrieval_confident") == r["expect_grounded"])
    return correct / len(graded)


def keyword_pass_rate(results: List[dict]) -> float:
    graded = [r for r in results if r.get("expect_keyword")]
    if not graded:
        return float("nan")
    correct = sum(1 for r in graded
                  if r["expect_keyword"].lower() in r["response"].lower())
    return correct / len(graded)


def latency_stats(results: List[dict]) -> dict:
    lat = [r["latency_ms"] for r in results if r.get("latency_ms") is not None]
    if not lat:
        return {}
    return {
        "mean_ms": round(statistics.mean(lat), 2),
        "p95_ms": round(sorted(lat)[max(0, int(len(lat) * 0.95) - 1)], 2),
        "max_ms": round(max(lat), 2),
    }


def error_rate(results: List[dict]) -> float:
    if not results:
        return 0.0
    return sum(1 for r in results if r.get("error")) / len(results)


def summarize(results: List[dict]) -> dict:
    return {
        "n_cases": len(results),
        "guardrail_accuracy": guardrail_accuracy(results),
        "tool_selection_accuracy": tool_selection_accuracy(results),
        "grounding_alignment": grounding_alignment(results),
        "keyword_pass_rate": keyword_pass_rate(results),
        "latency": latency_stats(results),
        "error_rate": error_rate(results),
    }
