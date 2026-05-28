---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# LLM as an API

Before we build an agent we need a clean mental model of the thing inside it. Strip away the chat UI and the marketing: a large language model, accessed via API, is a **stateless function** that maps a list of messages to one more message. That is it. Everything else — memory, tool use, agentic behavior — is built on top by the code calling the API.

## The shape of a chat call

A single OpenAI chat completion takes:

- A **model** identifier (`gpt-4o-mini`, `gpt-4o`, …).
- A list of **messages**, each with a `role` (`system` / `user` / `assistant` / `tool`) and `content`.
- Optional parameters: `temperature`, `max_tokens`, `tools`, etc.

It returns one assistant message plus a `usage` object telling you how many
tokens went in and came out.

```{code-cell} python
from openai import OpenAI

client = OpenAI()  # picks up OPENAI_API_KEY from the environment

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a terse assistant. One sentence max."},
        {"role": "user",   "content": "Why is Pagila a useful sample database?"},
    ],
    temperature=0,
)

print(response.choices[0].message.content)
print("---")
print("usage:", response.usage)
```

Three things to notice in the output:

1. The model returned **one** message. There is no streaming state, no session — the next call would have to send the entire conversation again.
2. `usage` reports `prompt_tokens` (what we sent) and `completion_tokens` (what came back). Both cost money; prompt tokens dominate in agent workloads because the conversation grows every turn.
3. `temperature=0` makes the response (mostly) deterministic. We use this throughout the module — agent loops are easier to reason about when the model isn't rolling dice.

## Roles, briefly

| Role | Who writes it | Purpose |
|---|---|---|
| `system` | You (the developer) | Persistent instructions, persona, rules. First message. |
| `user` | The end user | The question or request. |
| `assistant` | The model | Its reply. Also where tool calls appear (next lesson). |
| `tool` | Your code | The result of a tool the model asked you to run. |

If you have used the model only through ChatGPT, the system role may be new — it is the developer's lever for shaping behavior across an entire conversation.

## Tokens, cost, and why DE engineers should care

The API bills per **token**, not per request. A token is roughly ¾ of a word
in English. Two practical consequences for an agent:

- A long conversation = a large prompt every turn. The cost of turn N is
  proportional to **all** of turns 1..N–1 (plus the system prompt and any
  tool definitions). Agents bleed money in the tail.
- Tool **results** (e.g., 50 rows of SQL output) are sent back to the model
  on the next turn. Big tool results = big bills.

We will return to this in block 05 (context management). For now, just
notice the cost shape:

```{code-cell} python
short = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say 'hi'."}],
    temperature=0,
)

long_system = "You are a helpful assistant. " * 200  # ~1200 tokens of filler
long = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": long_system},
        {"role": "user",   "content": "Say 'hi'."},
    ],
    temperature=0,
)

print(f"short call: prompt={short.usage.prompt_tokens} completion={short.usage.completion_tokens}")
print(f"long  call: prompt={long.usage.prompt_tokens} completion={long.usage.completion_tokens}")
print(f"output identical? {short.choices[0].message.content.strip() == long.choices[0].message.content.strip()}")
```

Same output, very different prompt-token count. The system prompt is **not free** — and it is sent on every turn of an agent loop.

## What an LLM is not

It helps to be explicit about what is missing from the API:

- **No memory across calls.** Each call is stateless. If you want the model to remember the user's name, you have to put it in the messages of the next call yourself.
- **No access to your data.** It cannot read your database, your filesystem, or the internet — unless you give it a tool that does (next block).
- **No "thoughts" between calls.** Anything the model "knows" mid-task must be in the message list. There is no hidden scratchpad.

Every agent framework you will ever see is, at its core, code that maintains the message list and decides when to call the API again. That is what we are going to build.

## What we just learned

- A chat completion is a stateless function from messages to one message.
- Roles (`system` / `user` / `assistant` / `tool`) structure the conversation; the developer owns the system role.
- Cost scales with **prompt** tokens primarily — long system prompts and bloated tool outputs are where agents leak money.
- The model has no memory, no data access, no hidden state. Everything you want it to do has to live in the message list or be reachable through a tool.

Next: how the simple stateless call grows into an **agent loop**.
