"""
streamlit_app.py
Streamlit UI for the Bharat Motors Support Agent. Talks to the FastAPI
backend (deployment/app.py) over HTTP via API_BASE_URL -- it does NOT
import agent.core_agent directly, so the UI and the agent backend are
independently deployable/scalable services (see docs/deployment_guide.md).

Run locally (with the API already running on :8080):
    streamlit run deployment/streamlit_app.py

Design: the conversation is presented as a service "docket" rather than
generic rounded chat bubbles -- each agent reply carries a colored left
border reflecting its actual guardrail verdict (green=allow,
amber=escalate, red=critical, stone=refuse), echoing a dashboard telltale
light rather than a decorative accent. See the CSS block below for the
full token set.
"""
import os
import uuid
import requests
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8080")
REQUEST_TIMEOUT_S = float(os.environ.get("REQUEST_TIMEOUT_S", "20"))

VERDICT_COLOR = {
    "allow": "#4C9A6A",
    "escalate_critical": "#C1443C",
    "escalate_high": "#E8A33D",
    "escalate_medium": "#E8A33D",
    "refuse": "#7A756A",
    "error": "#C1443C",
}
VERDICT_LABEL = {
    "allow": "ALLOW",
    "escalate_critical": "ESCALATE · CRITICAL",
    "escalate_high": "ESCALATE · HIGH",
    "escalate_medium": "ESCALATE · MEDIUM",
    "refuse": "REFUSE",
    "error": "ERROR",
}

st.set_page_config(page_title="Bharat Motors Support", page_icon="🛠️", layout="centered")

# --------------------------------------------------------------------------
# Design tokens (matches docs/engineering_justification.md's design intent
# for the project: a dashboard/instrument-cluster identity, not a generic
# SaaS chat kit -- warm charcoal fascia, amber needle accent, and verdict
# colors reused meaningfully as telltale-light colors, not decoration).
# --------------------------------------------------------------------------
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #211F1B; --panel: #2B2820; --panel-raised: #332F27;
  --hairline: #4A4438; --text: #EFEAE0; --text-muted: #A79E8E;
  --amber: #E8A33D; --green: #4C9A6A; --red: #C1443C; --stone: #7A756A;
}
.stApp { background: var(--bg); color: var(--text); font-family: 'IBM Plex Sans', sans-serif; }
.brand-title { font-family: 'Bebas Neue', sans-serif; font-size: 2.1rem; letter-spacing: .04em;
  color: var(--amber); margin-bottom: -0.6rem; }
.brand-sub { color: var(--text-muted); font-size: .9rem; margin-bottom: 1rem; }
.docket-entry { background: var(--panel); border: 1px solid var(--hairline); border-radius: 4px;
  padding: .7rem .9rem; margin-bottom: .5rem; }
