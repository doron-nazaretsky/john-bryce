---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# When the SQL is wrong: error recovery

The model writes wrong SQL. Not often, not always, but enough that the agent has to handle it gracefully. The shape of recovery comes directly from block 02's rule: **errors return structured JSON with a `hint`; the model reads it and retries**.

In this lesson we provoke broken SQL on purpose, watch the loop recover, then talk about when recovery is the right answer and when something else (a guardrail, a cap, a different tool) is.

## Setup — reuse the tools and loop from lesson 03

We need everything from `03-end-to-end-walkthrough.md`. We re-import here to keep this notebook self-contained.

```{code-cell} python
import json, os, psycopg
from openai import OpenAI

ADMIN_URL = os.environ["DATABASE_URL"]
AGENT_URL = ADMIN_URL.replace("postgres:postgres@", "agent_ro:agent_ro@")
client = OpenAI()

def list_tables():
    with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_type='BASE TABLE' "
                    "AND table_name NOT LIKE 'payment_p%' ORDER BY table_name")
        return json.dumps([r[0] for r in cur.fetchall()])

def describe_table(table_name: str):
    with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT column_name, data_type, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s "
                    "ORDER BY ordinal_position", (table_name,))
        cols = [{"name":n,"type":t,"nullable":nl=="YES"} for n,t,nl in cur.fetchall()]
    return json.dumps({"table":table_name,"columns":cols} if cols
                      else {"error":f"no such table: {table_name}",
                            "hint":"call list_tables to see available tables"})

def run_sql(query: str, max_rows: int = 50):
    try:
        with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
            cur.execute(query)
            if cur.description is None:
                return json.dumps({"error":"no result set","hint":"use a SELECT"})
            cols = [d.name for d in cur.description]
            rows = cur.fetchmany(max_rows)
            truncated = (cur.fetchone() is not None)
            safe = [[str(v) if v is not None else None for v in row] for row in rows]
            return json.dumps({"columns":cols,"rows":safe,"truncated":truncated})
    except Exception as e:
        return json.dumps({"error":type(e).__name__,"message":str(e),
                           "hint":"fix the SQL and try again; check column names with describe_table"})

TOOL_IMPL = {"list_tables":list_tables, "describe_table":describe_table, "run_sql":run_sql}
TOOLS = [
    {"type":"function","function":{"name":"list_tables","description":"List base tables.",
     "parameters":{"type":"object","properties":{},"additionalProperties":False}}},
    {"type":"function","function":{"name":"describe_table",
     "description":"Get columns + types for one table.",
     "parameters":{"type":"object","properties":{"table_name":{"type":"string"}},
                   "required":["table_name"],"additionalProperties":False}}},
    {"type":"function","function":{"name":"run_sql",
     "description":"Execute read-only PostgreSQL SELECT. Errors return structured JSON with a hint.",
     "parameters":{"type":"object","properties":{"query":{"type":"string"}},
                   "required":["query"],"additionalProperties":False}}},
]
```

## Watch the recovery: a deliberately-misleading question

The phrase "movies" in the user's question nudges the model toward a non-existent `movies` table (the real one is `film`). Let's see what happens.

To actually *force* a recovery, we have to fight the model's own good judgment. By default the procedure prompt from lesson 02 pushes it toward `list_tables` + `describe_table` *before* writing SQL, and on a small schema like Pagila that almost always succeeds on the first try — there's nothing to recover from.

So we deliberately mis-tune the prompt: tell the model that schema-discovery tools are **expensive** and should only be used as a last resort. That nudges it toward guessing SQL from the user's wording, which is exactly the failure mode we want to provoke.

