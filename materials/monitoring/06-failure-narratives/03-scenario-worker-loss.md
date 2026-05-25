---
kernelspec:
  name: python3
  language: python
  display_name: Python 3
---

# Scenario C — Compute Loss

A Spark worker dies. In a Kubernetes-backed cluster this is a daily event — preemptible nodes, autoscaler decisions, OOM kills. The pipeline is *supposed* to absorb it. Did it?

## Setup

```{code-cell} python
import requests, subprocess, time

PROM = "http://prometheus:9090/api/v1/query"
LOKI = "http://loki:3100/loki/api/v1/query_range"

def prom(q):
    return requests.get(PROM, params={"query": q}).json()["data"]["result"]

def loki(q, lookback_s=120, limit=10):
    now = int(time.time() * 1e9)
    r = requests.get(LOKI, params={"query": q, "limit": limit,
                                   "start": now - lookback_s*10**9, "end": now}).json()["data"]["result"]
    return [v[1] for s in r for v in s["values"][:limit]]
```

## Trigger

```{code-cell} python
print(subprocess.check_output(["producer", "rate", "3"], text=True))   # give Spark visible work per epoch
time.sleep(15)
print(subprocess.check_output(["docker", "kill", "spark-worker-1"], text=True).strip())
time.sleep(45)  # wait for OTel pulls + a few epochs to fire
```

## Detection — the heap chart goes flat

Open **[20 · Spark](http://localhost:3001/d/spark)**. The headline panel **JVM heap used — driver vs each executor** has two executor lines, one per worker. Within ~30 seconds of the kill:

- `spark-worker-2`'s line keeps moving (sawtooth as each epoch runs and GC settles).
- `spark-worker-1`'s line goes **flat as a board**. The JVM stopped exporting, so the OTel collector's last-known value just persists.

The flatline is the visible symptom. Verify it inline:

```{code-cell} python
# Each executor's *fresh* heap activity in the last minute. A dead JVM has 0 here.
for m in prom('count by (host_name) (increase(jvm_memory_used_bytes{service_name="spark-executor"}[1m]) > 0)'):
    print(m["metric"].get("host_name"), "→ fresh samples:", m["value"][1])
```

`spark-worker-1` will be absent (no fresh samples); `spark-worker-2` will be present.

> A subtlety worth knowing: the `Live executors` stat at the top still reads `2` for several minutes. Prometheus's stale-series timeout is 5 minutes, so a dead worker keeps "counting" for that long. The heap chart is the better signal because *fresh* movement vs *frozen* values is visible immediately. In production you'd write the stat with the `increase(...)[1m] > 0` filter above to count only freshly-reporting hosts.

## Analysis — did the pipeline absorb it?

The load-bearing question. In **Explore → Loki** paste:

```logql
{service_name="etl"} |= "epoch done"
```

Or inline:

```{code-cell} python
for line in loki('{service_name="etl"} |= "epoch done"', limit=6):
    print(line)
```

Every epoch completes. No `epoch failed` lines, no ERRORs. That's Spark + Structured Streaming doing their job:

- Spark's task scheduler detects the lost executor and reschedules tasks onto the remaining worker.
- The streaming engine retries any mid-flight micro-batch from the checkpoint with the same `epoch_id`. The REPLACE upsert is idempotent, so the data stays correct.

**The pipeline self-healed.** Exactly why this failure mode is dangerous without observability — there is no ERROR to grep for. The only sign was the dashboard.

## Analysis — what did the recovery look like in time?

Open **[Explore → Tempo](http://localhost:3001/explore)** with TraceQL:

```traceql
{ resource.service.name = "etl-driver" }
```

Sort by start time and scan the `etl_batch` durations across the outage window. With our baseline load and only the upsert work inside the span, durations stay broadly similar — Spark's checkpoint replay is cheap and the surviving executor is barely loaded. **The point of looking is that the trace lets you ask the question** ("did any epoch take noticeably longer than usual?") in one query, against business-meaningful durations. Under real load, a duration shift here is where the cost of the failure would first appear.

| Signal | What it told you |
|---|---|
| Metrics (heap chart) | An executor disappeared. |
| Logs (epoch done) | The pipeline self-healed. |
| Traces (etl_batch duration) | The place to ask "did the recovery cost us latency?" — answered in business durations, not infra metrics. |

This is the integration test of the whole module. **Three signals, one investigation.**

## Recovery

```{code-cell} python
print(subprocess.check_output(["docker", "start", "spark-worker-1"], text=True).strip())
print(subprocess.check_output(["producer", "rate", "1"], text=True))
time.sleep(45)
for m in prom('count by (host_name) (increase(jvm_memory_used_bytes{service_name="spark-executor"}[1m]) > 0)'):
    print(m["metric"].get("host_name"), "→ fresh samples:", m["value"][1])
```

Both workers should be back to reporting fresh samples, the heap chart's flat line starts moving again, and the next epoch's `etl_batch` trace duration returns to baseline.

## What this scenario teaches

- "Did it work?" and "Did it cost us anything?" are two different questions answered by two different signals.
- Self-healing infrastructure is a gift wrapped in a trap: the failure is silent in logs but visible in metrics and traces. Watch all three.
- Beware stat panels that don't disambiguate fresh from stale. When you build dashboards, ask: *if the source stopped exporting, would this panel still look healthy?*
