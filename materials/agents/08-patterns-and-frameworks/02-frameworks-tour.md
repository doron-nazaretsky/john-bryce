---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# Frameworks tour: the same loop, in less code

We hand-rolled everything for pedagogical clarity. In production, most teams reach for one of two libraries that do the loop for you:

- **OpenAI Agents SDK** (`openai-agents`) — official, thin, sticks close to OpenAI's API. Recommended when you're already on OpenAI.
- **LangChain / LangGraph** — provider-agnostic, broader feature set, much more abstraction (and lock-in).

This lesson rebuilds the **same Pagila SQL agent** with the OpenAI Agents SDK and verifies it returns the same answer as the hand-rolled version. Then a short orientation to what LangChain looks like, so you can read it in the wild.

## Same agent, OpenAI Agents SDK

```{code-cell} python
import os, psycopg, json
from agents import Agent, Runner, function_tool

ADMIN_URL = os.environ["DATABASE_URL"]
AGENT_URL = ADMIN_URL.replace("postgres:postgres@", "agent_ro:agent_ro@")

@function_tool
def list_tables() -> str:
    """List base tables in the Pagila public schema."""
    with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_type='BASE TABLE' "
                    "AND table_name NOT LIKE 'payment_p%' ORDER BY table_name")
        return json.dumps([r[0] for r in cur.fetchall()])

@function_tool
def describe_table(table_name: str) -> str:
    """Get columns + types for one table."""
    with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
                    (table_name,))
        cols = [{"name":n,"type":t} for n,t in cur.fetchall()]
    return json.dumps({"table":table_name,"columns":cols})

@function_tool
def run_sql(query: str) -> str:
    """Execute a read-only PostgreSQL SELECT and return up to 50 rows as JSON."""
    try:
        with psycopg.connect(AGENT_URL) as conn, conn.cursor() as cur:
            cur.execute(query)
            cols = [d.name for d in cur.description]
            rows = [[str(v) if v is not None else None for v in r]
                    for r in cur.fetchmany(50)]
            return json.dumps({"columns":cols, "rows":rows})
    except Exception as e:
        return json.dumps({"error": type(e).__name__, "message": str(e)})

agent = Agent(
    name="Pagila SQL Analyst",
    instructions=(
        "You answer questions about the Pagila Postgres database. Use list_tables "
        "and describe_table to discover the schema, then run_sql to query. Always "
        "include exact numbers from the query in your answer."
    ),
    tools=[list_tables, describe_table, run_sql],
    model="gpt-4o-mini",
)

# Jupyter already runs an event loop, so we use the async Runner.run.
# In a plain Python script you would use Runner.run_sync(...) instead.
result = await Runner.run(agent, "How many films do we have?")
print("FINAL:", result.final_output)
```

That is the entire agent. Compare to block 04's hand-rolled version — they do the same thing; this is fewer lines and a tighter API. Three things the SDK gave us:

- `@function_tool` decorator builds the JSON Schema from type hints and the docstring — no hand-written tool catalog.
- `Agent` / `Runner.run_sync` collapses the entire loop into one call.
- Built-in tracing, retry, and parallel tool-call control — defaults are sensible.

## Verifying it returns the same answer

```{code-cell} python
# Plan's regression check: hand-rolled and SDK-served agents reach the same number.
def digits_of(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())

assert "1000" in digits_of(result.final_output), \
    f"Expected '1000' in SDK answer, got: {result.final_output!r}"
print("OK — Agents SDK reached the same ground-truth count as block 04.")
```

This is the proof point the plan called for: same database, same question, two different agent runtimes, equal numerical answer. The framework isn't doing magic — it's the same loop with sugar.

## What you give up by using the SDK

- **Visibility into the loop.** A bug in your tool — say, `run_sql` returning the wrong shape — surfaces as "the agent gave a weird answer," with one extra layer of abstraction between you and the cause. Always read what the SDK actually sends; don't trust documentation alone.
- **Cross-provider portability.** OpenAI Agents SDK is OpenAI-only. If you might switch to Anthropic or a local model, LangChain (or hand-rolling) is more portable.
- **Custom protocol changes.** Anything outside the SDK's "shape of an agent" — a custom turn-counting policy, a custom retry strategy, a quirky tool result format — becomes work to add.

For the majority of OpenAI-backed production agents, the trade is worth it.

## A glance at LangChain

LangChain is the other framework you will see. A representative skeleton:

```python
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.tools import tool

@tool
def list_tables() -> str:
    """List base tables in the Pagila public schema."""
    ...

agent = create_tool_calling_agent(
    llm=ChatOpenAI(model="gpt-4o-mini"),
    tools=[list_tables, describe_table, run_sql],
    prompt=ChatPromptTemplate.from_messages([...]),
)
executor = AgentExecutor(agent=agent, tools=[...], max_iterations=10)
executor.invoke({"input": "How many films do we have?"})
```

Three things to recognize when you read LangChain code:

- **`@tool` decorator** — same idea as `@function_tool`, slightly different metadata extraction.
- **`AgentExecutor`** — LangChain's name for the loop. Same loop you wrote in block 02.
- **`ChatPromptTemplate`** — LangChain's way of layering system prompts, history, and user input. Powerful, but adds another abstraction to learn.

LangChain's strengths: model provider-agnostic, large ecosystem of pre-built tools and integrations, **LangGraph** (the same project) for explicitly state-machine-shaped agents. Weaknesses: heavier, more opinionated, more breaking changes between versions.

## Rule of thumb

| Situation | Recommended |
|---|---|
| New project on OpenAI, single agent | **OpenAI Agents SDK** |
| Need provider portability | **LangChain** |
| Need explicit state machines / branching | **LangGraph** |
| Deep customization, no abstraction tax | **Hand-roll** (block 02) |
| Learning agents for the first time | **Hand-roll first**, then pick a framework |

You learned the hand-roll. Whichever framework you pick later, you will read its source code and recognize the loop. That is the point of this whole module.

## What we just learned

- The OpenAI Agents SDK reduces our block-04 agent to ~30 lines and reaches the same answers.
- LangChain offers the same model with broader provider support, at higher abstraction cost.
- Frameworks are conveniences over the loop, not replacements for understanding it.
- Pick by team / portability constraints, not by "which is the new shiny."

Next: how to know your agent is actually working in production — evals and observability.
