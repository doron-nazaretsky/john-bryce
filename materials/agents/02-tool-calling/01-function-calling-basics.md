---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# Function calling, in one round-trip

This block is where an "LLM that talks" becomes an "LLM that can do." The mechanism the OpenAI API exposes is called **function calling** (some docs call it **tool use** — same thing). You hand the model a catalog of functions it is **allowed** to call, the model decides whether to call one, and your code runs it.

The whole protocol is four messages. We will walk all four.

## Step 1 — Declare the tool

A tool is described to the model with a JSON schema: a name, a description, and the shape of its arguments.

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
                    "a": {"type": "integer", "description": "First addend."},
                    "b": {"type": "integer", "description": "Second addend."},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            },
        },
    },
]
```

A few things to internalize before going further:

- The `description` is **prompt engineering**. The model uses it to decide when to call this tool. "Add two integers" is concrete; "performs arithmetic" is vague. Write descriptions like you would write a docstring for a colleague — that is exactly the role they play here.
- The `parameters` schema is JSON Schema. The model is fine-tuned to respect it: `"required": ["a", "b"]` means the model will not call the tool without both. `"additionalProperties": False` means it will not invent extra fields.
- The function does not actually exist anywhere yet. The tool catalog is just text the model reads. Running it is your problem.

## Step 2 — Let the model call it

We send a user question along with the tool catalog. With `tool_choice="auto"` the model decides whether to use a tool.

```{code-cell} python
from openai import OpenAI
client = OpenAI()

messages = [
    {"role": "system", "content": "You are a helpful assistant. Use the provided tools when needed."},
    {"role": "user",   "content": "What is 17 + 25?"},
]

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
    tools=TOOLS,
    tool_choice="auto",
    temperature=0,
)

msg = response.choices[0].message
print("content:    ", repr(msg.content))
print()
print("tool_calls:")
for tc in msg.tool_calls or []:
    print(f"  id={tc.id}")
    print(f"  name={tc.function.name}")
    print(f"  arguments={tc.function.arguments}")
```

Notice `content` is `None` — the model produced **no text answer** this turn. Instead, `tool_calls` carries one entry: a request to run `add` with the JSON arguments `{"a":17,"b":25}`. That `None` content is the signal to your code that the model is asking you to run something before it will speak.

## Step 3 — Run the tool, then send the result back

The tool call has a `name`, a JSON-encoded `arguments` string, and an `id` you use to reference it. Run the actual function and append a `tool` role message with the result, **keeping the assistant message that requested it** in the history.

```{code-cell} python
import json

def add(a: int, b: int) -> int:
    return a + b

# 1. Append the assistant message that asked for the tool call.
messages.append(msg)

# 2. For each tool call, run the function and append its result.
for tc in msg.tool_calls:
    args = json.loads(tc.function.arguments)
    result = add(**args)
    messages.append({
        "role": "tool",
        "tool_call_id": tc.id,
        "content": str(result),
    })

# Show what the conversation looks like now.
for m in messages:
    role = m["role"] if isinstance(m, dict) else m.role
    content = m["content"] if isinstance(m, dict) else m.content
    print(f"{role:>9} | {repr(content)[:80]}")
```

Three things are worth a careful look:

1. **The assistant message stays in history.** If you drop it and only keep the tool result, the model loses the connection between question and result and the next turn falls apart.
2. **`tool_call_id` ties result to request.** A single assistant turn can request multiple tool calls in parallel; the IDs are how you pair results back.
3. **Tool results are always strings** in the `content` field. JSON, plain text, even a stringified DataFrame — but a string. Pick a format the model can parse comfortably; we will use JSON or plain text throughout.

## Step 4 — Ask the model to continue

Now call the API again with the extended message list. The model sees the tool result and produces a final answer.

```{code-cell} python
response2 = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
    tools=TOOLS,
    temperature=0,
)

print(response2.choices[0].message.content)
print("---")
print("tool_calls this turn:", response2.choices[0].message.tool_calls)
```

`tool_calls` is `None` this turn — the model is satisfied and emitted a final answer. The loop would exit here.

## The whole shape, on one slide

```{mermaid}
sequenceDiagram
    participant U as user
    participant A as assistant (LLM)
    participant T as tool (your code)
    U->>A: "What is 17 + 25?"
    A->>T: tool_calls = [add(a=17, b=25)]
    T->>A: "42"
    A->>U: "17 + 25 = 42."
```

Four messages, one round-trip of tool execution. That is function calling. Everything else in this module is variations on this pattern — more tools, more turns, more interesting tools.

## What we just learned

- Tools are declared as JSON Schema with a name, a description, and a parameter shape.
- The model returns either `content` (an answer) or `tool_calls` (a request to run something), never both meaningfully populated.
- You execute the call, append a `tool` role message with the result and the original `tool_call_id`, and call the API again.
- The conversation grows by **two** messages per tool round-trip: the assistant's request and the tool's reply.

Next: wrap this round-trip in a loop and watch the agent take multiple steps on its own.
