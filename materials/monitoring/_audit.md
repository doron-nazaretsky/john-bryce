# Monitoring Module — Audit Log

> One entry per section reshape. Append-only within a turn; do not edit previous entries except to mark deferred items resolved.

## Audit after writing the blueprint

- **Duplications found**: (see blueprint §2 concept ledger for the canonical assignments; the editorial review documented duplications across `batch_id`, platform-team ownership, contrib distribution, dashboard nav, cardinality, trace fragmentation, the "wow moment" phrasing.)
- **Forward refs found**: section 1 currently names `filelog` / `kafkametrics` receivers and contrib failure modes; the blueprint's §6 forward-reference budget resolves this — collapse those into the merged `01-foundations/02-pillars-and-stack` only as part of "here's our config".
- **Inconsistencies found**: `micro-batch` vs `epoch`; `batch_id` framed as "Spark epoch stringified" in one page and "business identifier" in another. Resolved by blueprint §3 terminology decisions.
- **Dead ends found**: spot SparkListener `job-NNNN` material is taught at length in `05-traces/02-the-traces-pipeline.md` but never used by any scenario. Blueprint §4 scenario payoff matrix confirms cut-to-one-paragraph.
- **Actions taken this turn**:
  - Wrote `_blueprint.md` with narrative spine, concept ledger, terminology decisions, scenario payoff matrix, tone rules, forward-reference budget.
  - Seeded this audit log.
  - (To do this turn or next: add `_blueprint.md` and `_audit.md` to `myst.yml` exclude list so they don't enter the site.)
- **Actions deferred to later page rewrites**:
  - All concrete rewrites — the blueprint is the only artifact produced this turn.
  - Scenario C trace-payoff retune (or reframe) — deferred to `06-failure-narratives/03-worker-loss` reshape.
  - File renames + `myst.yml` TOC update — happen incrementally inside each section's reshape turn.

## Audit after reshaping welcome + 01-foundations

- **Duplications resolved**: platform-team-ownership now stated once in `01-foundations/01-why-observability` (was in README + 01-why + 02-four-pillars + 03-stack-tour). Four-pillars diagram and the 10-container table now appear only on `01-foundations/02-pillars-and-stack` (was split across two pages with overlap). OTel SDK-vs-Collector clarification stated once.
- **Forward refs resolved**: `filelog` / `kafkametrics` / `postgresql` receivers are no longer named in section 1; only the *category* "contrib distribution" appears, with the specific receiver names deferred to `02-lab-tour` and signal sections.
- **Inconsistencies resolved (so far)**: README's "Three Failure Narratives" subsection that re-defined `batch_id` is gone (welcome page has no concept content). The "honest framing — trace fragmentation" subsection from README is gone; fragmentation will live exclusively in `05-traces/01-traces-concepts`.
- **Dead ends**: none introduced. The Tool Table that lived at the bottom of the old `03-stack-tour.md` (mentioning `producer rate`, `inject-bad`, `docker kill`) is dropped; that content belongs on `02-lab-tour/02-the-etl-pipeline`.
- **Actions taken this turn**:
  - Rewrote `README.md` as pure orientation (welcome page).
  - Created `01-foundations/01-why-observability.md` (cut "Three Failure Narratives", "Honest Framing", "Stack At A Glance" from old README; absorbed unique content from old `01-why-observability.md`).
  - Created `01-foundations/02-pillars-and-stack.md` (merged old `02-the-four-pillars.md` + `03-stack-tour.md`).
  - Deleted old `01-introduction/` directory.
  - Updated `myst.yml` TOC.
- **Actions deferred to later page rewrites**:
  - `02-lab-tour/02-the-etl-pipeline` must own: `batch_id` convention, `__BAD__` placeholder, watermark setting, `foreachBatch`, lab CLIs (now no longer defined anywhere).
  - `02-lab-tour/03-grafana-orientation` keeps the dashboard nav rule (already removed from elsewhere; just confirm no re-introduction).
  - `04-logs/01-logs-concepts` keeps the cardinality cross-reference back to `03-metrics/01`.
  - `05-traces/01-traces-concepts` is the sole owner of trace fragmentation now.

## Audit after reshaping 02-lab-tour

- **Duplications resolved**: `batch_id` convention now defined exclusively in `02-lab-tour/02-the-etl-pipeline` (was also in README + welsewhere). The `__BAD__` mechanism is now defined here on the lab-tour page rather than being introduced inline in Scenario B.
- **Forward refs resolved**: watermark setting links out to `materials/streaming/.../06-watermarks.md` rather than re-teaching the concept here.
- **Inconsistencies resolved**: `epoch` is now the term for the Spark unit (not "micro-batch" alone); `batch_id` is described as "derived from `epoch_id`" with a single forced framing.
- **Dead ends**: none introduced. The "Note on the long-running daemon" meta-history about earlier iterations was cut from `01-bring-up-the-lab`.
- **Actions taken this turn**:
  - Rewrote `01-bring-up-the-lab.md` (removed meta-history aside, updated container count to 10, tightened smoke test).
  - Renamed `03-the-etl-pipeline.md` → `02-the-etl-pipeline.md` (now the canonical home for `batch_id`, `__BAD__`, watermark setting, lab CLIs).
  - Renamed `02-grafana-orientation.md` → `03-grafana-orientation.md`. Already recently rewritten; no content edits this turn.
  - Updated `myst.yml` TOC ordering.
- **Actions deferred to later page rewrites**:
  - `03-metrics/02-reading-the-dashboards`: remove the "When to leave Overview" decision table (blueprint says it lives only on `02-lab-tour/03-grafana-orientation`).
  - `04-logs/01-logs-concepts`: cross-reference `03-metrics/01-metrics-concepts` for cardinality (don't redefine).
  - `06-failure-narratives/02-bad-data`: do not redefine `__BAD__`; reference the lab-tour page.

## Audit after reshaping 03-metrics

- **Duplications resolved**: "Why we use the contrib distribution" (and the example error message) is gone from the metrics section; it lives only on `01-foundations/02-pillars-and-stack`. The "When to leave Overview" decision table is removed from this section (lives only on `02-lab-tour/03-grafana-orientation`).
- **Forward refs resolved**: the in-our-lab section now cross-references `01-foundations/02-pillars-and-stack` rather than re-explaining the topology.
- **Inconsistencies resolved**: `batch_id` is named here as an example of what *not* to put on a metric (taste-shaping callout), citing the lab-tour page for what it *is*.
- **Dead ends**: none.
- **Actions taken this turn**:
  - Rewrote `01-metrics-concepts.md` to fold a short "in our lab" section into the concepts page (the wiring is referenced, not re-explained).
  - Deleted standalone `02-the-metrics-pipeline.md`.
  - Renamed `03-reading-the-dashboards.md` → `02-reading-the-dashboards.md`, lightly trimmed (removed the "when to leave Overview" table — duplicate with `02-lab-tour/03`; opened with a pointer to the orientation page).
  - Updated `myst.yml` TOC.
- **Actions deferred to later page rewrites**:
  - `04-logs/01-logs-concepts`: fold pipeline wiring into a short "in our lab" section (same pattern as metrics).
  - `05-traces/02-cross-signal-correlation`: similar fold for the trace pipeline.

## Audit after reshaping 04-logs

- **Duplications resolved**: the cardinality discussion is now a one-clause cross-reference to `03-metrics/01-metrics-concepts`, not a re-derivation. The Loki pipeline configuration (filelog receiver, json_parser operator, shared volume) is folded into a 3-paragraph "in our lab" section rather than a full standalone page.
- **Forward refs resolved**: `batch_id` referenced not redefined (cites `02-lab-tour/02-the-etl-pipeline`). The derived-field mechanism is shown here as a teaser; the full bidirectional pivot lives in `05-traces/02-cross-signal-correlation`.
- **Inconsistencies resolved**: log examples now use `e-42` consistently (replaced the lingering `b-20260520-...` legacy form). All "batch start"/"batch done" wording flipped to "epoch start"/"epoch done" to match the actual log emission and the terminology decision.
- **Dead ends**: none.
- **Actions taken this turn**:
  - Rewrote `01-logs-concepts.md` with the "don't reach for logs when you wanted metrics" rule promoted to the opening; cardinality cross-referenced; pipeline folded into a short "in our lab" section.
  - Deleted `02-the-logs-pipeline.md`.
  - Renamed `03-querying-logs-in-grafana.md` → `02-querying-logs.md`; tightened, dropped the "wow moment" oversell phrase (reserved for `05-traces/02`).
  - Updated `myst.yml` TOC.
- **Actions deferred to later page rewrites**:
  - `05-traces/01-traces-concepts`: only owner of trace fragmentation and sampling.
  - `05-traces/02-cross-signal-correlation`: spot SparkListener content reduced to one paragraph with pointer to `04-what-we-didnt-show`.

## Audit after reshaping 05-traces

- **Duplications resolved**: trace fragmentation is now explained exactly once on `01-traces-concepts` (was previously framed defensively three times — in README, in the concepts page, and again in the pipeline page). The two-trace-trees framing is on the concepts page; cross-signal correlation page references it instead of re-explaining.
- **Forward refs resolved**: the cross-signal correlation page references `01-traces-concepts` for fragmentation and `04-what-we-didnt-show` for SparkListener-based patterns.
- **Inconsistencies resolved**: `batch_id` consistently described as the **business identifier**, not "Spark epoch stringified". The "wow moment" phrasing appears only here, once, as planned.
- **Dead ends**: **resolved**. The spot SparkListener / `job-NNNN` material is reduced from ~80 lines of detailed pipeline content to one paragraph noting it exists and pointing readers at `04-what-we-didnt-show`. The TraceQL primer survives because Scenario B uses it.
- **Actions taken this turn**:
  - Rewrote `01-traces-concepts.md` as the sole owner of fragmentation, sampling, manual-vs-auto framing; folded the trace-pipeline wiring into a short "in our lab" section.
  - Deleted `02-the-traces-pipeline.md`.
  - Renamed `03-correlation-across-signals.md` → `02-cross-signal-correlation.md`; tightened (kept derived-field, tracesToLogsV2, TraceQL primer, business-identifier framing); reduced spot to one paragraph.
  - Updated `myst.yml` TOC.
- **Actions deferred to later page rewrites**:
  - `06-failure-narratives/01..03`: remove inline re-definitions of `batch_id`, derived field, TraceQL — reference the owning pages.
  - `06-failure-narratives/03-worker-loss`: decide between retuning the trigger and reframing the trace claim.
  - `06-failure-narratives/04-what-we-didnt-show`: must own the SparkListener-based-tracing topic since `05-traces/02` now points there.

## Audit after reshaping 06-failure-narratives/01..03

- **Duplications resolved**: Scenario B's inline explanation of `__BAD__` is replaced with a one-clause cross-reference to `02-lab-tour/02-the-etl-pipeline`. The derived-field mechanism is referenced (not re-explained) — pointer to `05-traces/02-cross-signal-correlation`. The closing-bullet sentence about `batch_id` vs `trace_id` is now a pointer rather than a re-derivation.
- **Forward refs resolved**: every concept used in the scenarios is either named earlier or referenced to its owning page.
- **Inconsistencies resolved**: directory renamed `06-putting-it-together` → `06-failure-narratives` to match the blueprint slug and the TOC section title. Scenario C trace claim is **reframed**, not retuned — the prose now says "traces let you ask the question" with a body matched to the lab's actual baseline load.
- **Dead ends**: none introduced. The Scenario C reframe means the trace section in C now stands on its own claim rather than depending on a hedge.
- **Actions taken this turn**:
  - Renamed directory `06-putting-it-together/` → `06-failure-narratives/`.
  - Updated `myst.yml` paths accordingly.
  - Trimmed Scenario B: `__BAD__` redefinition cut; derived-field mechanism reference added; closing bullets point to owning pages.
  - Rewrote the Scenario C trace-analysis section (replaced the "small but measurable" hedge with the reframed claim).
  - Scenario A left as-is (no redefinitions to remove).
- **Actions deferred to later page rewrites**:
  - `04-what-we-didnt-show`: must explicitly cover SparkListener-based tracing (`05-traces/02` points there).

## Audit after reshaping 04-what-we-didnt-show

- **Duplications resolved**: Section is now a *curated* further-reading map, not a grab-bag. Each topic gets a clear shape: what it is, when you'd reach for it, where to read more.
- **Forward refs**: `05-traces/02-cross-signal-correlation` and `05-traces/01-traces-concepts` are cited as the places the topics were first mentioned.
- **Inconsistencies**: removed phrases like "If you're doing this in your team:" and "Real teams *also* run the Spark History Server — …" that drifted toward tutorial register; the page now keeps a consistent tone with the rest of the module.
- **Dead ends**: SparkListener-based tracing now has an explicit owning page (here), satisfying the pointer that `05-traces/02` makes. No new dead ends introduced.
- **Actions taken this turn**:
  - Renamed `04-production-patterns.md` → `04-what-we-didnt-show.md`.
  - Rewrote the file as a tighter, structured reference; sections: Alerting, Sampling, SparkListener tracing, Orchestrator tracing, Spark UI, Profiling, OpenLineage, Where to go next.
  - `myst.yml` already updated in step 7 to point at the new filename.
- **Actions deferred**: none — this is the last section reshape.

## Final whole-module audit (step 9)

Validation against blueprint §verification.

**1. Concept ledger discipline.**
- `grep "batch_id"` shows the owning page (`02-lab-tour/02-the-etl-pipeline`, 7 hits — the definition site) and downstream pages use it heavily (cross-signal-correlation: 19, scenarios: 16; expected, since they USE it). No page outside the owning page contains a *definition* of the convention. ✅
- `grep "__BAD__"` shows definition on `02-lab-tour/02-the-etl-pipeline`; Scenario B cross-references via inline link instead of redefining. ✅
- `grep "contrib distribution"` confined to `01-foundations/02-pillars-and-stack` (the owning page); no re-explanation downstream. ✅
- Platform-team ownership: README has a one-paragraph welcome teaser; `01-foundations/01-why-observability` is the owning page; no third repetition. ✅
- Trace fragmentation: only mentioned by name in `05-traces/01-traces-concepts` (owner) and in the README learning-path table (one-word topic tag, not a definition). ✅

**2. No forward refs into section 1.**
- Only `kafkametrics` / `postgresql` / `filelog` mention in section 1 is the one-clause naming on `01-foundations/02-pillars-and-stack` as examples of contrib-only receivers — allowed by §6 forward-reference budget. ✅
- No use of `batch_id`, `__BAD__`, watermark, derived field, `tracesToLogsV2`, TraceQL, spot SparkListener, or cardinality in section 1. ✅

**3. Scenario payoff matrix dense.**
- Every concept kept in `05-traces/*` appears in at least one scenario column (etl_batch span, TraceQL `{ .batch_id = ... }`, derived field, tracesToLogsV2). Spot SparkListener was cut to one paragraph and re-located to `04-what-we-didnt-show` — the dead-end test passes. ✅

**4. Audit log closed.**
- Every "Actions deferred" item from earlier audit entries was addressed in the section it was deferred to:
  - "When to leave Overview" table removed from `03-metrics/02` (deferred from step 3 → done in step 4). ✅
  - Cardinality cross-reference from `04-logs/01` to `03-metrics/01` (deferred from step 3 → done in step 5). ✅
  - `__BAD__` not redefined in Scenario B (deferred from step 3 → done in step 7). ✅
  - Pipeline-into-concepts fold for logs (deferred from step 4 → done in step 5). ✅
  - Pipeline-into-concepts fold for traces (deferred from step 5 → done in step 6). ✅
  - Scenario C trace-claim decision (deferred from step 6 → reframed in step 7). ✅
  - SparkListener content owned by `04-what-we-didnt-show` (deferred from step 6 → done in step 8). ✅

**5. Read-aloud test (TOC order: README → 01 → 02 → 03 → 04 → 05 → 06).**
- No paragraph appears twice across sections.
- No term used before defined in concept ledger order.
- No tool taught and then never used (spot is now flagged as "we don't pivot on it"; `LoggingInstrumentor` is noted as deliberately off).
- "Wow moment" appears exactly once, in `05-traces/02-cross-signal-correlation` (fixed during step 9 by removing the second mention from `01-foundations/02-pillars-and-stack`). ✅

**6. Cross-check against editorial review.**
- Platform-ownership 4× duplication → resolved (now 2 sites, one welcome teaser + one owning page; complies with blueprint).
- `batch_id` 4× duplication → resolved (defined once on `02-lab-tour/02-the-etl-pipeline`).
- Contrib distribution 2× duplication → resolved (single owning page).
- Cardinality 2× duplication → resolved (`04-logs/01` cross-references metrics).
- Dashboard nav rule 2× duplication → resolved (table removed from metrics dashboards page).
- Forward refs into section 1 → resolved (only the allowed brief gloss remains).
- Spot dead-end → resolved (cut to one paragraph + owning page in `04-what-we-didnt-show`).
- Watermark assumed-not-taught → resolved (lab-tour links to streaming module).
- `__BAD__` introduced inside scenario → resolved (now on `02-lab-tour/02`).
- `epoch` vs `micro-batch` inconsistency → resolved (terminology decision locked).
- Loki "Don't reach for logs when you wanted metrics" buried → resolved (now opens `04-logs/01-logs-concepts`).
- Meta-history in `02-lab-tour/01` → resolved (cut).
- `04-production-patterns` grab-bag → resolved (restructured as `04-what-we-didnt-show` with per-topic shape).
- Scenario C hedge → resolved (reframed, not retuned).

**Page-length budget.** All 15 student-facing pages between 30 and 126 lines; well under the 250-line ceiling. Total module length 1411 lines, down from ~1800+.

**Final shape.**

```
README.md (welcome, 30 lines)
01-foundations/
  01-why-observability.md
  02-pillars-and-stack.md
02-lab-tour/
  01-bring-up-the-lab.md
  02-the-etl-pipeline.md
  03-grafana-orientation.md
03-metrics/
  01-metrics-concepts.md
  02-reading-the-dashboards.md
04-logs/
  01-logs-concepts.md
  02-querying-logs.md
05-traces/
  01-traces-concepts.md
  02-cross-signal-correlation.md
06-failure-narratives/
  01-scenario-producer-spike.md
  02-scenario-bad-data.md
  03-scenario-worker-loss.md
  04-what-we-didnt-show.md
```

15 student-facing pages (down from 19), 6 sections, every concept has exactly one owning page, every named tool is used downstream.

**Status: done.**
