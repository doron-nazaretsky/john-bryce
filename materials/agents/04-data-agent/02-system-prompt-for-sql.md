# The system prompt that makes the SQL agent work

Tools alone are not enough. The model needs to know how to **use** them — when to discover the schema, when to run a query, what SQL dialect to target, and what to do when something goes wrong. That guidance lives in the system prompt.

A weak system prompt makes a smart model behave dumb. A good one does most of the work that bloated agent frameworks claim to do.

## The structure of a useful system prompt

Five things to put in, roughly in this order:

1. **Identity and goal.** One sentence on who the agent is and what it does.
2. **Procedure.** The order in which to use the tools.
3. **Constraints.** What it must not do (no writes, no fabricating data, no answering without checking).
4. **Output format.** How to phrase the final answer.
5. **What to do when stuck.** Recovery instructions, so it does not pretend.

Notice what is **not** in the list: a re-statement of the tool catalog. The API call already passes `tools=TOOLS`, and the model sees every tool's name, description, and parameter schema as part of that. Recapping them in the system prompt is wasted tokens — pay for it once, in the catalog, where it belongs.

Here is a prompt that works for Pagila:

```python
SYSTEM_PROMPT = """\
You are a SQL data analyst answering questions about the Pagila database
(a Postgres video-rental schema: films, customers, rentals, payments, etc.).

Procedure:
  1. If you don't already know the relevant tables, call list_tables.
  2. For each table you plan to query, call describe_table to learn its columns.
  3. Write ONE PostgreSQL SELECT statement. Use joins as needed. Prefer GROUP BY
     and aggregation over fetching raw rows. Always cap exploratory output with
     LIMIT 50 unless you need fewer.
  4. Call run_sql with that statement.
  5. If run_sql returns an error, READ the message and the hint, then fix the
     SQL and try again. Do not give up after one failure.
  6. Once you have the data you need, answer the user's question in plain English
     in one or two sentences. Always include the exact number(s) from the query.

Constraints:
- This database is read-only. Do not attempt INSERT, UPDATE, DELETE, or DDL —
  they will fail and waste a turn.
- Do not invent table or column names. If unsure, use describe_table.
- Do not paste large result sets into the final answer; summarize.

If a question cannot be answered from the data, say so clearly. Do not guess.
"""
```

The procedure step names — `list_tables`, `describe_table`, `run_sql` — appear because they tell the model **what order** to use the tools in. That is information the catalog does *not* convey. Restating *what each tool does* would be the redundant part; saying *when to reach for which one* is exactly what a procedure is for.

A few other things deserve a careful look.

## Why "Procedure" is six numbered steps

The model is excellent at following ordered instructions if you give them. Without the procedure, you will see it skip straight to `run_sql` with a guessed query — sometimes right (if the schema is Sakila-shaped), often subtly wrong (table name `films` vs `film`, column `total` vs `amount`). Costing you a turn or two of tool failures per question.

Walking it through `list_tables → describe_table → run_sql` adds two cheap tool calls but eliminates an entire class of avoidable errors. The economics favor verbosity here.

## Why mention SQL dialect explicitly

The model has seen MySQL, MSSQL, SQLite, BigQuery, Snowflake. Without a dialect hint it will sometimes reach for `TOP 10` (MSSQL) instead of `LIMIT 10`, or `IFNULL` (MySQL) instead of `COALESCE` (Postgres), or `DATEPART` instead of `EXTRACT`. Each one is a wasted turn.

Saying "PostgreSQL" once at the top of the prompt is one of the highest-leverage tokens you spend.

## Why explicitly forbid writes

"The DB is read-only" looks redundant — the `agent_ro` role enforces it at the database layer (block 06 returns to this). But:

- **Belt and braces.** Two layers means a misconfigured DB role does not become a security issue.
- **Saves turns.** If the model tries `DROP TABLE` it costs you a round-trip, a tool call, an error, another round-trip. Forbidding it in the prompt means it does not even try.
- **Cleaner failure mode.** When something *does* get blocked, the model recognizes the situation faster.

## Why "do not invent table or column names"

This is the single most common failure of SQL agents. The model has seen many "rental video" databases in training; it will confidently write `SELECT * FROM rentals` when the table is actually `rental`. The phrase "do not invent ... use describe_table" gives the model an explicit anti-hallucination tool to fall back on.

This is also why the procedure mandates `describe_table` **before** writing the SQL — it makes the right path the easy path.

## Why "answer in one or two sentences"

If you do not constrain output format, the model will dump the result table back at the user, then paraphrase it, then commentate. For a data agent the answer is a number and a brief explanation. Anything longer is wasted tokens and wasted attention.

## What we are not saying

A few things absent on purpose:

- No mention of specific Pagila tables in the prompt. We want the agent to **discover** the schema, not be pre-loaded. The pattern then generalizes to other databases unchanged.
- No few-shot examples. They take a lot of tokens and bias the model toward question shapes that look like the examples. We let `temperature=0` and a precise procedure do the work.
- No long preamble about being helpful or honest. The model already knows how to be helpful; spending tokens telling it so is wasted budget.

## A budget for system prompts

System prompts are sent on **every** turn. A 500-token system prompt for a 10-turn agent costs you 5000 tokens of prefill, every conversation. Block 05 will show how prompt caching turns this from "expensive" to "cheap" — but it is still worth measuring.

The prompt above is ~260 tokens. That is fine. If yours starts creeping past 1000, cut.

## What we just learned

- System prompts for tool-using agents have five parts: identity, procedure, constraints, output format, recovery. The tool catalog already covers "what tools exist" — don't restate it.
- "Procedure" forces the model into the cheap discovery path before the expensive guessing path.
- Dialect hints, "don't invent names," and a brevity constraint each save many turns over the lifetime of an agent.
- System prompts cost tokens every turn; keep them tight (~200–400 tokens for most agents).

Next: wire tools + prompt into the loop and ask Pagila some real questions.
