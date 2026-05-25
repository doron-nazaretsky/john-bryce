# Monitoring Module — Blueprint (Source of Truth)

> **For the executing agent only.** Excluded from the MyST site. Read this before every section reshape. Update this **before** changing terminology, owning-page assignments, or the narrative spine.

## How to use this file

1. The **narrative spine** is the canonical TOC. `myst.yml` follows it, not the reverse.
2. The **concept ledger** says exactly one page owns each concept. Other pages must reference rather than re-define.
3. The **terminology decisions** are forced choices that resolve current-text inconsistencies. Don't drift.
4. The **scenario payoff matrix** is the dead-end filter. Anything taught in section 5 must show up in at least one cell, or it gets cut.
5. The **forward-reference budget** is what section 1 is allowed to name without defining.

If a reshape pass discovers something this file got wrong, **edit this file first**, fix the section second.

---

## 1. Narrative spine (the desired shape)

Eleven pages, six sections. Each line: `<slug> — "<question the page answers>"`. Slugs are stable identifiers used in cross-references; filenames must match the slug.

### Welcome (top-level)

- `welcome` — "What is this module about and what should I leave knowing?"
  - Replaces the current `README.md`. Includes the module premise, the four-hour learning path, prerequisites, and a one-paragraph honest framing that says *the stack is operated by platform/SRE teams in real life; this module makes you a competent consumer of it*. No concept content; pure orientation.

### 01-foundations

- `01-foundations/01-why-observability` — "Why does a data pipeline need observability at all, and how is this different from monitoring?"
  - Owns: monitoring vs observability; the silent / slow-burning / multi-hop / schema-related failure shapes; *trust no aggregate*; the DE-specific feedback-loop problem.
- `01-foundations/02-pillars-and-stack` — "What are the moving parts of an observability stack, and what is *ours* concretely?"
  - **Merges** the current `01-introduction/02-the-four-pillars.md` and `01-introduction/03-stack-tour.md`. One mermaid diagram for the four pillars (concept), one mermaid for our stack (concrete). One table for the 10 containers. The "OTel SDK ≠ OTel Collector" naming clarification lives here, once.

### 02-lab-tour

- `02-lab-tour/01-bring-up-the-lab` — "How do I get the lab running and verify everything is healthy?"
  - Docker memory bump, `make lab-monitoring`, healthcheck table, URLs, smoke test. **Cut**: the "note on the long-running daemon" meta-history about earlier lab iterations.
- `02-lab-tour/02-the-etl-pipeline` — "What is the ETL doing, and what conventions does it follow that the rest of the module relies on?"
  - **Canonical home for**: `batch_id` convention (`e-<N>`, derived from Spark `epoch_id`); `__BAD__` placeholder mechanism; the 2-minute watermark setting (with one-sentence link to `materials/streaming/03-streaming/06-watermarks.md` for the concept); `foreachBatch` REPLACE upsert; what `producer rate`, `producer inject-bad`, `spark batch start/stop/status` do.
- `02-lab-tour/03-grafana-orientation` — "Where do I look in Grafana, and how do the five dashboards encode an investigation workflow?"
  - The current Grafana orientation rewrite stands; light cross-reference edits only.

### 03-metrics

- `03-metrics/01-metrics-concepts` — "What is a metric, what kinds exist, and what can go wrong (cardinality)?"
  - Owns: counter/gauge/histogram/summary, cardinality, scrape vs push, OTLP vs Prom exposition format. Ends with a *short* "in our lab" section: ~5 lines naming the three metric sources (Java agent, kafkametrics receiver, postgresql receiver) and pointing at `02-pillars-and-stack` for the wiring. **No** standalone "metrics pipeline" page.
- `03-metrics/02-reading-the-dashboards` — "How do I read the four metrics dashboards (Overview, Kafka, Spark, Postgres)?"
  - The current `03-metrics/03-reading-the-dashboards.md`. The "When to leave Overview" decision table is **removed from here** and lives only in `02-lab-tour/03-grafana-orientation`.

### 04-logs

- `04-logs/01-logs-concepts` — "What are logs for (and what are they *not* for), and how do modern log stores stay cheap?"
  - **Opens with** "don't reach for logs when you wanted metrics" — promoted to load-bearing position. Then: structured vs unstructured, levels, label-indexed storage (cross-references cardinality in `03-metrics/01`), structured metadata. Ends with short "in our lab" section: JSON formatter + filelog receiver + shared `etl-logs` volume in ~10 lines. **No** standalone "logs pipeline" page.
