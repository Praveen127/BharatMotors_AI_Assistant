"""
policy_updater.py
Aggregates collected feedback (policy_rlhf/feedback_collector.py) into
policy-level adjustments and appends a human-readable audit trail to
logs/policy_change.log. This is a deliberately conservative, rule-based
"RLHF-lite" loop appropriate for a support agent: it never silently changes
SAFETY rules (those in safety/guardrails.py are fixed and not touched by
feedback), it only tunes non-safety behaviour such as response verbosity —
this boundary is itself documented as a design decision in
docs/engineering_justification.md.
"""
import json
import os
from datetime import datetime, timezone
from policy_rlhf.feedback_collector import get_aggregate, _load as load_feedback

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "logs", "policy_change.log")
POLICY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "data", "policy", "policy.json")


def _log(line: str):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} {line}\n")


def run_policy_update_cycle() -> dict:
    """Reads aggregate feedback, decides whether any NON-SAFETY policy
    parameter should change, applies it, and logs the decision. Returns a
    summary dict (also used by scripts/run_rlhf_pipeline.py evidence)."""
    agg = get_aggregate()
    with open(POLICY_PATH, "r", encoding="utf-8") as f:
        policy = json.load(f)

    changes = []
    total_length_reports = agg["too_long_reports"] + agg["too_short_reports"]
    if total_length_reports >= 3 and agg["too_long_reports"] > agg["too_short_reports"]:
        if policy["response_rules"]["max_sentences"] > 3:
            old = policy["response_rules"]["max_sentences"]
            policy["response_rules"]["max_sentences"] = max(3, old - 1)
            changes.append(f"max_sentences {old} -> {policy['response_rules']['max_sentences']} "
                            f"(reason: {agg['too_long_reports']} too-long reports vs "
                            f"{agg['too_short_reports']} too-short reports)")

    if changes:
        policy["version"] += 1
        from datetime import datetime as dt
        policy["updated_at"] = dt.now(timezone.utc).isoformat()
        with open(POLICY_PATH, "w", encoding="utf-8") as f:
            json.dump(policy, f, indent=2)
        for c in changes:
            _log(f"POLICY_UPDATE v{policy['version']}: {c}")
    else:
        _log(f"POLICY_UPDATE: no change (aggregate={agg})")

    return {"changes": changes, "aggregate": agg, "policy_version": policy["version"]}
