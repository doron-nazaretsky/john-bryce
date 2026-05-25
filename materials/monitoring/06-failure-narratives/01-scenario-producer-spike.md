---
kernelspec:
  name: python3
  language: python
  display_name: Python 3
---

# Scenario A — Producer Spike

You're on call. Slack lights up: "anyone else seeing weird throughput on clicks?" You have the dashboards, you have Explore, you have nothing else. Walk it.

## Setup — tiny query helper

These cells run inside the `workspace` container, on the same docker network as Prometheus, Loki, and Tempo. We use that to fetch the *same numbers* the Grafana panels show — so you can read along even without flipping browser tabs.

```{code-cell} python
import requests, subprocess, time

PROM = "http://prometheus:9090/api/v1/query"
LOKI = "http://loki:3100/loki/api/v1/query_range"

def prom(q: str):
    r = requests.get(PROM, params={"query": q}).json()["data"]["result"]
    return [(m.get("metric", {}), float(m["value"][1])) for m in r]

def loki(q: str, lookback_s: int = 60, limit: int = 10):
    now = int(time.time() * 1e9)
    r = requests.get(LOKI, params={
        "query": q, "limit": limit,
        "start": now - lookback_s * 10**9, "end": now,
    }).json()["data"]["result"]
    return [v[1] for s in r for v in s["values"][:limit]]
```

## Baseline

```{code-cell} python
print("producer rate:", prom('sum(deriv(kafka_partition_current_offset_ratio{topic="clicks"}[1m]))'))
print("consumed rate:", prom('sum(rate(kafka_consumer_records_consumed_total[1m]))'))
for line in loki('{service_name="etl"} |= "streaming progress"', limit=3):
    print(line)
```

Expected: producer/consumed near 100/sec; each epoch's `input_rows` is ~1000 (we use a 10-second trigger, so ~10 × 100/sec ≈ 1000 per epoch).

## Trigger

```{code-cell} python
print(subprocess.check_output(["producer", "rate", "5"], text=True))
time.sleep(60)  # let two trigger intervals settle through the stack
```

The producer now emits ~500 events/sec instead of ~100. Nothing else changes — the streaming query keeps running, no exceptions, no failed epochs.

## Detection — start at the Overview

Open **[00 · Overview](http://localhost:3001/d/overview)**. Two panels move within ~30 seconds:

- **Producer rate** stat jumps from ~120 to ~400 events/sec.
- **Throughput timeseries** ("produced → consumed → written") shows the `produced/sec` line stepping up; the `consumed/sec` line follows it after the next trigger fires.

Same numbers, fetched inline:

```{code-cell} python
print("producer rate:", prom('sum(deriv(kafka_partition_current_offset_ratio{topic="clicks"}[1m]))'))
print("consumed rate:", prom('sum(rate(kafka_consumer_records_consumed_total[1m]))'))
print("pg write rate:", prom('sum(rate(postgresql_operations_total{postgresql_table_name="public.aggregated_clicks",operation=~"ins|upd"}[1m]))'))
```

That's the leading signal. Nothing red, no failed batches — just a visible shift in the topline numbers. This is the production playbook: glance at Overview every morning, and a chart shape changing is your first clue.

The **Postgres write rate** does *not* move much — the streaming aggregation writes one row per `(product × open window)`, so 5× more events still produce roughly the same ~20 changed rows per epoch. **Input rate ≠ output rate** when aggregation collapses a dimension.

## Analysis — drill into Kafka

Click the **[Kafka](http://localhost:3001/d/kafka)** link at the top of the overview.

- **Production rate (partition offset growth)** — each of the 4 partition lines steps up to roughly 100/sec each (4 × 100 = ~400 total, matches the overview).
- **Consumer lag over time** — with a 10s trigger Spark catches up every epoch; lag stays low. Crank the rate higher (`producer rate 20`) and the consumer can't keep up — that's when all four partition lines climb together.

Same per-partition production view from here:

```{code-cell} python
for m, v in prom('sum by (partition) (deriv(kafka_partition_current_offset_ratio{topic="clicks"}[1m]))'):
    print(f"partition {m['partition']}: {v:.0f}/sec")
```

The "all lines climb together" shape is diagnostic: it means the bottleneck is *downstream* of Kafka — the consumer. If one partition climbed and the others were flat, you'd suspect a broker issue or a stuck partition assignment.

## Analysis — confirm in logs

In **Explore → Loki**, paste this query (copy-paste target — open <http://localhost:3001/explore>):

```logql
{service_name="etl"} |= "streaming progress"
```

Or fetch the same lines inline:

```{code-cell} python
for line in loki('{service_name="etl"} |= "streaming progress"', limit=5):
    print(line)
```

The `input_rows` per epoch now reads ~5000 instead of ~1000 — the same story Kafka told you, read from a different signal. **Two independent confirmations from two signals = high confidence.**

## Recovery

```{code-cell} python
print(subprocess.check_output(["producer", "rate", "1"], text=True))
time.sleep(60)
print("producer rate (after recovery):", prom('sum(deriv(kafka_partition_current_offset_ratio{topic="clicks"}[1m]))'))
```

Watch the throughput timeseries on Overview: produced/sec drops back, consumed/sec drops with it on the next trigger, `input_rows` returns to ~1000.

## What this scenario teaches

- The Overview's job is to make a shift like this visible in one glance.
- A shape change in a timeseries is a *finding*, not yet a *cause* — you went to Kafka, then to Loki to triangulate.
- Windowed aggregation hides per-event volume from downstream — the Postgres write rate barely flinched. If your alerting only watched the sink, you'd miss this entirely.
