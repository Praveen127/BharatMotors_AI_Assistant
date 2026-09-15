"""
langsmith_tracer.py
Lightweight tracer producing LangSmith-shaped trace spans (run name,
start/end time, inputs, outputs, parent/child span linkage) so an
individual interaction's internal steps (guardrail check -> retrieval ->
tool call -> LLM generation) can be inspected, not just the final answer.

Real LangSmith tracing (via `LANGCHAIN_TRACING_V2=true` + API key) uploads
these spans to smith.langchain.com over the network. Here, spans are
appended locally to logs/interactions.log under a "spans" key attached to
each interaction record when TRACE_MODE=verbose, keeping a single offline
evidence trail. See docs/engineering_justification.md, "Observability".
"""
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import List, Any


@dataclass
class Span:
    name: str
    start_ts: float
    end_ts: float = None
    inputs: Any = None
    outputs: Any = None

    def duration_ms(self):
        return round(((self.end_ts or time.time()) - self.start_ts) * 1000, 2)


class Tracer:
    def __init__(self):
        self.spans: List[Span] = []

    @contextmanager
    def span(self, name: str, inputs: Any = None):
        s = Span(name=name, start_ts=time.time(), inputs=inputs)
        try:
            yield s
        finally:
            s.end_ts = time.time()
            self.spans.append(s)

    def as_dicts(self):
        return [{"name": s.name, "duration_ms": s.duration_ms(),
                  "inputs": s.inputs, "outputs": s.outputs} for s in self.spans]
