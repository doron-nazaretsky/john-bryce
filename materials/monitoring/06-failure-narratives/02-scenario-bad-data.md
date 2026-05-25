---
kernelspec:
  name: python3
  language: python
  display_name: Python 3
---

# Scenario B — Bad Data

Someone in `#data-quality` asks: "Are the click counts off today?" There's no crash, no failed batch, no red dashboard. This is the dangerous failure mode — silent data loss with a successful-looking pipeline.

## Setup

```{code-cell} python
import requests, subprocess, time

PROM = "http://prometheus:9090/api/v1/query"
LOKI = "http://loki:3100/loki/api/v1/query_range"
TEMPO = "http://tempo:3200/api/search"

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
print(subprocess.check_output(["producer", "inject-bad", "200"], text=True))
time.sleep(20)  # let the next trigger fire and the WARN propagate
```

The producer emits 200 events without a `product_id` on its next tick. The `__BAD__` placeholder mechanism (see [*The ETL pipeline*](../02-lab-tour/02-the-etl-pipeline.md)) buckets them so the `foreachBatch` sink counts them, logs a WARN, drops them, and lets the good rows through.

The pipeline succeeds. Postgres just gets fewer rows than the producer sent. **Without observability you'd find out three days later, from a downstream finance report.**

## Detection — the warning indicator

Open **[00 · Overview](http://localhost:3001/d/overview)**. The **Schema-drop WARNs (30m)** stat goes from `0` (green) to `1` (yellow). That's all you need to know something dropped.

Same signal, inline:

```{code-cell} python
print(prom('sum(count_over_time({service_name="etl"} |= "dropped" |= "missing" [5m]))'))
```

If you missed it on Overview, **[40 · ETL Business](http://localhost:3001/d/etl)** carries the same signal twice — the **Schema-drop WARNs (1h)** stat and the **Schema-drop WARNs / sec** timeseries (a single spike). In production this query would back an alert rule.

## Analysis — find the offender's batch_id

On **40 · ETL Business**, scroll to the **All ETL log lines** panel and find the WARN line. Expand the row → click the **View traces for batch** button on the `batch_id` chip (mechanism: [*Cross-signal correlation*](../05-traces/02-cross-signal-correlation.md)) → Tempo opens with the matching `etl_batch` span. ~600 ms, normal shape. **The schema drop did not slow the pipeline down.**

Same path, executed:

```{code-cell} python
import re
warn = loki('{service_name="etl"} |= "dropped" |= "missing"', limit=1)
print("WARN:", warn[0] if warn else "(none yet — re-run after another trigger)")
# The WARN itself doesn't print the batch_id in the message body, but the matching
# epoch start (same e-N) carries `bad=1`. Pull the most recent such line.
ctx = loki('{service_name="etl"} |= "epoch start" |= "bad=1"', limit=1)
print("context:", ctx[0] if ctx else "(no bad epoch found)")
BATCH = re.search(r"batch_id=(\S+)", ctx[0]).group(1) if ctx else None
print("BATCH =", BATCH)
```

The `epoch start` line gives you `batch_id=e-<N>`. Look it up in Tempo (the TraceQL search Grafana opens behind the derived-field button):

```{code-cell} python
r = requests.get(TEMPO, params={"q": f'{{ .batch_id = "{BATCH}" }}', "limit": 1}).json()
trace = r.get("traces", [{}])[0]
print("trace_id:", trace.get("traceID"), "duration_ms:", trace.get("durationMs"))
```

Copy-paste targets for **Explore → Tempo** (TraceQL):

```traceql
{ .batch_id = "e-130" }                                       # one specific epoch
{ resource.service.name = "etl-driver" && duration > 2s }     # any slow etl_batch
```

## Analysis — full timeline for the affected batch

Back in **Explore → Loki**, pivot the other way:

```logql
{service_name=~".+"} | batch_id="e-130"
```

Inline:

```{code-cell} python
for line in loki(f'{{service_name=~".+"}} | batch_id="{BATCH}"', limit=10):
    print(line)
```

You see the entire story for that one micro-batch:

```
epoch start batch_id=e-130 input_rows=21 good=20 bad=1
dropped 200 records missing product_id (running total across 1 open window(s))
epoch done batch_id=e-130 rows_written=20 bad=1
streaming progress batch_id=e-130 input_rows=1800 dropped_by_watermark=0
```

This is the cross-signal pivot working: one identifier (`batch_id`) lets you see *what came in*, *what was rejected*, *what was written*, *what the watermark dropped*. Four lines, complete picture.

Note the shape: `input_rows=21` in the *aggregate stream* (rows whose count changed) versus `1800` in the *streaming progress* (raw events read from Kafka). **Knowing which number means what** is operator-fluency you build by reading these logs a few times.

## Verify in the sink

The narrative ends in Postgres, where a downstream consumer would notice:

```{code-cell} python
sql = (f"SELECT minute_window, SUM(click_count) AS total FROM aggregated_clicks "
       f"WHERE last_batch_id = '{BATCH}' GROUP BY minute_window;")
print(subprocess.check_output(
    ["docker", "exec", "postgres", "psql", "-U", "app", "-d", "clicks", "-c", sql],
    text=True))
```

The sum is ~200 lower than the producer's contribution for that minute. `last_batch_id` is the column that makes this query possible — every materialized table should carry it.

## What this scenario teaches

- A pipeline can succeed and still be wrong. The signal you need is a **deliberate WARN** at the silent-failure point, not an exception.
- Three clicks (Loki → derived field → Tempo → "Logs for this span") get you from "something dropped" to "every log line in the affected batch". That's what the cross-signal pivot buys you.
- The pivot identifier is `batch_id`, a business-level value — not `trace_id`. The reasoning is in [*Cross-signal correlation*](../05-traces/02-cross-signal-correlation.md).
