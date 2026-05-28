---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# What lives in conversation history, and why it bloats

Every call to the API sends the **entire** message list. There is no server-side memory. So the size of the message list at turn N is exactly what you pay to prefill on turn N, every turn. Conversations grow; bills grow with them.

This block is about understanding *what* grows, *how fast*, and *what you can do about it*. We start by measuring.

## What we send on each turn

To make the growth concrete, let's run the Pagila agent and count tokens after every turn. We use `tiktoken` to count locally without spending API money.

```{code-cell} python
import json, os, psycopg, tiktoken
from openai import OpenAI

ADMIN_URL = os.environ["DATABASE_URL"]
AGENT_URL = ADMIN_URL.replace("postgres:postgres@", "agent_ro:agent_ro@")
client = OpenAI()
enc = tiktoken.encoding_for_model("gpt-4o-mini")

def n_tokens(messages, tools=None):
    """Rough token count: sum the content + roles + tool-call JSON."""
    total = 0
    for m in messages:
        if isinstance(m, dict):
            content = m.get("content") or ""
            total += len(enc.encode(str(content)))
            total += 4  # role + framing tokens
        else:
            # ChatCompletionMessage object
            if getattr(m, "content", None):
                total += len(enc.encode(m.content))
            for tc in getattr(m, "tool_calls", None) or []:
                total += len(enc.encode(tc.function.name + tc.function.arguments))
            total += 4
    if tools:
        total += len(enc.encode(json.dumps(tools)))
    return total
```

Now reuse the SQL agent loop, but record token counts at every turn:

```{code-cell} python
# Minimal versions of the tools from block 04
def list_tables():
    with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_type='BASE TABLE' "
                    "AND table_name NOT LIKE 'payment_p%' ORDER BY table_name")
        return json.dumps([r[0] for r in cur.fetchall()])

def describe_table(table_name):
    with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
                    (table_name,))
        return json.dumps({"table":table_name,
                           "columns":[{"name":n,"type":t} for n,t in cur.fetchall()]})

def run_sql(query):
    try:
        with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
            cur.execute(query)
            cols = [d.name for d in cur.description]
            rows = [[str(v) if v is not None else None for v in r]
                    for r in cur.fetchmany(50)]
            return json.dumps({"columns":cols, "rows":rows})
    except Exception as e:
        return json.dumps({"error": type(e).__name__, "message": str(e)})

TOOL_IMPL = {"list_tables":list_tables, "describe_table":describe_table, "run_sql":run_sql}
TOOLS = [
    {"type":"function","function":{"name":"list_tables","description":"List base tables.",
     "parameters":{"type":"object","properties":{},"additionalProperties":False}}},
    {"type":"function","function":{"name":"describe_table","description":"Describe one table.",
     "parameters":{"type":"object","properties":{"table_name":{"type":"string"}},
                   "required":["table_name"],"additionalProperties":False}}},
    {"type":"function","function":{"name":"run_sql","description":"Run a PG SELECT.",
     "parameters":{"type":"object","properties":{"query":{"type":"string"}},
                   "required":["query"],"additionalProperties":False}}},
]

SYSTEM = ("You are a SQL analyst for Pagila (Postgres). Use list_tables, "
          "describe_table, then run_sql. Be terse.")
```

Same loop shape as block 02, just instrumented to log token counts. The two helpers below keep the loop body short.

```{code-cell} python
def call_llm(messages):
    r = client.chat.completions.create(
        model="gpt-4o-mini", messages=messages, tools=TOOLS,
        parallel_tool_calls=False, temperature=0)
    return r.choices[0].message

def run_tool_call(tc):
    args = json.loads(tc.function.arguments)
    result = TOOL_IMPL[tc.function.name](**args)
    return {"role":"tool","tool_call_id":tc.id,"content":result}

messages = [
    {"role":"system","content":SYSTEM},
    {"role":"user","content":"What are the top 3 most-rented film categories?"},
]

token_log = []
for turn in range(12):
    token_log.append(("before-call", turn, n_tokens(messages, TOOLS)))
    msg = call_llm(messages)
    messages.append(msg)
    if not msg.tool_calls:
        token_log.append(("final", turn, n_tokens(messages, TOOLS)))
        print(f"FINAL: {msg.content}")
        break
    for tc in msg.tool_calls:
        messages.append(run_tool_call(tc))

print()
print(f"{'phase':<14} {'turn':<5} {'tokens':>8}")
for phase, turn, n in token_log:
    print(f"{phase:<14} {turn:<5} {n:>8}")
```

Read the token column top-to-bottom. Three patterns will jump out.

## Pattern 1: every tool result lives in history forever

Each `describe_table` call we made added ~80–150 tokens of column metadata into the message list. Those tokens never leave — they are sent again on every subsequent turn. On a 10-turn agent, a chunky tool result from turn 2 is sent **eight more times**. That is where the bills come from.

## Pattern 2: the system prompt and tool catalog are sent every turn

Look at the very first row (`before-call, 0`). Most of those ~200 tokens are not the user question — they are the system prompt + JSON schemas of the three tools. Even at turn 0 with a one-line question, the tool catalog dominates: this minimal catalog is small, but a real agent with 30 tools instead of 3 would push that floor into the thousands.

Some production agents pay 5000+ tokens of overhead **per turn** before the user has said a word.

## Pattern 3: the curve goes one way

History only grows. There is no automatic forgetting. Whatever strategy you adopt for managing it has to be **explicit** — the API does nothing for you here.

## Three strategies you actually have

When the context starts costing more than you want, the toolbox is small:

1. **Drop old turns.** Keep only the last K turns plus the system. Simple, fast, lossy — the agent forgets what it learned earlier.
2. **Summarize old turns.** Replace turns 1..M with a single short "context so far" message. Lossy in a different way: the model has to trust your summary.
3. **Strip large tool results.** Keep the assistant message that requested the call (so the loop stays coherent) and replace the tool result body with a short marker ("[24 rows returned, see turn 7 for details]").

Lesson 02 covers (2). Lesson 03 covers prompt caching, which is what makes (1) cheap-but-not-free even when you do nothing. Lesson 04 explains the trap of doing both at once.

## Three things you don't have

For clarity, things the API will not do for you:

- **No automatic summarization.** The model does not "compress its own history."
- **No "remember this across sessions."** State only exists if you save it.
- **No way to retroactively reduce a message's cost.** Once you put 50 KB of tool output in history, every subsequent turn pays for it. You can edit the message list before the next call — that's the only escape.

## What we just learned

- The full message list is sent every turn; cost scales with its size.
- Tool results, the system prompt, and the tool catalog are the three big contributors.
- The API offers zero automatic memory management; every strategy is explicit code you have to write.
- Three patterns are practical: drop, summarize, strip. Each has a cost; lesson 04 is about how they interact with caching.

Next: summarization, the most aggressive of the three.
