# Exercise: extend the agent

Now the lesson hands the keys over. Pick one of the tracks below — most students finish a track in 60–90 minutes — and run it as homework after the lesson. Each track builds on a different block, so pick the one that interests you, not all three.

## Track A — Add a chart tool

The current data agent answers in prose. Add a `make_chart` tool that produces a small PNG and embeds a base64 reference in the answer (or saves to a file and returns the path).

**Hints:**
- Use `matplotlib` or `plotly`. `matplotlib` is already in the workspace.
- Tool signature: `make_chart(data: list[dict], kind: str, title: str) -> str` returning a path (or a `data:image/png;base64,...` URI).
- Decide whether the model passes data to the tool, or whether the tool re-runs SQL inside itself. The first is simpler; the second is more efficient.
- Update the system prompt: "When the question would benefit from a chart, call make_chart."

**Stretch:** put the chart-rendering tool behind MCP (block 03) so it can be reused by other agents unchanged.

## Track B — Multi-turn memory across user questions

The agent in blocks 04–06 forgets everything between questions because each call starts a fresh message list. Build a persistent agent that remembers prior questions in the same session.

**Hints:**
- Wrap the loop in a `Session` class that holds `messages` across `.ask(question)` calls.
- Apply the lessons from block 05: append-only within a task, summarize between tasks, never mutate the early prefix.
- Test with a follow-up question: "How many films do we have?" → "And how many actors?" — the second should not need to re-discover the schema.

**Stretch:** persist sessions to Postgres so a user can resume their conversation after a process restart.

## Track C — Plug a second MCP server in

Pick a published MCP server (or write a second one) and connect your agent to it alongside the Pagila MCP server from block 03.

**Hints:**
- Aggregate tool catalogs from both servers at startup.
- The dispatcher key for tool calls is `(server, tool_name)`; route correctly when the model emits a call.
- Try with a filesystem MCP server, a web-fetch MCP server, or a calendar MCP server. The fun is in watching the model orchestrate two domains.

**Stretch:** add a fallback when a server fails to start, so the agent still runs with whichever servers are reachable.

## Track D — Hardened safety

Take the safety block as a starting point and harden the agent against a small adversarial test suite.

**Hints:**
- Write 10 prompt-injection payloads inserted as data into Pagila tables.
- Encode them as eval cases (block 08) so they run on every change.
- For each, the expected behavior is: model refuses to comply AND DB role would block it if it tried.
- Track which payloads the model handles well vs. poorly; this is real research.

## Track E — Replace the SQL agent with an Agents SDK build

Convert your block-04 agent to the OpenAI Agents SDK (block 08, file 02) and add **two new tools** of your choosing. Use the SDK's tracing dashboard to inspect what the agent does.

**Hints:**
- The `@function_tool` decorator builds tool catalogs for you — use it everywhere.
- Pick tools that exercise *real* parts of Pagila: e.g., a `summarize_customer(customer_id)` tool that does a curated 3-table join.
- Compare the SDK trace to the message list from your hand-rolled version. Same loop, different presentation.

## Submission

If this is graded, submit:

1. A short README describing which track and what you built.
2. The code (preferably as a `demo-app/` style module).
3. An eval suite with at least 5 cases proving it works.
4. A note on what surprised you. Agent development is mostly empirical; the surprises are where the learning is.

Have fun.
