---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# Evals and observability for agents

Yesterday's monitoring lesson covered observability for a data pipeline. Agents need the same discipline — and a piece neither logs nor metrics nor traces alone covers: **evals**, a regression-testing harness for non-deterministic systems.

This lesson sketches both. It is necessarily short — the right level of either depends on your stack — but the patterns and the link back to traditional observability are what you take away.

## What "an eval" actually is

An eval is **a fixed set of inputs and a checker** that runs your agent and scores its outputs. Think `pytest`, but the unit under test is "the agent" and the assertions tolerate phrasing variation.

The minimum useful shape:

```python
EVAL_CASES = [
    {"q": "How many films do we have?",                 "must_contain": ["1000"]},
    {"q": "Top spending customer?",                     "must_contain": ["KARL", "SEAL"]},
    {"q": "Top film category by rentals?",              "must_contain": ["Sci-Fi"]},
]

def run_eval(agent_fn, cases):
    results = []
    for case in cases:
        ans = agent_fn(case["q"])
        passed = all(token in ans.upper() for token in
                     (t.upper() for t in case["must_contain"]))
        results.append({"q": case["q"], "passed": passed, "answer": ans})
    return results
```

Three notes:

- Cases live in a YAML file or a database — checked into the repo like tests.
- The check is **lenient** by design (substring, regex, length range). Strict string equality fails on harmless phrasing differences.
- Run on **every code change**, including changes to the system prompt or tool descriptions. Those are the biggest behavior-change risks.

## Eval categories that earn their cost

- **Correctness.** "Did the agent reach the right number?" — exactly what we asserted in blocks 04 and 08.
- **Tool use.** "Did the agent call the tool I expected, with the arguments I expected?" — captures regressions where the model starts skipping a discovery step.
- **Safety.** "Did the agent refuse to do X under prompt-injection conditions?" — the block-06 demo, encoded as a permanent test.
- **Cost & latency.** "Did the agent reach the answer in ≤K turns and ≤T tokens?" — catches model upgrades that make the agent more verbose.

You usually have ~20–100 cases per agent. More is fine; the floor is "enough to catch regressions before they reach users."

## Tracing the loop

The other half is **traces**: a record of every turn — model call, tool call, tool result, latency — so that when something goes wrong in production you can replay what the agent saw.

The block-02 message list is already most of a trace; you just need to persist it. The minimum-viable persistence:

```python
import time, json, uuid

def traced_run(question):
    trace_id = str(uuid.uuid4())
    started = time.time()
    messages = [{"role":"system","content":SYSTEM_PROMPT},
                {"role":"user","content":question}]
    events = []
    # ... loop body, recording each turn ...
    elapsed = time.time() - started
    # Persist {trace_id, started, elapsed, messages, events} to your sink of choice.
    return trace_id, final_answer
```

Where to send the trace:

- **OpenAI's traces dashboard** (`platform.openai.com/traces`). Free, automatic if you use the Agents SDK. Convenient for OpenAI-only setups.
- **OpenTelemetry → your existing backend.** Wrap each LLM and tool call in a span; ship to whatever monitoring stack yesterday's lesson set up. This is the right answer at scale — agents are not special enough to need a separate observability stack.
- **A simple table in Postgres / S3.** For early-stage projects, persisting the message list + metadata is enough.

## The link back to the monitoring module

The monitoring stack from yesterday — Prometheus for metrics, Loki for logs, Tempo for traces, Grafana for everything — works for agents too. The only changes are what you instrument:

| Signal | What to record for an agent |
|---|---|
| **Metrics** | `agent_turns_per_request`, `agent_tokens_per_request`, `agent_tool_call_count{name=...}`, `agent_failure_total{reason=...}` |
| **Logs** | The system prompt version, the model, structured per-turn entries (which tool, args, result size) |
| **Traces** | One span per turn; child spans for each tool call. Tag the root span with the user question hash for correlation |

The advice from that lesson applies unchanged: **attach business identifiers** (`request_id`, `user_id`) to every signal so you can pivot from "this user reported a wrong answer" to "show me the trace" without guessing.

## SLIs for agents that are worth tracking

- **Answer correctness (offline)** via the eval suite, run on a sample of production traces.
- **Time-to-final-answer (p50, p95)** — agents that grow slowly are a sign of prompt bloat.
- **Tokens per request (p50, p95)** — the cost SLI. Spikes here are usually a system-prompt change or a runaway loop.
- **Tool call success rate** — by tool name. The first signal that a downstream system has issues.
- **`max_turns` hit rate** — should be near zero. If it climbs, the agent is getting confused.

## One thing not to do

Do **not** rely on the model to evaluate its own outputs in production as the primary SLI. "LLM-as-judge" is a useful research technique and a reasonable component of an eval suite, but it is correlated with the model under test and shouldn't be your only signal. Pair it with deterministic checks (the `must_contain` style above) and human spot-checking.

## What we just learned

- Evals are a regression-testing harness for agents: fixed cases, lenient checks, run on every change.
- Four eval categories pay rent: correctness, tool use, safety, cost/latency.
- Traces are a persisted message list plus per-turn metadata; ship to your existing observability stack via OpenTelemetry.
- The monitoring stack from yesterday handles agents unchanged — the metric names change, not the architecture.

Next, and last: the open exercise.
