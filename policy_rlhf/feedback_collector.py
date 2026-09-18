"""
feedback_collector.py
Phase 7 (Adaptive Behaviour): stores lightweight feedback signals
(thumbs up/down, "too long"/"too short" comments) per session in
data/rlhf/feedback_store.json, and exposes get_response_style(session_id)
which core_agent.py consults to adjust future response style *within* and
*across* sessions for the same customer profile.

No PII is stored here -- sessions are keyed by an opaque session_id, and
feedback records contain only the feedback signal and a policy tag, never
the raw message text.
"""
import json
import os
from typing import Dict

STORE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "data", "rlhf", "feedback_store.json")


def _load() -> dict:
    if not os.path.exists(STORE_PATH):
        return {"sessions": {}, "aggregate": {"thumbs_up": 0, "thumbs_down": 0,
                                                 "too_long_reports": 0, "too_short_reports": 0}}
    with open(STORE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def record_feedback(session_id: str, signal: str) -> dict:
    """signal in {'thumbs_up','thumbs_down','too_long','too_short'}"""
    data = _load()
    sess = data["sessions"].setdefault(session_id, {
        "thumbs_up": 0, "thumbs_down": 0, "too_long_reports": 0,
        "too_short_reports": 0, "response_style": "normal",
    })
    key_map = {"thumbs_up": "thumbs_up", "thumbs_down": "thumbs_down",
               "too_long": "too_long_reports", "too_short": "too_short_reports"}
    field = key_map[signal]
    sess[field] += 1
    data["aggregate"][field] += 1

    # Adaptive rule: 2+ "too_long" reports -> switch this session to concise
    # style; 2+ "too_short" reports -> switch back to normal/detailed.
    if sess["too_long_reports"] >= 2:
        sess["response_style"] = "concise"
    elif sess["too_short_reports"] >= 2:
        sess["response_style"] = "normal"

    _save(data)
    return sess


def get_response_style(session_id: str) -> str:
    data = _load()
    sess = data["sessions"].get(session_id)
    return sess["response_style"] if sess else "normal"


def get_aggregate() -> Dict:
    return _load()["aggregate"]
