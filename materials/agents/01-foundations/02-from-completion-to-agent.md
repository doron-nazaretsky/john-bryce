# From a single completion to an agent loop

A chat completion answers a question. It cannot **do** anything. If you ask the model "how many films are in our database?" it will guess — confidently, fluently, and with no way to be right unless it happens to know Pagila by heart. To answer that question correctly, something somewhere has to actually run `SELECT count(*) FROM film`.

An agent is the small amount of code that closes that gap. Concretely:

> An **agent** is a loop that calls the LLM, lets it ask for actions, runs those actions, and feeds the results back — until the model says it is done.

This single sentence is the entire concept. Memorize it before reading another framework's documentation; it will keep you grounded.

## The loop in pseudocode

```
messages = [system_prompt, user_question]
while True:
    response = llm(messages, tools=...)
    messages.append(response.message)

    if response.has_tool_calls:
        for call in response.tool_calls:
            result = run_local_function(call.name, call.arguments)
            messages.append({"role": "tool", "content": result, "call_id": call.id})
        # then loop again — the model sees the results and decides what to do next
    else:
        return response.message.content   # the model produced a final answer
```

That is it. Everything sophisticated in agent design — multi-step plans, reflection, multi-agent systems — is decoration on this loop.

## Three states the loop is in

At any moment, an agent is in exactly one of three states:

1. **Thinking.** The model is generating; we are waiting on the API. Nothing else is happening.
2. **Acting.** The model returned a tool call; our code is running that tool (a SQL query, an HTTP request, a file read).
3. **Done.** The model returned a plain message with no tool calls; the loop exits and we hand the message to the user.

A useful debugging instinct: when an agent misbehaves, ask **which state was it in when it went wrong?** Did it pick the wrong tool (thinking)? Did the tool return garbage (acting)? Did it stop too early (done)? Each state has different failure modes and different fixes.

## What the model decides every turn

On every turn, given the message list so far, the model decides one of three things:

- **"I can answer."** Emits a plain assistant message → loop exits.
- **"I need to act."** Emits one or more tool calls → loop runs them and continues.
- **"I am stuck."** Emits an apologetic message or makes something up. This is the failure mode you must guard against — bad system prompts and bad tool design make it more likely.

The model has no concept of "now I am stuck" — it simply produces tokens. Making "stuck" rare is mostly a matter of giving the model **good tools** with **good descriptions** and a **system prompt** that tells it what to do when uncertain. We will spend block 02 on exactly that.

## Why we stop manually

Notice the `while True` in the pseudocode. In practice you never write that. Every production loop has a cap:

```
for turn in range(max_turns):     # often 5–20
    ...
```

Without the cap, a confused model can ping-pong tool calls forever. We will use `max_turns = 10` throughout the module. If your agent hits the cap, that is a signal it lost the plot — fix the prompt, the tools, or the question, not the cap.

## The mental model, drawn out

```{mermaid}
flowchart TD
    U[user question] --> M["messages = [system, user, ...]"]
    M --> L[call the LLM]
    L --> D{tool_calls?}
    D -- yes --> R[run tools, append results to messages]
    R --> L
    D -- no --> F[return assistant message — DONE]
```

If you ever see a framework diagram with twelve boxes and arrows everywhere, mentally collapse it back to this one. The complexity is almost always inside a single box (e.g., "the tool" might be another agent), not in some new control flow.

## Connecting to core concepts

> **Core concept** — see [Sync vs Async Communication](../../core-concepts/07-application-patterns/03-sync-vs-async-communication.md). The agent loop is a synchronous, request/response interaction with the LLM, with the agent itself acting as the orchestrator between sync calls (to the model) and potentially synchronous tool execution (to a DB). Multi-agent systems extend this with async messaging between agents, but the inner loop stays the same.

## What we just learned

- An agent = a loop around a stateless LLM API + tools + a `max_turns` cap.
- Every turn the model picks one of: answer, call tools, or fumble.
- "Where did it go wrong?" maps cleanly to the three states (thinking / acting / done).
- Frameworks dress this up; the loop underneath is always the same.

Next: a tour of the database we will spend the rest of the module talking to.
