"""
core_agent.py
The single agent class used across every phase of the capstone. Rather than
throwing away each phase's code, `SupportAgent.respond(..., mode=...)` can
run in five modes that map directly onto the capstone phases, so
docs/demo_script.md and docs/evaluation_report.md can show the exact same
class evolving:

    mode="baseline"     Phase 2 - rules/templates only, no LLM.
    mode="llm_only"     Phase 3 - LLM with a prompt, no retrieval/tools.
    mode="llm_rag"      Phase 4 - LLM + retrieval grounding.
    mode="llm_rag_tools" Phase 5 - + tool calling.
    mode="full"         Phase 6/7 - + planning, memory, adaptive behaviour,
                         and safety guardrails. This is the production mode
                         used by deployment/app.py.

LLM BACKEND: real calls go through langchain_google_genai.ChatGoogleGenerativeAI
(Google Gemini) when USE_MOCK_LLM=false and a GOOGLE_API_KEY + network are
available. Otherwise a deterministic MockLLM is used so the whole pipeline
(including grounding and safety behaviour, which do NOT depend on the LLM)
is fully testable offline. See docs/engineering_justification.md.
"""
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from agent.prompts import PROMPT_VARIANTS, DEFAULT_VARIANT
from agent.memory import MemoryStore, SessionMemory
from agent.planner import decompose
from retrieval.retriever import Retriever, RetrievedChunk
from tools.tool_search import route as route_tool
from tools import tool_registry
from tools.tool_escalate import escalate_from_guardrail
from safety.guardrails import evaluate as guardrail_evaluate, GuardrailVerdict
from safety.pii_filter import redact
from policy_rlhf.feedback_collector import get_response_style


# --------------------------------------------------------------------------
# LLM backends
# --------------------------------------------------------------------------
class MockLLM:
    """Deterministic offline LLM stand-in. It does NOT call any network
    service. It simulates response *quality* differences between the three
    prompt variants (see agent/prompts.py) so the prompt-comparison exercise
    in Phase 3 produces genuinely different, inspectable outputs rather than
    identical canned text -- this is what docs/prompt_comparison_table.md
    is built from."""

    def generate(self, prompt: str, variant: str, question: str,
                 context: str = "", style: str = "normal") -> str:
        has_context = bool(context.strip()) and "no confident" not in context.lower()

        if variant == "v1_minimal":
            # No context, no safety rules -> prone to generic/confident-sounding
            # answers even without grounding (this is the "hallucination risk"
            # failure mode Phase 3/9 is meant to surface).
            return (f"Sure! Regarding '{question.strip().rstrip('?')}': in most cases "
                     "this is covered under our standard policy, and pricing is generally "
                     "affordable. Let me know if you need anything else!")

        if variant == "v2_context_added":
            if has_context:
                snippet = context.strip().split("\n")[0][:180]
                return (f"Based on our records: {snippet}. Let me know if you have any "
                         "other questions!")
            return "I'm not sure about that, sorry."

        # v3_safety_grounded (default)
        if not has_context:
            return ("I don't have confirmed information on that in our policy records, "
                     "so I don't want to guess. I can escalate this to a specialist who "
                     "can check for you — would that be okay?")
        snippet = context.strip().split("\n")[0]
        snippet = snippet[:220]
        base = f"Here's what I can confirm from our policy records: {snippet}"
        if style == "concise":
            return base[:160].rstrip() + ("..." if len(base) > 160 else "")
        return base + " Let me know if you'd like me to go into more detail or escalate this."


class RealLLM:
    """Wraps langchain_google_genai.ChatGoogleGenerativeAI (Google Gemini)
    for production use."""

    def __init__(self, model: str = "gemini-2.5-flash", temperature: float = 0.2):
        from langchain_google_genai import ChatGoogleGenerativeAI
        # api_key is read from GOOGLE_API_KEY (or GEMINI_API_KEY) via
        # deployment/config.py's Config.GOOGLE_API_KEY -- passed explicitly
        # rather than relying on the SDK's own env lookup so the same
        # config path (.env / .env.example) governs both.
        from deployment.config import Config
        self._llm = ChatGoogleGenerativeAI(
            model=model, temperature=temperature,
            google_api_key=Config.GOOGLE_API_KEY or None,
        )

    def generate(self, prompt: str, variant: str, question: str,
                 context: str = "", style: str = "normal") -> str:
        resp = self._llm.invoke(prompt)
        return resp.content if hasattr(resp, "content") else str(resp)


