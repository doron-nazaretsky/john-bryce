---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# Writing a tiny MCP server

To make MCP concrete we will build the smallest server that does something useful, then talk to it from a client and watch the protocol in action.

## The server, in 30 lines

The official Python SDK ships `FastMCP`, a Flask-flavored helper that turns Python functions into MCP tools. The server we ship with this module lives at `demo-app/mcp_server.py`:

```{code-cell} python
:tags: [remove-input]
import pathlib
print(pathlib.Path("/workspace/materials/agents/demo-app/mcp_server.py").read_text())
```

Each `@mcp.tool()`-decorated function becomes a tool the client can list and call. `FastMCP` reads the type hints to build the JSON Schema for the arguments and uses the docstring as the tool description. So this is the **same** pattern as our hand-rolled tool catalog in block 02 — just expressed in Python and discovered at runtime.

## Connecting from a client

The client spawns the server as a subprocess and talks to it over stdio. Two SDK pieces do this for us: `StdioServerParameters` describes how to launch the subprocess, and `stdio_client` opens the streams.

```{code-cell} python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = StdioServerParameters(
    command="python",
    args=["/workspace/materials/agents/demo-app/mcp_server.py"],
)

async def list_and_call():
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Tools discovered:")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")
                print(f"      schema: {tool.inputSchema}")

            result = await session.call_tool("add", {"a": 17, "b": 25})
            print("\ncall result for add(17, 25):")
            for chunk in result.content:
                print(" ", chunk.text)

await list_and_call()
```

Notice three things in the output:

1. **Discovery is dynamic.** The client did not need to know in advance which tools existed; it asked the server. New tools added to the server show up automatically on the next connect.
2. **The input schema came from Python type hints.** `a: int, b: int` was translated to a JSON Schema by `FastMCP`. No duplicated definitions.
3. **The result is content blocks**, not a bare value. MCP supports text, images, and embedded resources — for a simple int return like `add`, you get one text block with the stringified value.

## Bridging MCP tools into the OpenAI tool schema

Our agent loop in block 02 expected the OpenAI-flavored tool schema. To make MCP tools usable by that loop, we translate once at startup. The shape is nearly identical — only the wrapping differs.

```{code-cell} python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def fetch_openai_tools():
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            tools = []
            for t in listed.tools:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": t.inputSchema,
                    },
                })
            return tools

openai_tools = await fetch_openai_tools()
for ot in openai_tools:
    print(ot["function"]["name"], "->", ot["function"]["description"])
```

That five-line translation is the entire bridge between MCP and OpenAI's function-calling protocol. Most agent frameworks ship a helper for exactly this — but writing it yourself once removes the magic.

## Sanity check

A useful gut check: the toolset our agent will see from the MCP server should be functionally indistinguishable from the hand-written tools we used in block 02.

```{code-cell} python
expected_names = {"add", "multiply"}
actual_names = {t["function"]["name"] for t in openai_tools}

assert actual_names == expected_names, f"missing or extra: {expected_names ^ actual_names}"

# Required fields and types should match too.
add_schema = next(t for t in openai_tools if t["function"]["name"] == "add")
assert add_schema["function"]["parameters"]["properties"]["a"]["type"] == "integer"
assert add_schema["function"]["parameters"]["properties"]["b"]["type"] == "integer"
print("OK — MCP-served tools have the same shape as block 02's hand-written ones.")
```

## What we just learned

- `FastMCP` turns Python functions into MCP tools using type hints and docstrings.
- A client spawns the server (stdio transport) and discovers tools dynamically via `list_tools`.
- MCP tool schemas map to OpenAI tool schemas with a tiny wrapper — five lines of code.
- The MCP-served tools are functionally identical to inline ones; what changes is *where they live*.

Next: plug this server into our agent loop and see the same calculator agent work — only the tool source changed.
