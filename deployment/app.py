"""
app.py
Phase 8 (Deployment Readiness): FastAPI backend wrapping SupportAgent.

Endpoints:
  GET  /health          -> liveness/readiness check (used by Docker/Cloud
                            Run/App Engine health checks, see app.yaml)
  POST /chat            -> ChatRequest -> ChatResponse (agent reply + trace)
  POST /feedback        -> FeedbackRequest -> updated feedback state
  GET  /tickets         -> open escalation tickets (support-staff view)

Run directly:      uvicorn deployment.app:app --host 0.0.0.0 --port 8080
Run via script:    python scripts/run_agent.py --serve
Interactive docs:  http://localhost:8080/docs  (FastAPI auto-generates this
                    from the Pydantic models below -- no extra work needed)

The Streamlit UI (deployment/streamlit_app.py) is a separate process that
talks to this API over HTTP via API_BASE_URL -- see docs/deployment_guide.md
for why the two are split into independent deployable services.
"""
import os
import sys
import time
import traceback
from typing import Optional, List, Dict, Any, Literal

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.core_agent import SupportAgent
from agent.memory import MemoryStore
from monitoring.langfuse_logger import log_interaction, _append, ERRORS_LOG
from policy_rlhf.feedback_collector import record_feedback
from policy_rlhf.policy_checker import check_response
from tools.tool_escalate import list_open_tickets
from deployment.config import Config


# --------------------------------------------------------------------------
# Request/response schemas (FastAPI auto-derives OpenAPI docs + validation
# from these -- e.g. a request missing "message" is rejected with a 422
# before it ever reaches the agent, unlike the manual `payload.get(...)`
# checks the earlier Flask version needed).
# --------------------------------------------------------------------------
class ChatRequest(BaseModel):
    session_id: str = Field(default="anonymous", max_length=128)
    message: str = Field(..., min_length=1, max_length=Config.MAX_REQUEST_CHARS)


class ChatResponse(BaseModel):
    interaction_id: str
    response: str
    guardrail_verdict: str
    tools_called: List[str]
    retrieved_sources: List[str]
    retrieval_confident: Optional[bool]
    escalation_ticket: Optional[Dict[str, Any]]
    latency_ms: float
    policy_check_passed: bool


class ChatErrorResponse(BaseModel):
    response: str
    error: str
    latency_ms: float


class FeedbackRequest(BaseModel):
    session_id: str = Field(default="anonymous", max_length=128)
    signal: Literal["thumbs_up", "thumbs_down", "too_long", "too_short"]


class HealthResponse(BaseModel):
    status: str
    mock_llm: bool


app = FastAPI(
    title="Bharat Motors Support Agent API",
    description="Backend for the Bharat Motors customer support agent (Scenario 3 capstone).",
    version="1.0.0",
)

# The Streamlit UI runs as a separate process/container and calls this API
# over HTTP (see deployment/streamlit_app.py), so cross-origin requests must
# be allowed. Locked to same-origin by default; set CORS_ALLOW_ORIGINS to a
# comma-separated list (or "*") in production if the UI is served from a
# different domain.
_cors_origins = os.environ.get("CORS_ALLOW_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _cors_origins == "*" else _cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

memory_store = MemoryStore()
agent = SupportAgent(memory_store=memory_store)

for w in Config.validate():
    print(f"[config warning] {w}")


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", mock_llm=Config.USE_MOCK_LLM)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    start = time.time()
    try:
        result = agent.respond(req.message, session_id=req.session_id, mode="full")

        # Post-generation policy compliance check (independent of guardrails)
        pc = check_response(
            result.response,
            is_escalation=result.trace.escalation_ticket is not None,
            is_safety_critical=(result.trace.guardrail_verdict == "escalate_critical"),
        )
        if not pc.passed:
            _append(ERRORS_LOG, {"session_id": req.session_id,
                                  "policy_violations": pc.violations,
                                  "response": result.response})

        interaction_id = log_interaction(req.session_id, req.message,
                                          result.response, result.trace)

        return ChatResponse(
            interaction_id=interaction_id,
            response=result.response,
            guardrail_verdict=result.trace.guardrail_verdict,
            tools_called=result.trace.tools_called,
            retrieved_sources=result.trace.retrieved_sources,
            retrieval_confident=result.trace.retrieval_confident,
            escalation_ticket=result.trace.escalation_ticket,
            latency_ms=round((time.time() - start) * 1000, 1),
            policy_check_passed=pc.passed,
        )

    except Exception as e:
        # Graceful failure handling (Phase 8 requirement) -- never a raw
        # 500 with a stack trace to the customer; the error is logged and a
        # calm fallback message is returned with a 200 so the UI can render
        # it like any other agent reply.
        err_text = str(e)
        _append(ERRORS_LOG, {"session_id": req.session_id, "error": err_text,
                              "traceback": traceback.format_exc()})
        return ChatResponse(
            interaction_id="error",
            response=("Sorry, something went wrong on my end. I've logged the "
                       "issue for our engineering team. Please try again, or I "
                       "can connect you with a specialist."),
            guardrail_verdict="error",
            tools_called=[],
            retrieved_sources=[],
            retrieval_confident=None,
            escalation_ticket=None,
            latency_ms=round((time.time() - start) * 1000, 1),
            policy_check_passed=False,
        )


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    updated = record_feedback(req.session_id, req.signal)
    return {"session_id": req.session_id, "feedback_state": updated}


@app.get("/tickets")
def tickets():
    return {"open_tickets": list_open_tickets()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("deployment.app:app", host=Config.HOST, port=Config.PORT, reload=False)
