---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# End-to-end: a SQL agent answering real questions

This is the headline build of the module. We assemble the three SQL tools from lesson 01, the system prompt from lesson 02, and the agent loop from block 02 — and ask Pagila three questions of increasing complexity.

## Setup — bring in the pieces

To keep this notebook readable, we import the tool functions defined in lesson 01. They are short enough to redeclare here.

```{code-cell} python
import json, os, psycopg
from openai import OpenAI

ADMIN_URL = os.environ["DATABASE_URL"]
AGENT_URL = ADMIN_URL.replace("postgres:postgres@", "agent_ro:agent_ro@")
client = OpenAI()

def list_tables() -> str:
    with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema='public' AND table_type='BASE TABLE'
              AND table_name NOT LIKE 'payment_p%'
            ORDER BY table_name;
        """)
        return json.dumps([r[0] for r in cur.fetchall()])

def describe_table(table_name: str) -> str:
    with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position;
        """, (table_name,))
        cols = [{"name": n, "type": t, "nullable": (nl=="YES")} for n,t,nl in cur.fetchall()]
    if not cols:
        return json.dumps({"error": f"no such table: {table_name}",
                           "hint": "call list_tables to see available tables"})
    return json.dumps({"table": table_name, "columns": cols})

def run_sql(query: str, max_rows: int = 50) -> str:
    try:
        with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
            cur.execute(query)
            if cur.description is None:
                return json.dumps({"error": "no result set", "hint": "use a SELECT"})
            columns = [d.name for d in cur.description]
            rows = cur.fetchmany(max_rows)
            truncated = (cur.fetchone() is not None)
            safe = [[str(v) if v is not None else None for v in row] for row in rows]
            return json.dumps({"columns": columns, "rows": safe, "truncated": truncated})
    except Exception as e:
        return json.dumps({"error": type(e).__name__, "message": str(e),
                           "hint": "fix the SQL and try again; check column names with describe_table"})

TOOL_IMPL = {"list_tables": list_tables, "describe_table": describe_table, "run_sql": run_sql}
```

## The tool catalog and system prompt

```{code-cell} python
TOOLS = [
    {"type":"function","function":{
        "name":"list_tables",
        "description":"List the base tables in the Pagila public schema. Takes no arguments.",
        "parameters":{"type":"object","properties":{},"additionalProperties":False}}},
    {"type":"function","function":{
        "name":"describe_table",
        "description":"Get columns + types for one table. Call before writing SQL that references the table.",
        "parameters":{"type":"object",
                      "properties":{"table_name":{"type":"string"}},
                      "required":["table_name"],"additionalProperties":False}}},
    {"type":"function","function":{
        "name":"run_sql",
        "description":"Execute a read-only PostgreSQL SELECT. Returns up to 50 rows as JSON. Errors return a structured error object.",
        "parameters":{"type":"object",
                      "properties":{"query":{"type":"string"}},
                      "required":["query"],"additionalProperties":False}}},
]

SYSTEM_PROMPT = """\
You are a SQL data analyst answering questions about the Pagila database
(Postgres, video-rental schema). Tools: list_tables, describe_table, run_sql.

Procedure:
  1. If unsure which tables exist, call list_tables.
  2. For each table you'll query, call describe_table first to see its columns.
  3. Write ONE PostgreSQL SELECT, using joins / GROUP BY as needed.
  4. Call run_sql.
  5. If run_sql returns an error, read the message and hint, fix the SQL, retry.
  6. Answer the user's question in one or two plain-English sentences, including
     the exact number(s) from the query.

Constraints: read-only DB; do not INSERT/UPDATE/DELETE/DROP; do not invent table
or column names — use describe_table when unsure.
"""
```

## The loop

Same three-piece pattern as block 02 — `call_llm` for the API call, `run_tool_call` for one tool dispatch, and a tiny loop body that reads like the diagram.

