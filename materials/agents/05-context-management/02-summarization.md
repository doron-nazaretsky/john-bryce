---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# Summarizing old turns

When the conversation history grows past your budget, you either **drop** turns or **summarize** them. Dropping loses everything older; summarizing loses detail but keeps the gist. This lesson is about doing summarization without wrecking the agent.

## The minimum viable summarizer

We use the model itself to compress an old slice of the conversation. The classic split: keep the system prompt verbatim, summarize everything older than the last K turns, keep the last K turns verbatim.

```{code-cell} python
import os, json
from openai import OpenAI
client = OpenAI()

def summarize_slice(messages_slice, *, model="gpt-4o-mini"):
    """Compress a list of messages into one short summary string."""
    flat = []
    for m in messages_slice:
        role = m["role"] if isinstance(m, dict) else m.role
        content = m["content"] if isinstance(m, dict) else getattr(m, "content", None)
        tool_calls = None if isinstance(m, dict) else getattr(m, "tool_calls", None)
        if tool_calls:
            flat.append(f"[{role}] tool_calls=" + ", ".join(
                f"{tc.function.name}({tc.function.arguments})" for tc in tool_calls))
        elif content:
            flat.append(f"[{role}] {content[:400]}")

    transcript = "\n".join(flat)

    r = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role":"system","content":
             "You are summarizing a transcript between a user and a tool-using "
             "agent. Preserve: the user's goal, every fact retrieved by tools "
             "(table names, columns, numbers), and any decisions made. Drop: "
             "small talk, redundant restatements. Output 3-6 bullet points."},
            {"role":"user","content":transcript},
        ],
    )
    return r.choices[0].message.content
```

Three rules in that system prompt are doing a lot of work:

- **"Preserve every fact retrieved by tools."** The single highest-value content in the history is what the tools returned — table names, schemas, query results. Lose those and the agent has to re-discover, paying twice.
- **"Preserve decisions made."** If the model already concluded something ("the relevant table is `payment`"), the summary should retain that.
- **Bullet points, not prose.** Bullets compress better and the model parses them just as well.

## A simple summarization policy

We replace messages 1..M with a single `system` message containing the summary, keeping the original system prompt at position 0 and the last K turns intact.

```{code-cell} python
def compact(messages, *, keep_last_n=4, system_keep=True):
    """Compress all but the last N turns. system_keep keeps the original system at index 0."""
    if len(messages) <= keep_last_n + (1 if system_keep else 0):
        return messages   # nothing to compress

    head = [messages[0]] if system_keep else []
    middle = messages[1:-keep_last_n] if system_keep else messages[:-keep_last_n]
    tail = messages[-keep_last_n:]

    if not middle:
        return messages

    summary = summarize_slice(middle)
    summary_msg = {"role":"system",
                   "content": f"<earlier-conversation-summary>\n{summary}\n</earlier-conversation-summary>"}
    return head + [summary_msg] + tail
```

A subtle decision: we put the summary in a **`system`** message, not a `user` message. The model treats system messages as instructions / context, and we want this content read as background, not as a turn the user took.

## Watch it compress a real run

Set up a few turns of a Pagila conversation, then compact and observe what shrinks.

```{code-cell} python
fake_history = [
    {"role":"system","content":"You are a SQL analyst for Pagila."},
    {"role":"user","content":"How many films do we have?"},
    {"role":"assistant","content":None},  # tool_calls would be here in a real msg
    {"role":"tool","tool_call_id":"a","content":'["actor","address","category","city","country","customer","film","film_actor","film_category","inventory","language","payment","rental","staff","store"]'},
    {"role":"assistant","content":None},
    {"role":"tool","tool_call_id":"b","content":'{"columns":["count"],"rows":[["1000"]]}'},
    {"role":"assistant","content":"There are 1,000 films."},
    {"role":"user","content":"And how many customers?"},
    {"role":"assistant","content":None},
    {"role":"tool","tool_call_id":"c","content":'{"columns":["count"],"rows":[["599"]]}'},
    {"role":"assistant","content":"There are 599 customers."},
    {"role":"user","content":"What about how many actors?"},
]

# Tokens before
import tiktoken
enc = tiktoken.encoding_for_model("gpt-4o-mini")
def tok(msgs): return sum(len(enc.encode(str(m.get("content") or ""))) + 4 for m in msgs)
print(f"before: {len(fake_history)} messages, ~{tok(fake_history)} tokens")

compacted = compact(fake_history, keep_last_n=3)
print(f"after:  {len(compacted)} messages, ~{tok(compacted)} tokens")
print()
print("--- the full compacted message list ---")
for i, m in enumerate(compacted):
    role = m["role"] if isinstance(m, dict) else m.role
    content = m["content"] if isinstance(m, dict) else getattr(m, "content", None)
    body = "<tool_calls>" if content is None else content
    print(f"[{i}] {role}:")
    for line in str(body).splitlines() or [""]:
        print(f"    {line}")
```

The compacted list should:

- Have far fewer messages (here: 12 → 5).
- Carry the load-bearing facts inside the summary — the table list and the headline numbers.
- Keep the most recent user question verbatim — so the model can answer it without losing fidelity at the freshest point.

Notice what's *missing* from your output: the summarizer may drop facts it judges secondary (you'll often see the 599 customers count omitted, for example). That is the lossy-by-design nature of this approach — and the reason you have to tune the summarizer's system prompt for what really matters in your domain.

If you re-check the assistant's next answer with this compacted history, it can usually continue the conversation, because the summary preserved most of what it needs.

## When to trigger compaction

The most common policy is a **token threshold**:

```python
if token_count(messages) > BUDGET_TOKENS:
    messages = compact(messages, keep_last_n=4)
```

You choose `BUDGET_TOKENS`. Some defaults:

- **Cost-driven:** pick a token cap that translates to a per-turn cost you're comfortable with.
- **Window-driven:** stay well under the model's context window. For `gpt-4o-mini` that's 128K, but you don't want to be near it — latency spikes and the model gets distracted.
- **Latency-driven:** larger prompts are slower. If your agent feels sluggish at 8K tokens, compact below that.

A second policy is **turn-based**: compact every K turns regardless of size. Simpler to reason about, less efficient.

## What summarization loses

Three things you trade away:

- **Exact phrasing.** If the user said something the model has to quote later, the summary may drop the words.
- **Edge-case awareness.** A failed tool call from earlier ("table not found") may not survive the summary. If the model later tries the same wrong table again, the warning is gone.
- **Cache compatibility.** This is the big one, and lesson 04 is entirely about it: replacing the middle of the message list **rewrites the prefix** that the API was caching, and the next call starts cold.

Holding onto that thought for next lesson: summarization saves prompt tokens *now* but can lose you a cache hit *later*. The arithmetic of which wins depends on how often you summarize.

## What we just learned

- Summarization compresses old messages into one short system message; the model itself does the work.
- A good summarizer system prompt explicitly preserves tool-retrieved facts and decisions.
- Trigger on token threshold or turn count; pick a budget driven by cost, window, or latency.
- Summarization loses exact phrasing, edge-case warnings, and — crucially — cache compatibility.

Next: how prompt caching works, and why summarization can defeat it.