- `04-logs/02-querying-logs` — "How do I actually query logs in Grafana?"
  - LogQL anatomy + the five queries. Live tail. Mentions the Loki→Tempo derived field briefly, but the full mechanism lives in `05-traces/02-cross-signal-correlation`.

### 05-traces

- `05-traces/01-traces-concepts` — "What is a trace, and why does the textbook 'one trace tree per request' story break in distributed compute?"
  - Owns: spans, trace_id, parent/child, sampling (mentioned, deferred). **Owns trace fragmentation** — explained once, here, with the standard "use a shared business attribute as the pivot" answer that motivates `05-traces/02`. Mentions auto vs manual instrumentation but the *cost/effort* discussion sits here, not on two pages. Ends with short "in our lab" section naming the two trace sources (Java agent on JVMs, manual `etl_batch` span in Python).
- `05-traces/02-cross-signal-correlation` — "How do I navigate from a symptom in one signal to the same batch in every other signal?"
  - Merges the current `05-traces/02-the-traces-pipeline.md` (cut down) and `05-traces/03-correlation-across-signals.md`. The pivot mechanism IS the trace story that matters for this lab. **spot SparkListener / `job-NNNN` material is reduced to one paragraph** noting it exists, it gives you Spark-internal spans we don't pivot on, and pointing readers at the Production Patterns page. Two clear directions: Loki→Tempo via derived field; Tempo→Loki via `tracesToLogsV2`. The TraceQL primer (4 queries) stays.

### 06-failure-narratives

- `06-failure-narratives/01-producer-spike` — Scenario A. The current page; cross-references trimmed (no re-explaining `batch_id`).
- `06-failure-narratives/02-bad-data` — Scenario B. The structural climax. Cross-references trimmed.
- `06-failure-narratives/03-worker-loss` — Scenario C. **Action item:** retune the trigger so the trace duration delta is unambiguous (raise `producer rate` during the kill so the surviving executor visibly queues), OR reframe the trace claim as "lets you ask the question" instead of "quantifies the cost". Pick one in the reshape, don't ship the current hedge.
- `06-failure-narratives/04-what-we-didnt-show` — Renamed from "production patterns". Honest "further reading" list with priorities: alerting (Alertmanager), sampling (head/tail/exemplars), Spark UI / History Server, profiling (Pyroscope), OpenLineage, orchestrator-level tracing. Each topic = 3–5 sentences. No tutorials. The grab-bag becomes a curated map.

**Total page count: 11** (down from 19, with no information lost — the cuts are duplications and dead ends).

---

## 2. Concept ledger

One row per concept. **Owning page is the only page that explains it.** Other pages reference in one clause.

