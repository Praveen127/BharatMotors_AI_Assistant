"""
scripts/run_evaluation.py
Runs evaluation/test_harness.py over data/evaluation/test_cases.json,
prints a pass/fail table + summary metrics, and writes the full results to
docs/evaluation_results.json (raw evidence backing docs/evaluation_report.md).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from evaluation import test_harness

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "evaluation_results.json")


def main():
    out = test_harness.run()
    results, summary = out["results"], out["summary"]

    print("=" * 78)
    print("EVALUATION RESULTS")
    print("=" * 78)
    n_pass, n_fail = 0, 0
    for r in results:
        ok = (r["expected_verdict"] is None or r["actual_verdict"] == r["expected_verdict"])
        if r.get("expect_tool") is not None:
            ok = ok and any(r["expect_tool"] in t for t in r["tools_called"])
        if r.get("expect_grounded") is not None:
            ok = ok and (r["retrieval_confident"] == r["expect_grounded"])
        if r.get("expect_keyword") is not None:
            ok = ok and (r["expect_keyword"].lower() in r["response"].lower())
        status = "PASS" if ok else "FAIL"
        n_pass += ok
        n_fail += (not ok)
        print(f"[{status}] {r['id']:6s} {r['category']:28s} "
              f"expected={str(r['expected_verdict']):18s} actual={r['actual_verdict']:22s} "
              f"latency={r['latency_ms']:.1f}ms")

    print("-" * 78)
    print(f"TOTAL: {n_pass} passed / {n_fail} failed  (n={len(results)})")
    print("SUMMARY METRICS:")
    print(json.dumps(summary, indent=2))

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"results": results, "summary": summary,
                    "n_pass": n_pass, "n_fail": n_fail}, f, indent=2)
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