def get_llm():
    use_mock = os.environ.get("USE_MOCK_LLM", "true").lower() == "true"
    if not use_mock:
        try:
            from deployment.config import Config
            return RealLLM(model=Config.LLM_MODEL, temperature=Config.LLM_TEMPERATURE)
        except Exception as e:
            print(f"[core_agent] Falling back to MockLLM: {e}")
    return MockLLM()


# --------------------------------------------------------------------------
# Baseline (Phase 2) — deliberately simple rule/template agent
# --------------------------------------------------------------------------
BASELINE_RULES = [
    (re.compile(r"\bwarranty\b", re.I),
     "Our standard warranty is 2 years or 40,000 km, whichever comes first."),
    (re.compile(r"\bservice\b.*\bbook", re.I),
     "You can book a service through our app, website, or by calling your service center."),
    (re.compile(r"\brecall\b", re.I),
     "Please check our website for recall information."),
    (re.compile(r"\bhi\b|\bhello\b", re.I), "Hello! How can I help you today?"),
]
BASELINE_FALLBACK = "Sorry, I don't understand. Please contact our helpline."


def baseline_respond(user_message: str) -> str:
    for pattern, answer in BASELINE_RULES:
        if pattern.search(user_message):
            return answer
    return BASELINE_FALLBACK


# --------------------------------------------------------------------------
# Trace / result objects
# --------------------------------------------------------------------------
@dataclass
class AgentTrace:
    mode: str
    guardrail_verdict: str
    tools_called: List[str] = field(default_factory=list)
    retrieved_sources: List[str] = field(default_factory=list)
    retrieval_confident: Optional[bool] = None
    escalation_ticket: Optional[dict] = None
    prompt_variant: Optional[str] = None
    latency_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class AgentResult:
    response: str
    trace: AgentTrace