```{code-cell} python
def call_llm(messages):
    response = client.chat.completions.create(
        model="gpt-4o-mini", messages=messages, tools=TOOLS,
        parallel_tool_calls=False, temperature=0,
    )
    return response.choices[0].message

def run_tool_call(tc, *, verbose=True):
    args = json.loads(tc.function.arguments)
    result = TOOL_IMPL[tc.function.name](**args)
    if verbose:
        short = result if len(result) < 120 else result[:117] + "..."
        print(f"  {tc.function.name}({list(args.keys())}) -> {short}")
    return {"role": "tool", "tool_call_id": tc.id, "content": result}

def run_data_agent(user_question: str, *, max_turns: int = 12, verbose: bool = True):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_question},
    ]
    for turn in range(max_turns):
        if verbose: print(f"[turn {turn}]")
        msg = call_llm(messages)
        messages.append(msg)

        if not msg.tool_calls:
            if verbose: print(f"  FINAL: {msg.content}")
            return msg.content

        for tc in msg.tool_calls:
            messages.append(run_tool_call(tc, verbose=verbose))

    raise RuntimeError(f"agent did not finish in {max_turns} turns")
```

## Question 1 — easy: "How many films do we have?"

```{code-cell} python
ans1 = run_data_agent("How many films do we have?")
```

Watch the trace. The model should:

1. Call `list_tables` (or jump straight to `describe_table('film')` if it's confident).
2. Call `run_sql("SELECT count(*) FROM film")` or equivalent.
3. Read `1000` from the result.
4. Answer in one sentence.

If you see it skip `describe_table` — that is fine for trivial questions. The procedure says "if unsure," and `count(*)` does not need column knowledge.

```{code-cell} python
# Strip commas / spaces so '1,000' still matches '1000'.
def digits_of(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())

assert "1000" in digits_of(ans1), f"Expected '1000' in digit-stripped answer, got: {ans1!r}"
print("OK — Q1 reached the ground-truth answer 1000.")
```

## Question 2 — medium: "Which customer has spent the most?"

This requires:

- Knowing there is a `payment` table (discoverable via `list_tables`).
- Knowing it has `customer_id` and `amount` columns (discoverable via `describe_table`).
- Joining or grouping to get a per-customer total.
- Ordering and taking the top row.

```{code-cell} python
ans2 = run_data_agent("Which customer has spent the most overall? Give me their name.")
```

```{code-cell} python
# Ground truth from block 01: KARL SEAL with $221.55
assert "KARL" in ans2.upper() and "SEAL" in ans2.upper(), \
    f"Expected top customer to be KARL SEAL, got: {ans2!r}"
print("OK — Q2 identified the right top customer.")
```

## Question 3 — harder: "What are the top 3 most-rented categories?"

This one needs **three joins**: `category → film_category → inventory → rental`. The model has to figure out the join graph from the schemas of those tables.

```{code-cell} python
ans3 = run_data_agent("What are the top 3 most-rented film categories, by total rental count?")
```

```{code-cell} python
# Ground truth from block 01: Sci-Fi (2490), New (2474), Documentary (2473)
top3_expected = {"Sci-Fi", "Sports", "Animation", "Action", "New", "Documentary"}
# The top three slot order can vary by tie-breaking, but Sci-Fi must be the top one
assert "Sci-Fi" in ans3, f"Expected Sci-Fi in top 3, got: {ans3!r}"
print("OK — Q3 reached the right top category.")
```

We are deliberately lax on the second-and-third place because Pagila has near-ties at 2474, 2473, 2469 — different runs may report them in slightly different orders depending on which join path the model takes. **Sci-Fi at the top is the load-bearing assertion.**

## What just happened

Three NL questions, three correct answers, zero hand-coded SQL on the application side. The model:

- Discovered the schema it needed using the cheap tools.
- Wrote SQL targeting the actual columns it had just learned about.
- Read the results and translated them back to English with the right numbers.

This is the entire "talk to your data" pattern. Everything beyond — multi-database routing, query plans, query caching, multi-step planners — is decoration on this loop with these tools.

## What we just learned

- The SQL agent is the same `run_agent` loop from block 02 with three real tools and a real system prompt.
- It answers count, join-with-aggregation, and three-way-join questions correctly with zero per-question code.
- Ground-truth comparison against the SQL from block 01 is the verification gate; we did it programmatically in cells.
- The handful of ties in question 3 are a real-world reminder: model answers can be correct *and* differ in formatting.

Next: what happens when the model writes broken SQL — and how the loop recovers.
