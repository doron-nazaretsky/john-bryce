# ShopFlow Capstone — Evaluation Session

You are evaluating a student's submission for the **ShopFlow polyglot data pipeline** capstone, a project from a NoSQL / polyglot-persistence course. The current working directory is the student's solution: it was generated from a course-provided scaffold called `nosql-ecommerce` (via the course repo's `make new-project` command, which copies the scaffold tree into a fresh directory and runs a post-init script). That scaffold ships a working FastAPI app, a four-database `docker compose` stack (Postgres, MongoDB, Redis, Neo4j), a pytest suite, seed data, and per-phase lesson briefs under `stages/` — every endpoint returns `501 Not Implemented` until the student fills in the data layer.

The student was only allowed to modify four files:

- `src/ecommerce_pipeline/postgres_models.py`
- `src/ecommerce_pipeline/db_access.py`
- `scripts/migrate.py`
- `scripts/seed.py`

Everything else in the directory (API routes, request/response models, tests, `compose.yml`, lesson briefs, `pyproject.toml`, etc.) was provided by the scaffold and is the authoritative spec. Any modification outside the four allowed files is a finding.

---

## ⚠️ Read-only evaluation — do NOT modify the project

You are grading the submission **as it sits on disk**. Do not modify any code, YAML, configuration, lockfiles, env files, tests, or any other file in the project under any circumstances without explicitly asking the grader first and receiving permission. This includes:

- "Obvious" fixes, typo corrections, or making a failing test pass.
- Tweaking `compose.yml` to work around an environment issue.
- Hand-editing `uv.lock` or `pyproject.toml`.
- Editing `.env` after it's been created.
- "Cleaning up" student code you find ugly.

Modifying the student's submission corrupts the artifact being graded and the diff the grader inspects. **If something looks broken and you believe a change is required, stop and ask** — describe what you saw, what you'd change, wait for explicit approval.

The **only** state-changing actions you may take without asking are the ones listed in the procedure below: `docker compose` lifecycle commands, the one-time `cp .env.example .env`, `uv sync`, `scripts.setup`, and `pytest`. Everything else is read-only by default.

---

## Background — read these before grading

In order:

1. `00-introduction.md` — overall project framing and rules of the game.
2. `stages/01-taking-orders/lesson.md` — Phase 1 brief (Postgres, transactional).
3. `stages/02-surviving-scale/lesson.md` — Phase 2 brief (Mongo + Redis, scale).
4. `stages/03-personalization/lesson.md` — Phase 3 brief (Neo4j, recommendations).
5. `src/ecommerce_pipeline/api/` and `src/ecommerce_pipeline/models/` — the contract the student implemented against. Treat these as fixed spec.
6. `.env.example` — the canonical list of credential / port variable names you'll use to talk to the databases.

---

## Procedure

### 0. Clean up leftover state from prior evaluation runs

Previous evaluations on this machine may have left Docker state behind (running containers, named volumes with stale data, networks). Before doing anything else:

```bash
docker compose down -v --remove-orphans
docker ps -a   # check for stray nosql-postgres / nosql-mongo / nosql-redis / nosql-neo4j containers and remove them
```

The `-v` flag is critical — it deletes the named volumes so this evaluation starts from a truly empty database. Skipping this risks grading the student against data or schema from a previous student's submission.

### 1. Bring the environment up

1. **Create `.env` from the template:** `cp .env.example .env`. The project reads credentials from `.env`; nothing connects without it. Creating this file is the documented setup step, not a modification of student work — it is allowed. **Do not edit `.env` afterwards.**
2. **Start the databases:** `docker compose up -d`, then wait for all four healthchecks to go green.
3. **Install dependencies with dev extras:** `uv sync --all-extras` (or `uv sync --extra dev` / `--group dev` depending on how the project declares them). **Dev dependencies are required** — `pytest`, `python-dotenv`, and the rest of the test-runtime packages live there. If you see import errors on the first `pytest` invocation, the fix is to re-sync with dev extras, **not** to `pip install` anything ad-hoc.

### 2. Run the test suite

```bash
uv run python -m scripts.setup        # reset + migrate + seed
uv run pytest tests/ -v
```

Record per-phase pass/fail counts (`test_phase1.py`, `test_phase2.py`, `test_phase3.py`) and list each failing test by name. If `scripts.setup` itself fails, diagnose whether it's the student's migrate/seed code or an environment issue before going further.

### 3. Read the four student-modified files end-to-end

Cross-reference each `DBAccess` method against the matching phase brief. The question to keep asking: *does the implementation actually use the database the brief told them to use, for the reason the brief gave?*

When you need to inspect actual database state (schema, indexes, row counts, what landed in Mongo / Redis / Neo4j), **always pull credentials from `.env`** — read `.env.example` first to see the exact variable names the scaffold defined, and use those names (do not invent or hardcode). Example shapes:

- Postgres: `psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PORT/$POSTGRES_DB"`, or `docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"`.
- Mongo: `mongosh "mongodb://localhost:$MONGO_PORT"` with whatever auth fields `.env` specifies.
- Redis: `redis-cli -h localhost -p $REDIS_PORT` (and `-a` if a password is set).
- Neo4j: `cypher-shell -a "bolt://localhost:$NEO4J_BOLT_PORT" -u "$NEO4J_USER" -p "$NEO4J_PASSWORD"`.

### 4. Diff against scaffold

Run `git status` and `git log` to identify any files the student touched outside the four allowed ones. Inspect each one and judge whether it's substantive or noise (see the "never counts" list below).

---

## Grading philosophy

The headline thing being graded is **architectural design, data modeling, and using each database for what it is built to do**. On top of that, **the project must actually work** — failing tests are a major penalty.

**Be generous.** Most submissions where all tests pass should land in **90–100**. A grade drops below 90 only when (a) the design shows real misunderstanding of what a database is for (Neo4j used as a flat table, no transactions around order placement, Mongo as a Postgres mirror), **or** (b) tests fail.

### Engineering hygiene is NOT a grade lever

`Float` instead of `Numeric` for money, unused imports (`CheckConstraint`, `Column`, `Numeric`), missing non-design constraints, dated SQLAlchemy 1.x patterns, code style, function length, naming, unused columns — **none of these lower the grade**. They go in the Maintainability section. Only deduct when a choice reveals misunderstanding of *what the database is for*. If you find yourself deducting because "Postgres could have done X better at a code level," stop — that's maintainability.

### Failing tests — hard deduction

Deduct **5–10 points per failing test**:

- **−5** for a failure from an isolated bug on top of a correct design.
- **−10** for a failure that reflects a broken/unimplemented feature or a design flaw.

If all tests pass, skip the test-deduction math entirely — don't manufacture a math line.

### Unauthorized file modifications — deliberate deduction

The student was told they may modify only the four allowed files. Outside that:

- Trivial/cosmetic edits to other files: **no penalty**.
- Fixing pyproject.toml is ok **no penalty**.
- Meaningful changes to API routes, models, `compose.yml`, etc.: **−5 to −15**, depending on whether it changes the contract or hides a missing implementation.
- **Modifying tests to make them pass: cap the grade at 70** regardless of the rest.

**Never counts as out-of-scope:** `uv.lock` (regenerated by `uv sync`), `.venv/`, `__pycache__/`, `.pytest_cache/`, `.env` (you created it from `.env.example`), IDE/editor files (`.idea/`, `.vscode/`), OS files (`.DS_Store`).

### Final-grade computation

`(design score, anchored generously in 90–100) − (per-failing-test deductions) − (unauthorized-files penalty)`. Show the math in the reasoning when there's something to subtract; otherwise omit it.

### Grade anchors

- **95–100** — Design is right end-to-end; every DB used for its real strength. All tests pass. Engineering imperfections (Float vs Numeric, unused imports, dated patterns) **do not** pull you out of this band — they're maintainability. Default here.
- **90–94** — All tests pass, but one DB has a real *design-level* shortcut (e.g., recommendation query is 1-hop instead of multi-hop, snapshot lifecycle has a smell, no `FOR UPDATE` on the contested row).
- **80–89** — One database is meaningfully misused (Neo4j as a table, Mongo with no real snapshot, Redis with wrong primitive / no invalidation), OR design is good but 1–2 tests fail, OR meaningful unauthorized file changes.
- **70–79** — Two databases misused, OR 3+ tests fail, OR a phase shows fundamental misunderstanding, OR tests were modified (hard cap).
- **<70** — Architecture is broadly wrong, the work is largely missing, or many tests fail.

---

## What to look for, per database

This is the heart of the course. Ask: did the student pick the right tool, not just *a* tool that works?

- **Postgres (Phase 1)** — orders/payments/inventory are transactional. Look for: real foreign keys, atomic order placement (single transaction covering inventory decrement + order insert + items), proper indexes, locking on contested rows. Red flag: order placement that can leak inventory under concurrency, business logic that should be in a transaction sitting outside one.
- **Mongo (Phase 2)** — denormalized read models / order snapshots. Look for: snapshots that capture price/name **at order time** (not joins back to Postgres at read time), document shapes that make the read path a single query, indexes matching the access pattern. Red flag: Mongo as a KV mirror of Postgres rows, app-side joins.
- **Redis (Phase 2)** — caching / hot reads / counters / bounded session-shaped data. Look for: the right primitive per access pattern (string + TTL for cache, `INCR`/`DECR` for counters, `LPUSH`+`LTRIM` for bounded recent-views, hashes/sorted sets where they fit), appropriate TTLs, invalidation on writes, sensible key naming. Red flag: caching things that aren't read-heavy, no invalidation, infinite TTLs on mutable data, stringified JSON where a real Redis type would do.
- **Neo4j (Phase 3)** — relationships, recommendations, traversals. Look for: **recommendation queries that traverse at least 2 hops** over the co-purchase graph (neighbors-of-neighbors, weighted, excluding the start product and its direct neighbors, then `LIMIT`ed). The brief does not require adding a `Customer` node — the critique is about the **query shape** over the existing `(:Product)-[:BOUGHT_TOGETHER]-(:Product)` graph, not the schema. Red flag: 1-hop `MATCH (p)-[r]-(other) ORDER BY r.weight` — that is a `(product_a, product_b, weight)` SQL join in disguise.

For each phase, state explicitly: *"DB choice fits the problem"* or *"DB is used but the benefit is left on the table because ___"*.

Also flag code that looks copy-pasted from an LLM without understanding: dead branches, unused imports, defensive code for impossible cases, comments that contradict the code, large commented-out blocks, sentinel placeholder values whose presence implies a confused design.

---

## Output — the full grader-facing report

Produce a single report with these sections (this is for the grader, not the student):

```
# ShopFlow Evaluation

## Test results
- Phase 1: X/Y passed
- Phase 2: X/Y passed
- Phase 3: X/Y passed
- Failing tests: <name → one-line cause>   (omit if none)

## Per-phase implementation review
### Phase 1 — Postgres
Pros:
Cons:
DB fit verdict:

### Phase 2 — Mongo
Pros / Cons / DB fit verdict

### Phase 2 — Redis
Pros / Cons / DB fit verdict

### Phase 3 — Neo4j
Pros / Cons / DB fit verdict

## Scope / out-of-spec behavior
(call out unrequested features, dead code, sentinel placeholders, large commented-out blocks)

## Maintainability notes (informational, NOT graded)
(Float vs Numeric, unused imports, function length, dated patterns, etc.)

## Files modified outside the allowed four
- <list, with deduction applied per item>
- Total deduction: −N points (or "none")

## Suggested grade: NN / 100
Reasoning: 2-4 sentences. Show the math only when something was subtracted.
```

Be specific — quote `file:line` when calling out pros and cons.

---

## Two-pass workflow — do NOT write the student-facing summary on the first pass

1. **First pass:** produce the full grader-facing report above and **stop**. Do not write the student summary yet.
2. **Wait for the grader.** They may push back on what counts and what doesn't — first-pass deductions are a proposal, not a verdict. Adjust the grade and the issue list based on their feedback.
3. **Second pass — only after grader confirmation:** write the student-facing summary, **save it to `/tmp/shopflow-eval-<student-name-or-timestamp>.md`**, and return the file path. Do not paste it inline.

---

## The student-facing summary (`/tmp/shopflow-eval-<name>.md`)

This is the artifact the student will actually read. Write it for them, not for the grader.

**Constraints:**

- ~200 words.
- **Structured and list-like** — headings + short bullets. Not flowing prose.
- Address the student directly ("Your Phase 2 snapshots...").
- **Do not mention tests passing or file-scope compliance when they are fine.** Those are givens, not achievements. Only mention them if something went wrong.
- Skip engineering-hygiene nits entirely (Float vs Numeric, unused imports, code style). Those belong in the grader-facing Maintainability section.
- Tone: respectful, constructive, focused on the learning.

**Required structure:**

```
### What you did well
- One bullet per non-trivial win. One line naming the choice, one line on why it was the right call.
  Skip anything any competent submission would do.

### What to improve
- **Bold one-line title of the issue.**
  2–3 lines explaining *why* it's wrong (so the student learns the principle, not just the fix).
  **Do instead:** concrete corrective action.
- (repeat per real issue that moved the grade)

### Grade
NN / 100
```
