---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# Your first hand-rolled agent loop

Previous lesson: one tool, one round-trip, four messages. That is not yet an agent — it is just a fancy function call. An agent emerges when the loop keeps going on its own, choosing tools and chaining results until the task is done.

In this lesson you will write the loop. Twenty lines of Python. Read every one.

## Two tools, so the model has to choose

Tasks that need just one tool can't show the agentic part — the chaining. We will give the model `add` and `multiply` and ask it a question that needs both.

```{code-cell} python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "Add two integers. Returns the integer sum.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "multiply",
            "description": "Multiply two integers. Returns the integer product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            },
        },
    },
]

TOOL_IMPL = {
    "add":      lambda a, b: a + b,
    "multiply": lambda a, b: a * b,
}
```

## The loop

We'll build the loop from three named pieces so the body reads like the diagram from block 01: **call the LLM**, **run one tool call**, **the loop itself**.

```{code-cell} python
import json
from openai import OpenAI
client = OpenAI()

SYSTEM_PROMPT = (
    "You are a careful calculator. Use the tools — do not do arithmetic in your head."
)

def call_llm(messages):
    """One round-trip to the model. Returns the assistant message."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
        parallel_tool_calls=False,  # see "A note on parallel calls" below
        temperature=0,
    )
    return response.choices[0].message

def run_tool_call(tc, *, verbose=True):
    """Execute one tool call and return the `tool` role message to append."""
    args = json.loads(tc.function.arguments)
    fn = TOOL_IMPL[tc.function.name]
    result = fn(**args)
    if verbose:
        print(f"  {tc.function.name}({args}) = {result}")
    return {"role": "tool", "tool_call_id": tc.id, "content": str(result)}
```

Now the loop itself is tiny — it reads exactly like the pseudocode:

```{code-cell} python
def run_agent(user_question: str, *, max_turns: int = 10, verbose: bool = True,
              return_messages: bool = False):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_question},
    ]

    for turn in range(max_turns):
        if verbose: print(f"[turn {turn}]")

        msg = call_llm(messages)
        messages.append(msg)

        if not msg.tool_calls:                      # no tool calls → done
            if verbose: print(f"  final: {msg.content}")
            return (msg.content, messages) if return_messages else msg.content

        for tc in msg.tool_calls:                   # run each tool call
            messages.append(run_tool_call(tc, verbose=verbose))

    raise RuntimeError(f"agent did not finish in {max_turns} turns")
```

That is the entire loop. Eight lines of body, and each one maps to a box in the flowchart: call the LLM, append its message, check for tool calls, run them and append results, repeat. Future blocks just swap better tools, smarter system prompts, and richer error handling into the same skeleton — `call_llm` and `run_tool_call` stay essentially this short.

## Watch it chain

```{code-cell} python
answer = run_agent("What is (12 + 8) * 3?")
print("---")
print("answer:", answer)
```

Look at the trace. The model:

1. Called `add(12, 8)` and saw `20`.
2. Called `multiply(20, 3)` and saw `60`.
3. Emitted a final answer that contains the number `60`.

That is the chain. The model is not running Python; it is choosing, one step at a time, what your Python should run next. The output of step N becomes the input the model considers in step N+1, because we appended the tool result to `messages`.

## Verify the result

We expect `(12 + 8) * 3 = 60`. Let's assert the model agrees:

```{code-cell} python
assert "60" in answer, f"Expected '60' in answer, got: {answer!r}"
print("OK — agent reached the right number.")
```

This kind of programmatic assertion against a model's free-text output is also the simplest **eval** you can write. We will build on it in block 08.

## A note on parallel tool calls

By default, OpenAI's API lets the model emit **multiple tool calls in a single assistant turn** — useful when calls are independent (e.g., "look up the weather in Tokyo and Paris"). But when calls **chain** (the result of one feeds the next), parallel mode bites: the model has no way to see the first result before issuing the second, so it guesses, and the guess is often wrong (or, with low-cost models, the JSON itself gets mangled).

For step-by-step reasoning — which is the dominant case in agent workloads — set `parallel_tool_calls=False`. The model still calls tools, just one at a time, seeing each result before deciding the next move. That is the behavior we want for the rest of this module.

Rule of thumb:

| Use parallel | Use sequential |
|---|---|
| Independent lookups, batched I/O | Each call depends on the previous result |
| Read-only queries you want to fan out | SQL agents, planners, anything chained |

## Look at the message list afterwards

A useful exercise: see exactly what the model saw on its last call. We re-run the agent with `return_messages=True` so it hands back the full message list alongside the answer.

```{code-cell} python
_, final_messages = run_agent("What is (12 + 8) * 3?", verbose=False, return_messages=True)

for m in final_messages:
    role = m["role"] if isinstance(m, dict) else m.role
    content = m["content"] if isinstance(m, dict) else m.content
    tool_calls = None if isinstance(m, dict) else getattr(m, "tool_calls", None)
    tag = f"[{role}]"
    if tool_calls:
        print(f"{tag:>11} TOOL_CALLS:")
        for tc in tool_calls:
            print(f"             {tc.function.name}({tc.function.arguments})")
    elif content is not None:
        print(f"{tag:>11} {str(content)[:100]}")
```

This is the **only** state the model has access to. There is no hidden scratchpad. If you wanted to debug a misbehaving agent, you would print this exact list and look at it line by line — the failure is always somewhere in there.

## What we just learned

- An agent loop is ~20 lines of Python: call API, run tool calls if any, repeat.
- The model chains tools by reading prior tool results, which appear in the message list as `tool` role messages.
- `max_turns` exists to bound runaways; if you hit it, the agent is lost.
- Inspecting the final message list is the best debugging tool you have.

Next: how to design tools so the model picks the right one for the right reason.
