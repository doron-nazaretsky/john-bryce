# AI Agent Development

An LLM that you call once is a chatbot. An LLM that you call in a **loop**, with **tools**, against your own **data**, is an agent. This module teaches you how to build the loop, design the tools, ground the agent in real data, and run it safely — using the OpenAI API and a Postgres database seeded with Pagila (the canonical Postgres sample).

By the end of the four hours you will have built a working "talk to your data" SQL agent over Pagila, swapped its tools for an MCP server, added a RAG sidebar for unstructured knowledge, and seen the same agent re-implemented in OpenAI's higher-level Agents SDK so the framework stops being magic.

## Prerequisites

- Comfortable with Python and the SQL module (Pagila has a Sakila-style normalized schema: `film`, `customer`, `rental`, `payment`, etc.).
- Docker Desktop running, with the agents lab up: `make lab-agents`.
- An `OPENAI_API_KEY` exported in your host shell before `make lab-agents`. Budget: ~$0.10–$0.25 per student for a full execute pass at `gpt-4o-mini`.

```{note}
This module requires the **agents lab**. Run `make lab-agents` before starting.
The lab seeds Pagila on first boot (~30 s) and exposes pgvector for the RAG block.
```

## Learning path

| Section | Topic | Duration |
|---|---|---|
| **01 — Foundations** | LLM-as-API + the agent loop mental model | ~20 min |
| **02 — Tool calling** | Hand-rolled first agent with a toy tool | ~35 min |
| **03 — MCP** | The standard for exposing tools across agents | ~25 min |
| **04 — Talk to your data** | SQL agent over Pagila, end to end | ~55 min |
| **05 — Context management** | History, summarization, prompt caching, and their tradeoff | ~35 min |
| **06 — Safety** | Prompt injection + read-only guards | ~15 min |
| **07 — RAG sidebar** | Embeddings and pgvector for unstructured knowledge | ~25 min |
| **08 — Patterns & frameworks** | ReAct, planner-executor, frameworks tour, agent observability | ~20 min |
| **09 — Exercise** | Extend the agent (start in class, finish at home) | ~10 min |

**Total: ~4 hours.**

## Concept map

This module reuses several patterns from `core-concepts/`. Where a generic
concept appears, lessons link back to its tool-agnostic home rather than
re-explain.

| Core concept | Where it shows up in this module |
|---|---|
| Architecture patterns → the **agent loop** | 01 Foundations, 02 Tool calling |
| Architecture patterns → **caching patterns** | 05 Context management (prompt-prefix caching is just another cache — same hit/miss/TTL mental model) |
| Data structures → **vectors / nearest-neighbor** | 07 RAG sidebar |
| Application patterns → **sync vs async communication** | 03 MCP (stdio vs HTTP transports) |

## A note on the role

Agent development sits between traditional software engineering and ML. As a
data engineer, you will rarely train the model — you'll wrap it with tools,
ground it in your data, and operate it in production. That's exactly where
this module spends its time. We will not cover fine-tuning, model evaluation
benchmarks, or anything that requires a GPU.
