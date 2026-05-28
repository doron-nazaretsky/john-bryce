---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# Designing tools the model can actually use

A tool catalog is the agent's user interface — except the "user" is a language model, and the way you write descriptions and shape return values directly determines whether it will succeed. Three things to optimize, in order of impact:

1. **Names and descriptions** — what gets the model to pick the right tool.
2. **Granularity** — how many tools to have, and how powerful each should be.
3. **Error returns** — how the model can recover when something goes wrong.

We will work through each on a tiny toy domain so the failures and fixes are obvious. Block 04 applies all three to real SQL tools.

## 1. Names and descriptions are prompt engineering

The model reads tool names and descriptions every turn before deciding what to call. Compare two ways of declaring the same function:

```{code-cell} python
BAD = {
    "type": "function",
    "function": {
        "name": "process",
        "description": "Processes inputs.",
        "parameters": {
            "type": "object",
            "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
            "required": ["x", "y"],
        },
    },
}

GOOD = {
    "type": "function",
    "function": {
        "name": "rectangle_area",
        "description": (
            "Compute the area of an axis-aligned rectangle from its width "
            "and height in meters. Returns the area in square meters as a float."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "width":  {"type": "number", "description": "Width in meters."},
                "height": {"type": "number", "description": "Height in meters."},
            },
            "required": ["width", "height"],
            "additionalProperties": False,
        },
    },
}
```

The `GOOD` version tells the model:

- **What the tool is for** ("compute the area of an axis-aligned rectangle"). The model picks tools whose descriptions match the user's intent.
- **What units to pass** ("meters"). Without this, the model may pass anything.
- **What it returns** ("the area in square meters as a float"). The model uses this when forming the final answer.

Bad descriptions don't just hurt accuracy — they hurt tool **selection**. If you have ten tools and three of them have vague descriptions, the model will reach for the well-described ones every time and the others will go unused.

## 2. Granularity — one big tool or many small ones?

A common newcomer mistake is to write a single mega-tool with lots of parameters:

```python
# Tempting but wrong:
TOOL = {
    "name": "shape_calc",
    "description": "Calculates properties of shapes.",
    "parameters": {
        "type": "object",
        "properties": {
            "shape": {"type": "string", "enum": ["rectangle", "circle", "triangle"]},
            "operation": {"type": "string", "enum": ["area", "perimeter"]},
            "params": {"type": "object", "additionalProperties": True},
        },
    },
}
```

This loses you two things:

- **Schema enforcement.** `"params": {"additionalProperties": True}` means the model can pass anything; you lose the contract.
- **Discoverability.** Listing `rectangle_area`, `circle_area`, and `triangle_area` as separate tools tells the model "these are the things I can do." A single `shape_calc` requires the model to infer that from the parameters — extra cognitive load.

The opposite extreme is also wrong — twenty trivial tools (`add`, `subtract`, `multiply`, `divide`, `square`, …) pad the prompt with descriptions and waste tokens every turn.

Rule of thumb: **one tool per conceptual action**, with a description short enough that ten of them fit in a glance. For our SQL agent in block 04, that resolves to three tools: list tables, describe a table, run a query. Not thirty.

## 3. Error returns the model can use

Tools fail. The model has to recover. The shape of your error return determines whether it can.

```{code-cell} python
import json

def divide_v1(a: float, b: float):
    return a / b   # raises ZeroDivisionError if b == 0

def divide_v2(a: float, b: float):
    if b == 0:
        return {"error": "division by zero", "hint": "ask for a non-zero denominator"}
    return {"result": a / b}
```

If `divide_v1` raises, your loop crashes — the model never sees the error. Wrapping it in a try/except and returning the stack trace as a string is slightly better, but the model has to parse a Python traceback to figure out what went wrong.

`divide_v2` returns a structured error that the model can read and react to:

```{code-cell} python
# Imagine the model called divide_v2(a=10, b=0). Here's what it sees:
err = divide_v2(10, 0)
print(json.dumps(err))
```

Now when the loop appends this string as the `tool` message, the model sees `{"error": "division by zero", "hint": "..."}` and can decide to ask the user for a different number, switch tools, or give up gracefully.

Three guidelines that emerge:

- **Never let exceptions escape into the loop.** Catch them at the tool boundary and return a structured error.
- **Errors should suggest the next step.** "division by zero" is fine; "division by zero — ask for a non-zero denominator" is better. The model takes hints literally.
- **Use the same return shape for success and error.** Either always JSON (`{"result": ...}` vs `{"error": ...}`) or always plain text. Inconsistency is what makes the model fumble.

## A small example pulling it together

```{code-cell} python
import json
from openai import OpenAI
client = OpenAI()

TOOLS = [{
    "type": "function",
    "function": {
        "name": "divide",
        "description": (
            "Divide a by b. Returns {'result': float} on success, or "
            "{'error': str, 'hint': str} when the division is undefined."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "Numerator."},
                "b": {"type": "number", "description": "Denominator. Must be non-zero."},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
    },
}]

def divide(a, b):
    if b == 0:
        return {"error": "division by zero", "hint": "ask the user for a non-zero denominator"}
    return {"result": a / b}

messages = [
    {"role": "system", "content": "Use the divide tool. Be concise."},
    {"role": "user",   "content": "What is 10 divided by 0?"},
]

for _ in range(5):
    r = client.chat.completions.create(
        model="gpt-4o-mini", messages=messages, tools=TOOLS, temperature=0)
    msg = r.choices[0].message
    messages.append(msg)
    if not msg.tool_calls:
        print("FINAL:", msg.content)
        break
    for tc in msg.tool_calls:
        args = json.loads(tc.function.arguments)
        result = divide(**args)
        print(f"called divide({args}) -> {result}")
        messages.append({
            "role": "tool", "tool_call_id": tc.id,
            "content": json.dumps(result),
        })
```

The model calls `divide(10, 0)`, receives the structured error, and produces a graceful final message instead of crashing or pretending the answer is infinity. That recovery loop is only possible because the tool returned an error the model could read.

## What we just learned

- Tool **names** and **descriptions** are prompt engineering — they determine selection.
- **Granularity** is per conceptual action; not too coarse, not too fine.
- **Errors** must be structured returns, not exceptions; suggest the next step in the hint.
- Consistent return shape (always JSON or always plain text) makes the model robust.

Next block: **MCP** — a standard for exposing tools so the same `divide` could be served by any agent runtime.