```{code-cell} python
SYSTEM_PROMPT = """\
You are a SQL analyst for the Pagila database (Postgres).
Be efficient: list_tables and describe_table are EXPENSIVE schema-discovery
calls. Use them only as a last resort when you are confused. For most questions
you should be able to guess the table and column names from the user's wording
and go straight to run_sql.

If a tool returns an error, READ the message and hint, then retry with a fix.
Do not give up.
"""

def call_llm(messages):
    r = client.chat.completions.create(
        model="gpt-4o-mini", messages=messages, tools=TOOLS,
        parallel_tool_calls=False, temperature=0)
    return r.choices[0].message

def run_tool_call(tc, trace):
    args = json.loads(tc.function.arguments)
    result = TOOL_IMPL[tc.function.name](**args)
    trace.append((tc.function.name, args, result[:150]))
    return {"role":"tool","tool_call_id":tc.id,"content":result}

def run_with_trace(question, max_turns=12):
    messages = [{"role":"system","content":SYSTEM_PROMPT},
                {"role":"user","content":question}]
    trace = []
    for _ in range(max_turns):
        msg = call_llm(messages)
        messages.append(msg)
        if not msg.tool_calls:
            trace.append(("final", msg.content))
            return msg.content, trace
        for tc in msg.tool_calls:
            messages.append(run_tool_call(tc, trace))
    raise RuntimeError("ran out of turns")

answer, trace = run_with_trace("How many rows are in the `movies` table?")
print("--- trace ---")
for step in trace:
    print(step)
print()
print("FINAL ANSWER:", answer)
```

What you should see in the trace:

- The model takes the bait — it skips `list_tables` and calls `run_sql("SELECT count(*) FROM movies")` (or similar) on its first move.
- `run_sql` returns a structured `UndefinedTable` error with our `hint` field telling it to use `describe_table` / `list_tables`.
- The model reads the hint, switches to the discovery path it had been avoiding, finds `film`, and retries `SELECT count(*) FROM film`.
- The final answer is the same `1,000` it would have reached the direct way — just with one extra recovery turn in the middle.

That is the load-bearing point of this lesson: **the wrong path is cheap and the recovery is automatic** *because* the tool returned a structured error with a hint. Without the hint, the model would have nothing to react to.

## A second example — column-name recovery

Same trick at the column level: ask for a column that doesn't exist but sounds plausible. Under our "discovery is expensive" prompt, the model again guesses first.

```{code-cell} python
answer, trace = run_with_trace(
    "What is the total revenue from rentals in the 'amount_total' column?"
)
print("--- trace ---")
for step in trace:
    print(step)
print()
print("FINAL ANSWER:", answer)
```

`amount_total` does not exist; the column is just `amount` on the `payment` table. With the discouragement-of-discovery prompt, the model:

1. Tries `SELECT sum(amount_total) FROM payment` (guesses the column from the question's wording).
2. Gets back `{"error":"UndefinedColumn", "message":"...", "hint":"check column names with describe_table"}`.
3. Calls `describe_table('payment')`, sees the real column is `amount`.
4. Retries with `SELECT sum(amount) FROM payment` and reaches the right total.

The structured error with hint is what makes step 2 → step 3 → step 4 happen instead of the agent throwing up its hands after step 1.

## When recovery is NOT the right answer

Self-recovery in the loop is the right pattern when:

- The error is something the model could plausibly fix from the next-step information (wrong table name, wrong column, syntax error, type mismatch).
- Retrying is cheap.
- A wrong answer would be worse than spending a few extra turns.

Recovery is the **wrong** pattern when:

- The error reveals an actual safety issue (e.g., permission denied because the model tried to DELETE). Bury that on purpose — let it fail without a hint, so the agent gives up instead of looping. Block 06 returns to this.
- Retrying costs real money (an external API charge per call, sending an email per call). Wrap those tools with rate-limits or human-in-the-loop confirmation; do not let the model retry on its own.
- The error is non-deterministic (timeout, transient network failure). Retry **once or twice** at most, with a small delay — and put the retry in your tool, not in the loop.

In short: in-loop recovery is appropriate for **logic errors the model produced**, not for **system errors your tool encountered**.

## Iteration caps as a safety net

The `max_turns` parameter we have been passing exists for exactly this kind of situation. If the model genuinely cannot fix the SQL — say, the user asked an unanswerable question — the loop would otherwise spin forever. Twelve turns is enough headroom for two or three recovery attempts on a hard question, and it is small enough that the cost of a runaway is bounded.

When the agent hits the cap **regularly**, that is the signal that something is wrong with your prompt, your tools, or the question — fix those, not the cap.

## What we just learned

- Structured tool errors with a `hint` field turn "the agent crashed" into "the agent tried again and got it right."
- Self-recovery is the right pattern for logic-level errors the model produced; it is the wrong pattern for safety errors or external side effects.
- A `max_turns` cap is the cheap safety net; if it trips often, fix the underlying agent, not the cap.

This concludes the build of the data agent. Next block: managing the context it accumulates.
