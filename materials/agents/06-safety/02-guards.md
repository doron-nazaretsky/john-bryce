---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# Guardrails beyond the system prompt

The system prompt and the read-only DB role were the first two layers. There are three more an agent on real infrastructure should have:

1. **A SQL allowlist at the tool layer.** Catch destructive intent before it leaves your process.
2. **Iteration caps** (we used `max_turns` throughout). Bound the worst case.
3. **Result-size caps.** Bound the cost of a single tool call.

This lesson walks each in code and explains when to use them.

## Layer 3: SQL allowlist in the `run_sql` tool

The read-only role at the DB is the strongest layer — it does not trust anything, including a hypothetical bug in our code. But there are good reasons to also block destructive SQL inside the tool itself:

- Early, clear errors the model can react to (vs. a DB permission-denied message).
- Cheaper failure (no round-trip to Postgres).
- Belt-and-braces against future code changes that accidentally widen the role.

The minimum-viable version is a keyword check, with the right caveats:

```{code-cell} python
import re, json

FORBIDDEN_KEYWORDS = ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "TRUNCATE ",
                      "ALTER ", "CREATE ", "GRANT ", "REVOKE ", "COMMIT ", "ROLLBACK ")

def is_destructive(query: str) -> bool:
    """Best-effort destructive-statement check. NOT a security boundary.
    Real security is the DB role; this is for early/clean errors only."""
    # Strip comments to defeat the easiest evasion attempts.
    no_block_comments = re.sub(r"/\*.*?\*/", " ", query, flags=re.DOTALL)
    no_line_comments = re.sub(r"--[^\n]*", " ", no_block_comments)
    upper = " " + no_line_comments.upper() + " "
    return any(kw in upper for kw in FORBIDDEN_KEYWORDS)

samples = [
    "SELECT * FROM film",
    "select count(*) from film",
    "DROP TABLE customer",
    "delete from rental where rental_id < 100",
    "SELECT * FROM film /* DROP TABLE customer */",        # DROP is in a comment, not real
    "SELECT * FROM film -- DROP TABLE",                     # same — comment, not real
    "WITH cte AS (DELETE FROM rental RETURNING *) SELECT 1", # real DELETE inside a CTE
]
for q in samples:
    print(f"  destructive={is_destructive(q)!s:<5} | {q}")
```

A blunt keyword check is **not** a security boundary — a determined attacker who controls the query string can find evasions (Unicode tricks, exotic syntax). That is what the DB role is for. The allowlist's job is to fail fast on common cases the model would generate by mistake. Don't reach for SQL parsers; reach for the next layer of defense.

## Layer 4: iteration caps

Every loop in this module had `max_turns`. That was not decoration — it is the hard bound on how badly a confused agent can spend your money in one user request:

```python
# rough cost ceiling per user question
worst_case_cost ≈ max_turns × tokens_per_turn × $/token
```

What value to pick?

- **High-throughput consumer agents** (chatbots): 6–10 turns. Anything longer hints at a bad question, and giving up gracefully is better than continuing.
- **Internal analytics agents** (the kind we built): 12–15. Three-way joins genuinely take a few discovery calls.
- **Long-running workflow agents** (planners): 25+ — but at that scale you should also have **checkpointing**, so a stuck agent can be resumed instead of restarted.

If you find yourself wanting `max_turns = 50` for a single user request, something else is wrong — usually the system prompt or the tool catalog.

## Layer 5: result-size caps

We already capped `run_sql` at 50 rows. That stops one runaway query from putting 10,000 rows into history and inflating every subsequent turn. The cap should match what the model can productively process — which is much smaller than what fits in the context window.

The pattern, generalized:

```{code-cell} python
def cap_result(result: str, max_chars: int = 4000) -> str:
    if len(result) <= max_chars:
        return result
    return result[:max_chars] + f"\n... [truncated; original was {len(result)} chars]"

print(cap_result("a" * 50))
print(cap_result("a" * 6000)[-80:])
```

Two design notes:

- **Mention the truncation** in the marker. Otherwise the model thinks the data ended naturally and may report incomplete results as complete.
- **Truncate at the tool layer**, not just at display time. Truncating in display lets the full bloat into history; only tool-layer truncation actually saves tokens.

## Putting it together — the safe `run_sql`

The production-grade `run_sql` accumulates everything from blocks 04 and 06:

```python
def run_sql(query: str, *, max_rows: int = 50, max_chars: int = 4000) -> str:
    # Layer: tool-layer allowlist
    if is_destructive(query):
        return json.dumps({"error": "destructive SQL is not allowed",
                           "hint": "use SELECT only — this DB is read-only"})
    try:
        with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
            cur.execute(query)
            if cur.description is None:
                return json.dumps({"error": "no result set", "hint": "use a SELECT statement"})
            cols = [d.name for d in cur.description]
            rows = cur.fetchmany(max_rows)
            truncated = (cur.fetchone() is not None)
            safe = [[str(v) if v is not None else None for v in r] for r in rows]
            result = json.dumps({"columns": cols, "rows": safe, "truncated": truncated})
            return cap_result(result, max_chars=max_chars)
    except Exception as e:
        return json.dumps({"error": type(e).__name__, "message": str(e),
                           "hint": "fix the SQL and try again; check column names with describe_table"})
```

Five layers of defense in 25 lines:

| Layer | Where | What it stops |
|---|---|---|
| 1. System prompt | Agent | Most model-side mistakes; injection from tool output |
| 2. DB role | Database | Anything that bypasses 1–3 |
| 3. SQL allowlist | Tool | Early, clean errors on destructive intent |
| 4. `max_turns` | Loop | Runaway loops, unbounded cost |
| 5. Row/char cap | Tool | Bloated context window, bloated bill |

You almost never need all five for every tool — pick the ones that match the tool's blast radius.

## What we just learned

- A SQL allowlist in the tool catches destructive intent early; it's a cost/UX layer, not a security boundary.
- `max_turns` is the cheap budget cap; pick it to match the work, not the worst case.
- Result-size caps stop one big query from making every following turn expensive.
- Defense in depth is the discipline: five small, cheap checks compose to something hard to break.

Next block: enriching the data agent with unstructured knowledge via vector search.
