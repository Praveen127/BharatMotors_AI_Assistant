# Problem Framing Document
## Customer Support Agent — Indian Automobile Industry (Bharat Motors)

**Capstone Track:** A — Framework-Based (LangChain)
**Industry Scenario:** Scenario 3 — Customer Support: AI Support Resolution Agent

---

## 1. Who is the user, and what workflow does the agent support?

**Primary persona:** Anaya, a car-owning customer of Bharat Motors, a fictional
Indian passenger-vehicle manufacturer used as the training domain for this
capstone. Anaya contacts support through a chat channel (web widget or app)
with everyday ownership questions and occasional urgent issues.

**Daily workflow the agent supports:** first-line, always-on customer support
for post-purchase vehicle ownership — the questions a call-center agent or
service-center front desk currently fields dozens of times a day:
- "Is my car still under warranty?"
- "Where's my nearest service center?"
- "Does my car have a pending recall?"
- "I have a complaint / my car has a problem — help."

The agent's job is to resolve the routine cases instantly, ground every
factual claim in verified company documents, and hand off anything sensitive,
unresolved, or unsafe to a human specialist with full context — never to
pretend it can do a human's job.

## 2. The exact problem being solved

Bharat Motors' support volume is dominated by a small set of repetitive,
policy-answerable questions, but they currently compete for the same queue
as safety-critical and legally sensitive cases, causing slow response times
across the board. A poorly-designed automated agent makes this worse in two
specific, dangerous ways: (a) it can **invent** a warranty/recall answer that
sounds confident but is wrong, and (b) it can **fail to escalate** a genuine
safety issue (e.g. brake failure) because it tries to be helpful instead of
handing off. This capstone builds an agent that is deliberately conservative
in both directions.

## 3. Inputs, outputs, constraints, assumptions

| | |
|---|---|
| **Input** | Free-text customer message, optional session ID; may contain a vehicle registration number, VIN, or PIN code. |
| **Output** | A grounded natural-language response, OR a refusal, OR an escalation with a ticket ID and SLA. Every output is traceable to a guardrail verdict, retrieved source(s), and/or tool call. |
| **Constraint** | The agent must never approve/reject a claim, quote a legal opinion, fabricate a policy number, or write PII to persistent logs. |
| **Assumption** | Backend systems (warranty DB, service-center directory, recall DB) are represented here as mock lookups (`tools/tool_registry.py`) standing in for real internal APIs — architecturally interchangeable without changing the agent logic. |
| **Assumption** | The agent is a *decision-support / resolution* layer, not a transactional one — it never moves money, changes a booking, or edits a customer record. |

## 4. Example user questions (5)

1. "Is my car's engine still covered under warranty?"
2. "Can you check the warranty status for registration MH12AB1234?"
3. "Where's the nearest service center to PIN 560001?"
4. "My brakes just failed and I can smell burning — what do I do?"
5. "This is the second time I'm reporting my AC isn't cooling and nothing's been done."

## 5. Success criteria

The agent is successful if, across a held-out test set (see
`data/evaluation/test_cases.json`, n=12):

- **≥90% guardrail accuracy** — safety-critical, refusal, and escalation
  triggers fire on the correct cases (achieved: **100%**, see
  `docs/evaluation_report.md`).
- **100% tool-selection accuracy** on unambiguous tool-intent messages
  (achieved: **100%**).
- **No fabricated policy answers** — the agent must report "no confident
  match" rather than guess when retrieval confidence is low (grounding
  alignment achieved: **100%** after threshold tuning).
- **Zero raw PII bytes in `logs/interactions.log`** (verified by pattern scan,
  see Evaluation Report §"Safety Enforcement").
- **Sub-second latency** for guardrail/tool/escalation paths; retrieval+LLM
  paths bounded by the LLM call itself (mock: <1s; real API: provider-dependent).

## 6. Known failure cases and edge scenarios (anticipated up front)

| Scenario | Required behaviour |
|---|---|
| Safety-critical symptom (brakes, smoke, fuel leak) | Escalate CRITICAL, advise stopping vehicle use, do not diagnose |
| Active/possible recall mentioned | Escalate HIGH, never assert recall status without a VIN lookup |
| Refund/discount/dissatisfaction | Escalate MEDIUM, never authorize a waiver |
| Same complaint reported twice | Detected via session memory, escalated MEDIUM instead of repeating the same canned answer |
| Ambiguous/underspecified tool request (e.g. warranty question, no reg. number) | Tool call is **skipped**, not guessed — agent asks for the missing detail |
| Question outside the knowledge base (e.g. exact resale value) | Retrieval confidence check reports "no confident match"; agent declines to guess |
| Request to falsify a record / bypass a recall / get another customer's data | Hard refusal, independent of any prompt wording |
| Multi-part question ("Is it under warranty? Also find me a service center") | Decomposed by `agent/planner.py`, each sub-task handled and combined |
| LLM/API failure at runtime | `deployment/app.py` catches the exception, logs it, returns a graceful fallback message |

This document is intentionally written *before* Phase 2 implementation began,
and the test cases in Section 5 map 1:1 onto `data/evaluation/test_cases.json`
used in the Phase 9 evaluation harness.