# --------------------------------------------------------------------------
# Main agent
# --------------------------------------------------------------------------
class SupportAgent:
    def __init__(self, memory_store: Optional[MemoryStore] = None):
        self.memory_store = memory_store or MemoryStore()
        self._llm = get_llm()
        self._retriever = None  # lazy-loaded (requires built index)

    def _get_retriever(self) -> Retriever:
        if self._retriever is None:
            self._retriever = Retriever()
        return self._retriever

    # ---- public entrypoint -------------------------------------------
    def respond(self, user_message: str, session_id: str = "default",
                mode: str = "full", prompt_variant: str = DEFAULT_VARIANT) -> AgentResult:
        start = time.time()
        trace = AgentTrace(mode=mode, guardrail_verdict="not_evaluated")

        try:
            if mode == "baseline":
                response = baseline_respond(user_message)
                trace.guardrail_verdict = "n/a (baseline has no guardrails — this is Phase 2's documented limitation)"
                trace.latency_ms = (time.time() - start) * 1000
                return AgentResult(response=response, trace=trace)

            mem = self.memory_store.get(session_id)

            # --- Safety guardrails run BEFORE generation, on every mode
            #     except baseline (baseline demonstrates the pre-safety state)
            # Only track "repeated complaint" for messages that actually
            # read as a complaint/problem report -- plain repeated
            # informational questions (e.g. asking a FAQ twice) must NOT
            # be treated as an escalation signal. (Caught during Phase 9
            # evaluation: an early version flagged any repeated question,
            # which incorrectly escalated a customer re-asking a routine
            # warranty FAQ. See docs/evaluation_report.md.)
            complaint_cue = re.search(
                r"\b(not work|not cooling|not fixed|issue|problem|broken|"
                r"doesn'?t work|isn'?t work|noise|leak|complain)\b",
                user_message, re.I)
            repeated = False
            if mode == "full" and complaint_cue:
                topic_key = re.sub(r"[^a-z ]", "", user_message.lower())
                topic_key = " ".join(w for w in topic_key.split()
                                       if w not in {"the", "my", "is", "a", "to", "and", "of"})[:40]
                repeated = mem.note_complaint(topic_key)
            gr = guardrail_evaluate(user_message, repeated_complaint=repeated)
            trace.guardrail_verdict = gr.verdict.value

            if gr.verdict == GuardrailVerdict.REFUSE:
                mem.add_turn("user", user_message)
                mem.add_turn("agent", gr.message)
                trace.latency_ms = (time.time() - start) * 1000
                return AgentResult(response=gr.message, trace=trace)

            if gr.verdict in (GuardrailVerdict.ESCALATE_CRITICAL,
                               GuardrailVerdict.ESCALATE_HIGH,
                               GuardrailVerdict.ESCALATE_MEDIUM):
                ticket = escalate_from_guardrail(gr, user_message)
                trace.escalation_ticket = ticket
                full_response = f"{gr.message} Your ticket ID is {ticket['ticket_id']} (SLA: {ticket['sla']})."
                mem.add_turn("user", user_message)
                mem.add_turn("agent", full_response)
                trace.latency_ms = (time.time() - start) * 1000
                return AgentResult(response=full_response, trace=trace)

            # --- mode == llm_only: no retrieval/tools -------------------
            if mode == "llm_only":
                prompt_template = PROMPT_VARIANTS[prompt_variant]
                prompt = prompt_template.format(question=user_message,
                                                  context="", memory="") \
                    if "{context}" in prompt_template else prompt_template.format(question=user_message)
                response = self._llm.generate(prompt, prompt_variant, user_message, context="")
                trace.prompt_variant = prompt_variant
                trace.latency_ms = (time.time() - start) * 1000
                return AgentResult(response=response, trace=trace)

            # --- Planning: decompose compound requests (Phase 6) --------
            subtasks = decompose(user_message) if mode == "full" else [type("T", (), {"text": user_message})()]

            answers = []
            for st in subtasks:
                sub_text = st.text
                context_str = ""

                if mode in ("llm_rag", "llm_rag_tools", "full"):
                    retriever = self._get_retriever()
                    chunks, confident = retriever.retrieve_grounded(sub_text, k=3)
                    trace.retrieval_confident = confident
                    trace.retrieved_sources.extend([c.source for c in chunks])
                    if confident:
                        context_str = "\n---\n".join(f"[{c.source}] {c.text}" for c in chunks)
                    else:
                        context_str = "(no confident match found in knowledge base)"

                if mode in ("llm_rag_tools", "full"):
                    plan = route_tool(sub_text)
                    if plan.tool_name and plan.confidence == "high":
                        tool_fn = next(t["func"] for t in tool_registry.TOOL_SPECS
                                        if t["name"] == plan.tool_name)
                        try:
                            tool_result = tool_fn(**plan.args)
                            trace.tools_called.append(plan.tool_name)
                            context_str = f"[tool:{plan.tool_name}] {tool_result}\n" + context_str
                        except Exception as e:
                            trace.tools_called.append(f"{plan.tool_name} (FAILED: {e})")
                    elif plan.tool_name and plan.confidence == "low":
                        # Demonstrates a correctly-avoided incorrect tool call:
                        # intent detected but required argument missing, so the
                        # agent does NOT call the tool with a guessed value.
                        trace.tools_called.append(f"{plan.tool_name} (SKIPPED: {plan.note})")

                prompt_variant_used = prompt_variant
                style = get_response_style(session_id) if mode == "full" else "normal"
                memory_text = mem.as_prompt_context() if mode == "full" else ""

                prompt_template = PROMPT_VARIANTS[prompt_variant_used]
                fmt_kwargs = {"question": sub_text}
                if "{context}" in prompt_template:
                    fmt_kwargs["context"] = context_str
                if "{memory}" in prompt_template:
                    fmt_kwargs["memory"] = memory_text
                prompt = prompt_template.format(**fmt_kwargs)

                answer = self._llm.generate(prompt, prompt_variant_used, sub_text,
                                              context=context_str, style=style)
                answers.append(answer)

            response = "\n".join(answers)
            trace.prompt_variant = prompt_variant

            if mode == "full":
                mem.add_turn("user", user_message)
                mem.add_turn("agent", response)
                # opportunistically remember a vehicle registration number if
                # the customer supplied one, so later turns don't need to ask again
                from safety.pii_filter import PATTERNS
                for label, pattern in PATTERNS:
                    if label == "VEHICLE_REG":
                        m = pattern.search(user_message)
                        if m:
                            mem.set_fact("vehicle_reg", m.group(0))

            trace.latency_ms = (time.time() - start) * 1000
            return AgentResult(response=response, trace=trace)

        except Exception as e:
            trace.error = str(e)
            trace.latency_ms = (time.time() - start) * 1000
            return AgentResult(
                response=("Sorry, something went wrong on my end. I've logged the "
                           "issue — please try again, or I can connect you with a "
                           "specialist."),
                trace=trace,
            )
