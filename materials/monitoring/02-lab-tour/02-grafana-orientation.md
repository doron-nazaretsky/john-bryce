# Orienting Yourself in Grafana

Open http://localhost:3001. No login. The lab is configured with `anonymous role = Admin`, so you have full read/write access without typing a password.

If you accidentally bookmarked the login page from a previous Grafana install, you'll land on a login screen — just nuke the cookie or use a fresh browser window.

## The sidebar

The left sidebar (hamburger icon if collapsed) has the items you'll use:

| Item | What it's for |
|---|---|
| **Home** | The default Grafana welcome page. Ignore. |
| **Dashboards** | The 5 pre-provisioned dashboards for this lab. |
| **Explore** | Ad-hoc queries against any datasource. **You will live here.** |
| **Connections → Data sources** | Read-only view of the three datasources (Prometheus, Loki, Tempo). |
| **Alerting** | Empty. The lab has no alert rules — production patterns covers them in section 6. |

The "wow moments" of the lab — jumping from a log line to its trace — happen in **Explore**, not Dashboards.

## The five dashboards

Open **Dashboards** in the sidebar. You'll see five entries, prefixed by number for stable sort order:

- **00 · Overview** — single screen, no scrolling. The first thing you open when something seems off.
- **10 · Kafka** — broker / partition / consumer lag in detail.
- **20 · Spark** — JVM heap, GC, executor count, CPU per role.
- **30 · Postgres** — sink write rate, row count growth, cache hit ratio, commits vs rollbacks.
- **40 · ETL Business** — domain-level: batch outcome bars, dropped records, full log stream.

We'll come back to each dashboard in section 3, after you have the metrics concepts to read them.

### Investigation pattern

The dashboard numbers are not arbitrary — they encode an investigation order. **Start at 00.** If the overview says something is wrong (failed batches, lag climbing, write rate dropped), the stat panel's color tells you which system-level dashboard to open next:

```
00 Overview (always start here)
    │
    ├── lag climbing      →  10 Kafka      (which partition? consumer side?)
    ├── batches failing   →  40 ETL        (what does the log say?)
    ├── writes dropped    →  30 Postgres   (rollbacks? cache hit?)
    └── JVM heap > 80%    →  20 Spark      (which executor? GC time?)
```

This pattern — "overview tells you which dashboard to open next" — is the production model. Real teams call it "RED method" (Rate, Errors, Duration) or "USE method" (Utilization, Saturation, Errors). The dashboards here implement the same idea for our pipeline shape.

## Explore — the ad-hoc query view

Click **Explore** in the sidebar. At the top there's a datasource picker:

- **Prometheus** for `kafka_consumer_records_lag`, `jvm_memory_used_bytes`, etc.
- **Loki** for log queries with LogQL.
- **Tempo** for trace lookups with TraceQL.

The query editor changes per datasource. We'll teach the syntax for each in their respective sections (3 for PromQL, 4 for LogQL, 5 for TraceQL).

A few Explore features worth knowing now:

- **Split view** (top-right): see two datasources side by side. Useful for "log line on the left, the trace on the right".
- **Live tail** (Loki only): watch new log lines as they arrive, no refresh needed.
- **Time picker** (top-right): defaults to "last 1 hour". When investigating a specific batch, pin to a tight window first.
- **Run query shortcut**: Cmd-Enter (Mac) / Ctrl-Enter.

## Refresh + time picker

Dashboards default to a 10–15 second auto-refresh. The refresh interval is shown in the top-right of each dashboard; you can change it or set to off if you want a static view.

The time picker controls the window all panels in the dashboard look at. Default is "last 30 minutes" on most, "last 1 hour" on 40 ETL Business. **Set this aggressively when investigating** — looking at the wrong time window is the most common reason "the panel is empty".

## Dark mode

The lab provisions dashboards with dark mode hint (`style: dark`), and the Grafana container env sets `GF_USERS_DEFAULT_THEME=dark`. If yours looks light, click your avatar at the bottom-left → Preferences → Theme = Dark.

Colors used throughout:

- **Green** (semi-dark) — success, healthy, "this is doing its job".
- **Yellow / amber** — caution, attention but not yet failure.
- **Red** (semi-dark rose) — failure, exhausted, broken.
- **Blue** — informational, neutral, cumulative.

These are Grafana's `semi-dark-*` palette — muted to look at home on a dark background without burning your eyes during a 4-hour session.

Next: a closer look at the ETL pipeline you'll be observing.