| Concept | Owning page | Terminology | One-line definition |
|---|---|---|---|
| Monitoring vs observability | `01-foundations/01-why-observability` | "monitoring" = predicted threshold checks; "observability" = ad-hoc questions | Monitoring answers known questions; observability lets you ask new ones. |
| DE-specific failure shapes | `01-foundations/01-why-observability` | "silent / slow-burning / multi-hop / schema-related" | Pipelines fail in ways that don't trip exit codes. |
| Platform-team ownership | `01-foundations/01-why-observability` | "platform / SRE / DevOps team" | The stack is operated by another team; the DE consumes it. |
| The four pillars | `01-foundations/02-pillars-and-stack` | "instrumentation / collection / storage / analytics" | Every observability stack does these four things in this order. |
| OTel SDK vs Collector vs OTLP | `01-foundations/02-pillars-and-stack` | SDK = in your app; Collector = sidecar daemon; OTLP = wire format | Different OTel pieces students will conflate; name them once. |
| Contrib vs core collector distribution | `01-foundations/02-pillars-and-stack` | "contrib distribution" | Receivers like `kafkametrics`, `postgresql`, `filelog` are contrib-only. |
| Our 10 containers | `01-foundations/02-pillars-and-stack` | (table) | One canonical container table in the module. |
| Docker memory requirement | `02-lab-tour/01-bring-up-the-lab` | "8 GB" | Lab needs ~7.6 GB; default 4 GB causes silent OOMs. |
| Lab CLIs (`producer`, `spark`) | `02-lab-tour/02-the-etl-pipeline` | (table) | `producer rate / inject-bad / start / stop / status`, `spark batch start / stop / status`. |
| `batch_id` convention | `02-lab-tour/02-the-etl-pipeline` | `e-<N>`, derived from Spark `epoch_id` | The cross-signal pivot identifier; on every log line, the `etl_batch` span, and the Postgres `last_batch_id` column. |
| `epoch_id` / micro-batch | `02-lab-tour/02-the-etl-pipeline` | "epoch" (Spark's word); never "micro-batch id" in prose | Spark's monotonic integer for each streaming trigger. |
| `__BAD__` placeholder | `02-lab-tour/02-the-etl-pipeline` | `__BAD__` literal | Buckets records with missing `product_id` so they count without writing. |
| Watermark setting | `02-lab-tour/02-the-etl-pipeline` | "2 minutes" | Links to streaming module for the watermark *concept*; this page owns only *our setting*. |
| `foreachBatch` REPLACE upsert | `02-lab-tour/02-the-etl-pipeline` | "REPLACE upsert" | Idempotent under replay because the aggregate is Spark-state-store-maintained. |
| The five dashboards | `02-lab-tour/03-grafana-orientation` | "00 Overview / 10 Kafka / 20 Spark / 30 Postgres / 40 ETL Business" | One table; investigation order. |
| Investigation pattern (Overview → system → Explore) | `02-lab-tour/03-grafana-orientation` | "RED / USE methods" mentioned in passing | The mermaid flow lives only here. |
| Dashboards-are-provisioned-from-disk caveat | `02-lab-tour/03-grafana-orientation` | (note) | Edits don't survive restart; edit JSON in `labs/monitoring/config/grafana/dashboards/`. |
| Counter / gauge / histogram / summary | `03-metrics/01-metrics-concepts` | (four types) | The three-and-a-half primitives. |
| Cardinality | `03-metrics/01-metrics-concepts` | (rule of thumb: fixed-size enumerations) | Why `batch_id`, `user_id`, paths-with-IDs must NOT be metric labels. |
| Scrape vs push | `03-metrics/01-metrics-concepts` | (two collection models) | OTel collector adapts push-from-app to scrape-by-Prom. |
| OTLP vs Prometheus exposition format | `03-metrics/01-metrics-concepts` | (wire formats) | `_total` suffix convention; `resource_to_telemetry_conversion`. |
| Reading 00 Overview | `03-metrics/02-reading-the-dashboards` | (panel-by-panel) | What each stat / chart means and when it's red. |
| Reading 10 Kafka / 20 Spark / 30 Postgres | `03-metrics/02-reading-the-dashboards` | (same) | Same shape for the system dashboards. |
| "Job duration is a span, not a metric" | `03-metrics/02-reading-the-dashboards` | (callout) | One paragraph explaining why Spark job duration isn't a Prom panel. |
| Don't reach for logs when you wanted metrics | `04-logs/01-logs-concepts` | (load-bearing opening) | The taste-shaping rule. |
| Structured vs unstructured logs | `04-logs/01-logs-concepts` | "JSON formatter" | Always structured in production. |
| Log levels | `04-logs/01-logs-concepts` | (DEBUG/INFO/WARN/ERROR/FATAL) | The five-level scheme; what *not* to do. |
| Label-indexed storage (Loki) | `04-logs/01-logs-concepts` | "stream", "label", "structured metadata" | References `03-metrics/01` cardinality. |
| LogQL anatomy + the five queries | `04-logs/02-querying-logs` | (label selector / line filter / pipeline) | Query language usage. |
| Live tail | `04-logs/02-querying-logs` | "Live tail" | At least one scenario should reference it. |
| Spans / trace_id / parent-child | `05-traces/01-traces-concepts` | (textbook) | Definitions. |
| Trace fragmentation | `05-traces/01-traces-concepts` | "fragmentation across the task-serialization boundary" | Explained once, not three times. |
| Sampling | `05-traces/01-traces-concepts` | "head-based / tail-based" | Mentioned, deferred to Production Patterns. |
| Manual vs auto instrumentation | `05-traces/01-traces-concepts` | "Java agent / manual span" | Cost vs business-semantics tradeoff. |
| Derived field (Loki → Tempo) | `05-traces/02-cross-signal-correlation` | "derived field" | One direction of the cross-signal pivot. |
| `tracesToLogsV2` (Tempo → Loki) | `05-traces/02-cross-signal-correlation` | "tracesToLogsV2" | The other direction. |
| TraceQL primer | `05-traces/02-cross-signal-correlation` | (four queries) | Owned here, not in concepts. |
| spot SparkListener / `job-NNNN` spans | `05-traces/02-cross-signal-correlation` | "spot listener" | **One paragraph maximum.** Mentions it exists, gives Spark-internal spans we don't pivot on; pointer to Production Patterns. |
| Scenario A — producer spike | `06-failure-narratives/01-producer-spike` | (narrative) | Metrics-led; logs confirm. |
| Scenario B — bad data | `06-failure-narratives/02-bad-data` | (narrative) | Logs-led; trace pivot exercised. |
| Scenario C — worker loss | `06-failure-narratives/03-worker-loss` | (narrative) | Metrics-led; logs confirm self-heal; trace claim **must be retuned or reframed** (see narrative spine). |
| Alerting (Alertmanager) | `06-failure-narratives/04-what-we-didnt-show` | (short) | Symptom-based vs cause-based. |
| Sampling (head / tail / exemplars) | `06-failure-narratives/04-what-we-didnt-show` | (short) | Pointer back to `05-traces/01`. |
| Spark UI / History Server | `06-failure-narratives/04-what-we-didnt-show` | (short) | What OTel doesn't replace. |
| OpenLineage | `06-failure-narratives/04-what-we-didnt-show` | (short) | Column-level lineage as complementary signal. |
| Pyroscope / profiling | `06-failure-narratives/04-what-we-didnt-show` | (short) | The fourth-signal mention. |
| Orchestrator-level tracing | `06-failure-narratives/04-what-we-didnt-show` | (short) | Airflow/Dagster/Prefect → Spark trace propagation. |

---

## 3. Terminology decisions (resolve inconsistencies)

| Decision | Force the use of | Drop the use of | Why |
|---|---|---|---|
| Cross-signal identifier | `batch_id` (stringified `e-<N>`) | `b-...` prefix anywhere in prose; `trace_id`-as-pivot framing | Single naming across module; legacy regex still matches but prose shouldn't reference the legacy form. |
| Source of `batch_id` | "derived from Spark's `epoch_id`" | Anything that frames `batch_id` and `epoch_id` as separate concepts | One concept, two names; `batch_id` is what the *pivot* is called, `epoch_id` is the underlying int. |
| Spark unit name | `epoch` (Spark's own word) | `micro-batch id` (use `micro-batch` as a noun is fine; but the *id* is `batch_id` / `epoch_id`, never `micro-batch id`) | Resolves the README↔lab-tour drift. |
| Failure-narrative section title | "Failure Narratives" | "Putting It Together"; "Scenarios" without "Failure Narrative" qualifier | Already done in `myst.yml`; lock it. |
| Stack ownership framing | "Platform / SRE / DevOps team operates the stack; the DE consumes it." | Any longer restatement on multiple pages | Said once in `01-foundations/01`; everywhere else uses a clause like "(see *Why observability* for who owns this)". |
| Contrib distribution mention | One paragraph in `01-foundations/02-pillars-and-stack` | Re-explanation in `03-metrics/01`, `04-logs/01`, anywhere else | Defined once; referenced. |
| The four-pillars and our-stack diagrams | Both live on `01-foundations/02-pillars-and-stack`, as the *only* place they appear | Re-drawing either in later pages | Owning page. |
| Streaming concept dependencies (watermark, structured streaming, `foreachBatch`) | Link out to `materials/streaming/03-streaming/{05-windowing,06-watermarks,...}.md` for the *concept* | Re-teaching watermark or windowed aggregation in monitoring | Monitoring uses these; streaming owns them. |

---

## 4. Scenario payoff matrix (dead-end filter)

Every row in `05-traces/*` must appear in at least one cell of this table, or it gets cut. Same for any non-trivial mechanism in `03-metrics/*` and `04-logs/*`.

| Scenario | Metric signal used | Log signal used | Trace signal used | Pivot mechanism exercised |
|---|---|---|---|---|
| A — Producer spike | `deriv(kafka_partition_current_offset_ratio)` on Overview + Kafka; partition view in `10 Kafka` | `streaming progress … input_rows=` line via LogQL | (none — and that's the point: rates live in metrics+logs) | — |
| B — Bad data | `Schema-drop WARNs (30m)` stat on Overview | WARN line in Loki; `epoch start … bad=1` for batch_id extraction | `etl_batch` span via TraceQL `{ .batch_id = "..." }`; trace shows fast (~600ms) — drop didn't slow pipeline | **Loki → Tempo via derived field; Tempo → Loki via `tracesToLogsV2`** |
| C — Worker loss | Heap chart flat-line on `20 Spark`; `count by (host_name) (increase(jvm_memory_used_bytes[1m]) > 0)` for fresh-samples filter | `epoch done` lines confirming self-heal; absence of `epoch failed` | `etl_batch` duration delta (**weak**: retune trigger to make unambiguous, or reframe as "lets you ask the question") | — |

**Implications for trace-section content (the dead-end test):**

- `etl_batch` manual span → used in B and C → **keep**.
- `batch_id` as span attribute → used in B → **keep**.
- TraceQL `{ .batch_id = "..." }` → used in B → **keep**.
- Derived field (Loki → Tempo) → used in B → **keep**.
- `tracesToLogsV2` (Tempo → Loki) → used in B → **keep**.
- Spot SparkListener / `application` / `job-NNNN` spans → **not used in any scenario** → cut to one paragraph in `05-traces/02-cross-signal-correlation`, with a pointer to Production Patterns ("real teams use SparkListener-based tracing — out of scope here").
- Sampling → not used → mentioned once in concepts, deferred to Production Patterns.
- Two-trace-trees framing → directly motivates the `batch_id` pivot → **keep**, but explained once in `05-traces/01`, not re-explained in `05-traces/02`.

---

## 5. Tone & depth rules

- **Opinionated taste-shaping content goes near the top of its page**, not buried. The "don't reach for logs when you wanted metrics" rule opens `04-logs/01-logs-concepts`. The "trust no aggregate" rule sits early in `01-foundations/01-why-observability`.
- **No meta-history about earlier lab iterations.** No "in an earlier version of the lab we used to…" asides. Instructor trivia, not student-facing.
- **Code cells in scenarios are EITHER executable OR a copy-paste target shown in a fenced block** — never both for the same query, unless the inline form is an explicit sanity-check on the dashboard form (in which case label it as such).
- **One mermaid per concept maximum.** The four-pillars diagram lives on one page. The "our stack" diagram lives on one page. Re-drawing either is a duplication.
- **No "wow moment" oversell.** The phrase appears at most once in the module, in `05-traces/02-cross-signal-correlation`. Anywhere else, describe the mechanism directly.
- **Cross-references use the page's blueprint slug**, not the file path. `(see *The ETL pipeline* for the `batch_id` convention)` survives a rename; `(see 02-lab-tour/02 for...)` doesn't.
- **Bottom of each page = one-sentence handoff to the next.** "Next: how to read the dashboards." No long recap of what was just covered.
- **Page length ceiling ~250 lines.** If a reshape grows a page past that, the blueprint underdrew the structure — split it and update this file.

---

## 6. Forward-reference budget

`01-foundations/*` may name these without defining them — students recognize them or can search:

- Prometheus, Grafana, Kafka, Spark, Postgres (proper nouns)
- "Metric", "log", "trace" (textbook intuition is enough at this stage; precise definitions arrive in sections 3–5)
- "Container", "Docker Compose"
- "Dashboard", "alert" (general meaning)

`01-foundations/*` may **NOT** name without defining:

- Specific OTel collector receivers (`filelog`, `kafkametrics`, `postgresql` receiver) — these belong in `02-pillars-and-stack` only as part of "here's our collector configuration", with a brief gloss
- `batch_id`, `epoch_id`, `__BAD__`, watermark — these belong to lab-tour
- Cardinality, structured metadata, derived field, `tracesToLogsV2`, TraceQL — these belong to the signal sections
- "Spot SparkListener", `job-NNNN` — belong to `05-traces/02` (and minimally)

`02-lab-tour/*` may name without defining: anything `01-foundations/*` owned. Beyond that, lab-tour OWNS `batch_id`, `__BAD__`, the watermark setting, `foreachBatch`, the CLIs.

`03-metrics`, `04-logs`, `05-traces` may name without defining: anything `01-foundations/*` or `02-lab-tour/*` owns. Cross-references between signal sections are allowed *only* when they reference the owning page (e.g. `04-logs/01` may say "the same cardinality rule from metrics applies here — see *Metrics concepts*").

`06-failure-narratives/*` may name without defining: everything taught before it. Scenarios should not re-define concepts; they USE them.

---

## 7. Out of scope (carry-over from plan)

- The structural option of a "first investigation" stub between Lab Tour and Metrics. Interesting; not this rewrite. If a future pass wants it, the spine becomes 12 pages, not 11.
- A dedicated watermarks page. The streaming module owns watermarks; monitoring links out.
- Lab code or dashboard JSON changes. Pure prose-and-structure pass. Exception: the Scenario C trigger retune is a single env-var / CLI argument change, well within scope of the failure-narrative reshape if we go that route.

---

## 8. Reshape order (mirrors plan §The loop)

1. ✅ Blueprint written (this file).
2. `welcome` + `01-foundations/*` reshape → audit.
3. `02-lab-tour/*` reshape → audit.
4. `03-metrics/*` reshape → audit.
5. `04-logs/*` reshape → audit.
6. `05-traces/*` reshape → audit.
7. `06-failure-narratives/01..03` reshape → audit.
8. `06-failure-narratives/04-what-we-didnt-show` reshape → audit.
9. Final read-through; `myst.yml` final state confirmed; site builds.
