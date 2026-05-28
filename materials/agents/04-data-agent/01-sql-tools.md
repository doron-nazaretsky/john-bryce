---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# Three tools to talk to a database

The principle from block 02 was: **one tool per conceptual action**. For a SQL agent, the smallest set that lets the model answer arbitrary questions on a schema it has not memorized is three tools:

| Tool | What it does | Why the agent needs it |
|---|---|---|
| `list_tables` | Returns the names of base tables in `public` | The model has to know what tables exist before it can query them |
| `describe_table` | Returns columns + types for one table | The model has to know the column names and types before it can write a SELECT |
| `run_sql` | Executes a read-only SQL statement and returns rows | The model has to actually retrieve the answer |

That is it. With these three the model can answer any question Pagila supports — by first discovering the schema, then writing a query. We will spend this lesson implementing them.

## A read-only connection

The `run_sql` tool will run **model-generated SQL**, which is exactly the kind of code you do not want to grant write privileges to. We will use a read-only Postgres role for the connection. We create it once, here:

```{code-cell} python
import os, psycopg

ADMIN_URL = os.environ["DATABASE_URL"]   # postgres user, full access

with psycopg.connect(ADMIN_URL, autocommit=True) as conn, conn.cursor() as cur:
    # Idempotent: create the role only if it doesn't exist, then re-grant.
    # Re-running this cell on top of an existing role is safe.
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_ro') THEN
                CREATE ROLE agent_ro LOGIN PASSWORD 'agent_ro';
            END IF;
        END$$;
        GRANT CONNECT ON DATABASE pagila TO agent_ro;
        GRANT USAGE ON SCHEMA public TO agent_ro;
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_ro;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO agent_ro;
    """)

AGENT_URL = ADMIN_URL.replace("postgres:postgres@", "agent_ro:agent_ro@")
print("Agent DB URL (read-only):", AGENT_URL)
```

This is the kind of guardrail block 06 (safety) treats in depth. For now, just know: the agent connects as `agent_ro`. Any `INSERT`, `UPDATE`, `DELETE`, or `DROP` the model writes will fail at the database, regardless of what the loop does.

## Tool 1 — list_tables

```{code-cell} python
import json
import psycopg

def list_tables() -> str:
    """Return a JSON array of base table names in the public schema."""
    with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
              AND table_name NOT LIKE 'payment_p%'
            ORDER BY table_name;
        """)
        names = [row[0] for row in cur.fetchall()]
    return json.dumps(names)

print(list_tables())
```

A few decisions in there:

- We **return a JSON string**, not a Python list — tool results have to be strings the model can read. JSON is the safest choice when the data is structured.
- We **filter out partition children** (`payment_p%`). The model would otherwise see 30+ tables of which 20 are noise, and might pick the wrong one.
- The tool is **completely parameterless**. No knobs the model could turn — easy to call, hard to misuse.

## Tool 2 — describe_table

```{code-cell} python
def describe_table(table_name: str) -> str:
    """Return JSON metadata for a table: ordered list of {name, type, nullable}."""
    with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
        """, (table_name,))
        cols = [{"name": n, "type": t, "nullable": (nl == "YES")} for n, t, nl in cur.fetchall()]
    if not cols:
        return json.dumps({"error": f"no such table: {table_name}", "hint": "call list_tables to see available tables"})
    return json.dumps({"table": table_name, "columns": cols})

print(describe_table("film")[:300], "...")
print(describe_table("does_not_exist"))
```

Two patterns to notice — both from block 02's lessons on tool design:

- **Empty result → structured error with a hint** ("call list_tables to see available tables"). The model now has a recovery path: ask the schema for the right name, then retry.
- The **success shape and error shape are both JSON** — consistent return type.

## Tool 3 — run_sql

```{code-cell} python
def run_sql(query: str, max_rows: int = 50) -> str:
    """Execute a read-only SQL statement; return JSON with columns + rows.

    Errors (syntax, permissions, missing table) come back as structured JSON
    the model can read and react to.
    """
    try:
        with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
            cur.execute(query)
            if cur.description is None:
                return json.dumps({"error": "query produced no result set",
                                   "hint": "use a SELECT statement"})
            columns = [d.name for d in cur.description]
            rows = cur.fetchmany(max_rows)
            truncated = (cur.fetchone() is not None)
            # Stringify non-JSON-native types (Decimal, datetime, etc.)
            safe_rows = [[str(v) if v is not None else None for v in row] for row in rows]
            return json.dumps({
                "columns": columns,
                "rows": safe_rows,
                "truncated": truncated,
            })
    except Exception as e:
        return json.dumps({"error": type(e).__name__, "message": str(e),
                           "hint": "fix the SQL and try again; check column names with describe_table"})

# Smoke test
print(run_sql("SELECT count(*) AS n FROM film")[:200])
print(run_sql("SELECT broken sql here")[:200])
```

Design choices worth flagging:

- **`max_rows=50`** caps how much we send back to the model. A query that returns 10,000 rows would otherwise flood the context window and spike the bill. The model sees a `truncated: true` flag and can choose to refine the query (`LIMIT`, `GROUP BY`, …).
- **Decimals and datetimes are stringified.** Without this, `json.dumps` would crash on a `Decimal` column — and a crashing tool is the worst tool. Stringification is lossless for the model.
- **All exceptions are caught** and returned as structured errors with a hint. This is the third lesson from block 02 in action.

## The tool schemas the model will see

Finally, the JSON Schema declarations we hand to the API. Same shape as block 02, just three of them:

```{code-cell} python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "List the base tables available in the public schema of the Pagila database. Takes no arguments. Returns a JSON array of table names.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_table",
            "description": "Get the column names, types, and nullability for a single table. Call this before writing SQL that references the table.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Exact table name as returned by list_tables."},
                },
                "required": ["table_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": "Execute a read-only SQL SELECT statement and return up to 50 rows. The connection is read-only; INSERT/UPDATE/DELETE will fail. On error, returns a JSON object with `error`, `message`, and `hint` fields.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "A PostgreSQL SELECT statement."},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]

TOOL_IMPL = {
    "list_tables":    lambda: list_tables(),
    "describe_table": lambda table_name: describe_table(table_name),
    "run_sql":        lambda query: run_sql(query),
}

print(f"{len(TOOLS)} tools declared, {len(TOOL_IMPL)} implementations wired")
```

Notice how every description tells the model **when** to use the tool, **what** to pass it, and **what** comes back. That is not redundant — it is exactly what good tool descriptions look like.

## What we just learned

- Three tools is enough for any SQL agent: `list_tables`, `describe_table`, `run_sql`.
- The `agent_ro` Postgres role is the first line of defence against model-written destructive SQL.
- Every tool returns JSON; every error returns JSON with a `hint` the model can act on.
- `run_sql` caps row count to keep the prompt cheap and bounded.

Next: the system prompt that wraps these tools.
