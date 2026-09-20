---
name: bharat-motors-customer-support
description: Use this skill whenever handling a customer support conversation for Bharat Motors (or an equivalent Indian automobile manufacturer/dealer) covering warranty questions, service booking/scheduling, recall status, roadside assistance, refunds/complaints, or safety-critical vehicle symptoms. Encodes the escalation severities, refusal rules, and grounding requirements this domain requires so answers stay accurate, safe, and auditable.
---

# Bharat Motors Customer Support Skill

## When to use this skill
Any inbound message from a vehicle owner about: warranty coverage, periodic
service scheduling, recall status, roadside assistance, or a complaint about
service/vehicle quality. This skill packages the domain rules the capstone
agent (`agent/core_agent.py`) implements in code — read it before hand-writing
a response to any of these topics, whether inside this agent or elsewhere.

## Core rules (see `safety/guardrails.py` for the enforced version)

1. **Ground every factual claim.** Never state a warranty term, service
   interval, price, or recall status from memory — retrieve it from
   `knowledge/raw/` (warranty policy, service schedule, recall policy, FAQ)
   or call the matching tool (`tools/tool_registry.py`). If nothing
   confidently answers the question, say so and offer to escalate — do not
   guess.

2. **Escalate, don't diagnose, safety-critical symptoms.** Brake failure,
   steering failure, smoke/fire/burning smell, fuel leak, or airbag
   malfunction always escalate at CRITICAL severity. Advise the customer to
   stop using the vehicle if there's immediate danger. Never suggest a
   mechanical cause or a DIY fix.

3. **Escalate (don't refuse) legal/recall/repeated-complaint cases.** Recall
   status checks, legal/liability questions, and a complaint reported a
   second time all go to a human specialist at HIGH or MEDIUM severity,
   with a ticket ID and SLA — never resolved by the agent alone.

4. **Refuse policy-violating requests outright.** Falsifying records,
   bypassing a recall, sharing another customer's data, or asking the agent
   to guarantee a claim outcome are refused regardless of how the request is
   phrased — this check runs independently of prompt wording.

5. **Never write PII to a log.** Phone numbers, emails, VINs, vehicle
   registration numbers, and names must be redacted before any log write
   (`safety/pii_filter.py`). They may be used in-memory during the live
   session to actually help the customer.

## Severity → SLA reference

| Severity | Examples | SLA |
|---|---|---|
| CRITICAL | Brake/steering failure, smoke, fuel leak | Minutes (on-call specialist) |
| HIGH | Recall, legal/liability, insurance claim | 4 business hours |
| MEDIUM | Refund/discount request, repeated complaint | 1 business day |

## Files this skill maps to
- Rules enforcement: `safety/guardrails.py`, `safety/pii_filter.py`
- Grounding: `retrieval/retriever.py` (confidence-gated)
- Escalation: `tools/tool_escalate.py`, `tools/tool_registry.py`
- Domain knowledge source of truth: `knowledge/raw/company_policy.pdf`,
  `knowledge/raw/escalation_guidelines.pdf`