.docket-entry.user { background: var(--panel-raised); margin-left: 1.5rem; }
.docket-entry.agent { border-left: 4px solid var(--stone); margin-right: 1.5rem; }
.verdict-badge { font-family: 'Bebas Neue', sans-serif; letter-spacing: .05em; font-size: .78rem;
  padding: .1rem .5rem; border-radius: 3px; display: inline-block; margin-bottom: .3rem; color: #1a1a17; }
.meta-line { color: var(--text-muted); font-size: .78rem; margin-top: .3rem; }
.ticket-chip { display: inline-block; background: var(--panel-raised); border: 1px solid var(--amber);
  color: var(--amber); font-family: 'Bebas Neue', sans-serif; letter-spacing: .04em;
  padding: .15rem .6rem; border-radius: 3px; margin: .15rem .3rem .15rem 0; font-size: .85rem; }
section[data-testid="stSidebar"] { background: var(--panel); border-right: 1px solid var(--hairline); }
</style>
""", unsafe_allow_html=True)


def call_api(method: str, path: str, **kwargs):
    try:
        resp = requests.request(method, f"{API_BASE_URL}{path}", timeout=REQUEST_TIMEOUT_S, **kwargs)
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = "st_" + uuid.uuid4().hex[:10]
if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {role, text, trace}

# --------------------------------------------------------------------------
# Sidebar: instrument strip (backend status, telltales, open tickets)
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="brand-title">BHARAT MOTORS</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-sub">Support Assistant — control panel</div>', unsafe_allow_html=True)

    health, err = call_api("GET", "/health")
    if err:
        st.error(f"Backend unreachable at {API_BASE_URL}\n\n{err}")
        st.caption("Start the API with: `uvicorn deployment.app:app --port 8080`")
    else:
        mode = "MOCK (offline)" if health["mock_llm"] else "LIVE (Gemini)"
        st.success(f"API connected · {mode}")

    st.caption(f"Session `{st.session_state.session_id}`")
    if st.button("New session"):
        st.session_state.session_id = "st_" + uuid.uuid4().hex[:10]
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.markdown("**Last reply telltales**")
    last_agent = next((m for m in reversed(st.session_state.messages) if m["role"] == "agent"), None)
    if last_agent and last_agent.get("trace"):
        t = last_agent["trace"]
        v = t.get("guardrail_verdict", "—")
        color = VERDICT_COLOR.get(v, "#555")
        st.markdown(f'<span class="verdict-badge" style="background:{color}">'
                     f'{VERDICT_LABEL.get(v, v.upper())}</span>', unsafe_allow_html=True)
        st.caption(f"Knowledge grounded: {t.get('retrieval_confident')}")
        st.caption(f"Tools called: {', '.join(t.get('tools_called') or []) or 'none'}")
        st.caption(f"Latency: {t.get('latency_ms')} ms")
    else:
        st.caption("No messages yet this session.")

    st.divider()
    st.markdown("**Open tickets**")
    tickets_data, terr = call_api("GET", "/tickets")
    if tickets_data and tickets_data.get("open_tickets"):
        for tk in tickets_data["open_tickets"]:
            st.markdown(f'<span class="ticket-chip">{tk["ticket_id"]} · {tk["severity"]}</span>',
                         unsafe_allow_html=True)
            st.caption(tk["issue_summary"][:80])
    else:
        st.caption("None open.")

    st.divider()
    st.markdown("**Feedback on last reply**")
    fcols = st.columns(2)
    if fcols[0].button("👍 Helpful", use_container_width=True) and last_agent:
        call_api("POST", "/feedback", json={"session_id": st.session_state.session_id, "signal": "thumbs_up"})
        st.toast("Thanks — noted.")
    if fcols[1].button("👎 Not helpful", use_container_width=True) and last_agent:
        call_api("POST", "/feedback", json={"session_id": st.session_state.session_id, "signal": "thumbs_down"})
        st.toast("Thanks — noted.")
    fcols2 = st.columns(2)
    if fcols2[0].button("Too long", use_container_width=True) and last_agent:
        call_api("POST", "/feedback", json={"session_id": st.session_state.session_id, "signal": "too_long"})
        st.toast("Got it — I'll keep replies shorter.")
    if fcols2[1].button("Too short", use_container_width=True) and last_agent:
        call_api("POST", "/feedback", json={"session_id": st.session_state.session_id, "signal": "too_short"})
        st.toast("Got it — I'll add more detail.")

# --------------------------------------------------------------------------
# Main: the docket (conversation)
# --------------------------------------------------------------------------
st.markdown('<div class="brand-title">SUPPORT DOCKET</div>', unsafe_allow_html=True)
st.markdown('<div class="brand-sub">Ask about warranty, service booking, recalls, or roadside '
             'assistance. Sensitive or urgent cases are escalated to a human specialist with a '
             'ticket number.</div>', unsafe_allow_html=True)

if not st.session_state.messages:
    st.markdown('<div class="docket-entry agent">This is Bharat Motors\u2019 automated first line '
                 'of support. How can I help?</div>', unsafe_allow_html=True)

for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f'<div class="docket-entry user">{msg["text"]}</div>', unsafe_allow_html=True)
    else:
        t = msg.get("trace", {})
        v = t.get("guardrail_verdict", "allow")
        color = VERDICT_COLOR.get(v, "#7A756A")
        badge = f'<span class="verdict-badge" style="background:{color}">{VERDICT_LABEL.get(v, v.upper())}</span>'
        ticket = t.get("escalation_ticket")
        ticket_html = (f'<div class="ticket-chip">{ticket["ticket_id"]} · SLA {ticket["sla"]}</div>'
                        if ticket else "")
        st.markdown(
            f'<div class="docket-entry agent" style="border-left-color:{color}">'
            f'{badge}<br>{msg["text"]}{ticket_html}'
            f'<div class="meta-line">{t.get("latency_ms","—")} ms'
            f'{" · tools: " + ", ".join(t["tools_called"]) if t.get("tools_called") else ""}</div>'
            f'</div>', unsafe_allow_html=True)

# --------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------
prompt = st.chat_input("Type your question…")
if prompt:
    st.session_state.messages.append({"role": "user", "text": prompt})
    with st.spinner("Thinking…"):
        data, err = call_api("POST", "/chat", json={
            "session_id": st.session_state.session_id, "message": prompt,
        })
    if err:
        st.session_state.messages.append({
            "role": "agent",
            "text": f"Couldn't reach the support backend ({err}). Please try again shortly.",
            "trace": {"guardrail_verdict": "error"},
        })
    else:
        st.session_state.messages.append({
            "role": "agent", "text": data["response"], "trace": data,
        })
    st.rerun()
