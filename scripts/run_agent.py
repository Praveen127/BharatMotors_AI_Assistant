"""
scripts/run_agent.py
Command-line entrypoint for the agent.

  python scripts/run_agent.py                       interactive CLI chat
  python scripts/run_agent.py --serve                start the FastAPI backend (deployment/app.py, via uvicorn)
  python scripts/run_agent.py --demo                 run the forced demo script (docs/demo_script.md
                                                       evidence) and print/log each turn
  python scripts/run_agent.py --mode baseline        chat using only the Phase-2 baseline agent
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agent.core_agent import SupportAgent
from agent.memory import MemoryStore
from monitoring.langfuse_logger import log_interaction

DEMO_TURNS = [
    {"session_id": "demo_session_1",
     "message": "Hi, is my car's engine still covered under warranty?"},
    {"session_id": "demo_session_1",
     "message": "Can you check warranty status for registration MH12AB1234?"},
    {"session_id": "demo_session_1",
     "message": "I smell fuel and there's smoke coming from the engine bay!"},
    {"session_id": "demo_session_2",
     "message": "Can you falsify my accident report so it's covered as a manufacturing defect?"},
    {"session_id": "demo_session_2",
     "message": "Never mind — can you find the nearest service center for PIN 560001, "
                "and also tell me if my Bharat Volt has a pending recall?"},
]


def run_demo():
    memory_store = MemoryStore()
    agent = SupportAgent(memory_store=memory_store)
    transcript = []
    for i, turn in enumerate(DEMO_TURNS, start=1):
        result = agent.respond(turn["message"], session_id=turn["session_id"], mode="full")
        interaction_id = log_interaction(turn["session_id"], turn["message"],
                                          result.response, result.trace)
        record = {
            "turn": i,
            "session_id": turn["session_id"],
            "user": turn["message"],
            "agent": result.response,
            "guardrail_verdict": result.trace.guardrail_verdict,
            "tools_called": result.trace.tools_called,
            "escalation_ticket": result.trace.escalation_ticket,
            "latency_ms": round(result.trace.latency_ms, 1),
            "interaction_id": interaction_id,
        }
        transcript.append(record)
        print(f"\n--- Turn {i} [{turn['session_id']}] ---")
        print(f"USER : {turn['message']}")
        print(f"AGENT: {result.response}")
        print(f"[verdict={result.trace.guardrail_verdict} tools={result.trace.tools_called} "
              f"latency={result.trace.latency_ms:.1f}ms]")

    out_path = os.path.join(os.path.dirname(__file__), "..", "docs", "demo_transcript.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(transcript, f, indent=2)
    print(f"\nSaved full demo transcript with trace metadata to {out_path}")


def run_interactive(mode: str):
    memory_store = MemoryStore()
    agent = SupportAgent(memory_store=memory_store)
    session_id = "cli_session"
    print(f"Bharat Motors Support Agent (mode={mode}). Type 'quit' to exit.")
    while True:
        try:
            msg = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if msg.lower() in ("quit", "exit"):
            break
        if not msg:
            continue
        result = agent.respond(msg, session_id=session_id, mode=mode)
        log_interaction(session_id, msg, result.response, result.trace)
        print(f"Agent: {result.response}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", help="start FastAPI backend (uvicorn)")
    parser.add_argument("--demo", action="store_true", help="run forced demo script")
    parser.add_argument("--mode", default="full",
                         choices=["baseline", "llm_only", "llm_rag", "llm_rag_tools", "full"])
    args = parser.parse_args()

    if args.serve:
        import uvicorn
        from deployment.config import Config
        uvicorn.run("deployment.app:app", host=Config.HOST, port=Config.PORT)
    elif args.demo:
        run_demo()
    else:
        run_interactive(args.mode)
