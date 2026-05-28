---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# Wiring MCP into the agent loop

We have an MCP server (`add`, `multiply`) and we know how to translate its tool list into the OpenAI schema. Now we close the loop: the **agent calls the model**, the **model asks for a tool**, **we dispatch over MCP**, **we feed the result back**. The same `(12 + 8) * 3` problem from block 02 — but with tools served from a different process entirely.

## Setup — discover tools and prepare a dispatcher

```{code-cell} python
import asyncio, json
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = StdioServerParameters(
    command="python",
    args=["/workspace/materials/agents/demo-app/mcp_server.py"],
)

client = OpenAI()
```

## The MCP-backed agent loop

We keep the loop skeleton from block 02. The only difference is **how we dispatch tool calls** — instead of `TOOL_IMPL[name](**args)`, we make an async MCP call. Three small helpers first, then the loop reads like pseudocode.

```{code-cell} python
def fetch_tools_as_openai_schema(listed):
    """Translate an MCP list_tools result into OpenAI tool-catalog shape."""
    return [{
        "type": "function",
        "function": {
            "name": t.name,
            "description": t.description or "",
            "parameters": t.inputSchema,
        },
    } for t in listed.tools]

def call_llm(messages, tools):
    """One LLM round-trip. Returns the assistant message."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=tools,
        parallel_tool_calls=False,
        temperature=0,
    )
    return response.choices[0].message

async def run_tool_call_via_mcp(session, tc):
    """The only line that changes from block 02: dispatch over MCP."""
    args = json.loads(tc.function.arguments)
    result = await session.call_tool(tc.function.name, args)
    result_str = result.content[0].text
    print(f"  mcp:{tc.function.name}({args}) = {result_str}")
    return {"role": "tool", "tool_call_id": tc.id, "content": result_str}
```

```{code-cell} python
async def run_agent_via_mcp(user_question: str, *, max_turns: int = 10):
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = fetch_tools_as_openai_schema(await session.list_tools())

            messages = [
                {"role": "system", "content":
                    "You are a careful calculator. Use the tools — do not do arithmetic in your head."},
                {"role": "user", "content": user_question},
            ]

            for turn in range(max_turns):
                print(f"[turn {turn}]")
                msg = call_llm(messages, tools)
                messages.append(msg)

                if not msg.tool_calls:
                    print(f"  final: {msg.content}")
                    return msg.content

                for tc in msg.tool_calls:
                    messages.append(await run_tool_call_via_mcp(session, tc))

            raise RuntimeError(f"agent did not finish in {max_turns} turns")

answer = await run_agent_via_mcp("What is (12 + 8) * 3?")
print("answer:", answer)
```

Compare to block 02's trace: identical. The model sees the same tool catalog, picks the same calls, gets the same results. The plumbing underneath went from a Python dict to a JSON-RPC call to a subprocess — and the agent did not know or care.

## Verify it reached the right answer

```{code-cell} python
assert "60" in answer, f"Expected '60' in answer, got: {answer!r}"
print("OK — MCP-backed agent returned the right number.")
```

This is the **regression check** the lesson plan called for: the same question answered by both the inline-tool agent (block 02) and the MCP-tool agent (this lesson) reaches the same numerical answer. That is the proof point — MCP is *just another tool transport*, not a different mental model.

## What changes when you swap MCP servers

Because tool discovery is dynamic, you can point this same agent at a different MCP server and it picks up whatever tools that server exposes. A Postgres MCP server would suddenly give it `list_tables` and `run_sql`. A GitHub MCP server would give it `create_issue` and `list_prs`. The loop above does not change.

In production this is how multi-tool agents are composed: stand up an MCP server per system, declare which ones an agent can connect to, and the model gets the union of their tool catalogs. Block 04 will hand-roll Pagila tools inline — but you should hear the echo: those exact tools could be served from an MCP server and dropped into any future agent unchanged.

## What we just learned

- An MCP-backed agent loop is **identical** to block 02's loop except for how the tool gets dispatched (an async `session.call_tool` instead of `TOOL_IMPL[name](**args)`).
- Tool discovery is dynamic — no code changes when the server adds a new tool.
- Same question, same answer, different tool source. That equivalence is the value MCP buys you.
- The pattern composes: one agent + multiple MCP servers = the union of their tools.

Next block: the lesson's headline build — a real SQL agent over Pagila.
