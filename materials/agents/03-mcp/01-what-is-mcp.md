# What MCP is, and what it isn't

In block 02 we hand-rolled tools: a Python dict mapping names to lambdas, JSON Schema definitions hand-written next to them, and a loop that dispatches by name. That works — but every team building an agent reinvents it, and tools written for one agent runtime cannot move to another.

**MCP — the Model Context Protocol** — is a standard for how an LLM-driven application talks to a tool provider. Instead of each app inventing its own tool registry, an MCP server exposes a uniform interface, and any MCP-aware client can use it. Think of MCP as **USB for agent tools**: a single shape so anything with the right port can plug in.

## The shape of the protocol

MCP is JSON-RPC over a transport. The two transports in common use today:

- **stdio** — the server runs as a subprocess of the client; messages flow over stdin/stdout. Cheap, local-only, the default for development.
- **HTTP + SSE** — the server is a network service; messages flow over HTTP with server-sent events for streaming. The default for production / remote tools.

Either way, the message shape is the same. A client connects, performs a handshake, and can then call three kinds of primitives the server exposes:

| Primitive | What it is | We use it for |
|---|---|---|
| **Tools** | Callable functions the model can request | Everything in this module |
| **Resources** | Read-only data the client can fetch (files, DB rows) | Not covered — could host the Pagila schema as a resource |
| **Prompts** | Reusable prompt templates the server suggests | Not covered |

For agent development, **tools are the load-bearing primitive**. The other two are nice-to-haves we will skip in this module.

## Why this is worth a standard

Consider the alternative: every agent application defines tools internally. Want your SQL agent to also talk to a Slack tool? You rewrite the Slack integration inside your codebase. Want to switch your agent runtime from OpenAI Agents SDK to LangChain? You re-port every tool definition.

MCP decouples **tool implementation** from **agent runtime**. A Postgres MCP server, written once, works for:

- A custom hand-rolled loop (what we'll build next).
- Anthropic's Claude Desktop.
- OpenAI's Agents SDK.
- LangChain, LlamaIndex, whatever comes next.

This is the same separation TCP made between applications and links, or that ODBC made between SQL clients and databases. It is boring infrastructure. It is also why anyone serious about agents in 2025+ is paying attention.

## Server / client model

```{mermaid}
flowchart LR
    subgraph Client["Agent app (the client)"]
        C1[calls LLM]
        C2[keeps message list]
        C3[dispatches tool calls]
    end
    subgraph Server["MCP server"]
        S1[exposes tools]
        S2[executes them]
        S3[returns results]
    end
    Client <-->|"JSON-RPC over stdio / HTTP"| Server
```

The client is "the brain plus the loop." The server is "the hands." Conceptually identical to the loop in block 02 — but the implementation of `TOOL_IMPL` now lives in a different process (or even on a different machine), and the wire format is standardized.

## When MCP is overkill

MCP earns its complexity when **tools are reusable across applications**. If your agent has three tools, only ever used by this one agent, never to be shared, never to be moved to a different runtime — skip MCP. The block-02 hand-rolled approach is fine.

You want MCP when:

- The tool talks to a system many agents will want (Postgres, GitHub, Slack, internal APIs).
- You need to swap agent runtimes without re-porting tools.
- A platform team wants to centrally own and version tool definitions, separately from the apps that consume them.

For this module: we will use MCP to expose the SQL tools we would otherwise write inline. The reward is small in this lesson (one agent, one tool set), but the pattern is what you would do at work.

## What we just learned

- MCP = a JSON-RPC standard for exposing **tools** (plus resources and prompts) to LLM applications.
- Transports: **stdio** (local subprocess) and **HTTP + SSE** (network).
- The win is **decoupling**: same tool server works for any MCP-aware agent runtime.
- Worth the overhead when tools are reusable across apps; skip it for one-off tools.

Next: write a working MCP server in about 30 lines and see the protocol in motion.
