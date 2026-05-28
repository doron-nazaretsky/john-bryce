---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# The interaction: caching vs. summarization

Lesson 02: summarize to keep the prompt small. Lesson 03: caching cuts the per-turn cost of a stable prefix. Both are good. Put them together and they fight.

**Summarization rewrites the middle of the message list. The cache sees a different prefix. The cache misses.** What was supposed to save you money has, briefly, cost you the discount you were enjoying.

This lesson shows the effect and gives you design rules to win both at once.

## The collision, visible

We'll do two runs of the same conversation. In the **append-only** run, the cache extends as conversation grows. In the **summarize-every-turn** run, we replace the middle on every turn and the cache is destroyed.

```{code-cell} python
import os
from openai import OpenAI
client = OpenAI()

# Long stable preamble to ensure we cross the 1024-token caching threshold.
SYSTEM = (
    "You are a careful assistant. " * 50
    + "\n".join(f"Rule {i}: behave consistently and follow user instructions." for i in range(80))
)

def chat(messages):
    r = client.chat.completions.create(
        model="gpt-4o-mini", messages=messages, temperature=0,
    )
    u = r.usage
    cached = u.prompt_tokens_details.cached_tokens if u.prompt_tokens_details else 0
    return r.choices[0].message.content, u.prompt_tokens, cached

# Build a conversation of 5 short turns.
USER_TURNS = [
    "Say hi.",
    "What is 2 + 2?",
    "What is 3 + 3?",
    "What is 4 + 4?",
    "What is 5 + 5?",
]

print("--- Append-only conversation ---")
messages = [{"role":"system","content":SYSTEM}]
total_prompt = 0
total_cached = 0
for q in USER_TURNS:
    messages.append({"role":"user","content":q})
    answer, p, c = chat(messages)
    messages.append({"role":"assistant","content":answer})
    print(f"  prompt={p:5d}  cached={c:5d}  ({100*c/p:.0f}% hit)")
    total_prompt += p
    total_cached += c

print(f"  TOTAL prompt={total_prompt} cached={total_cached} hit-rate={100*total_cached/total_prompt:.0f}%")
```

```{code-cell} python
print("--- Prepend-dynamic-header run (cache killer) ---")

import time

# Anti-pattern: PREPEND something dynamic to the system prompt. This is the classic
# footgun — a "current time" header, a per-turn ID, or a regenerated summary placed
# *before* the stable system prompt. Because prefix caching matches from byte 0,
# ANY change in the first part of the prompt kills the entire cached prefix. This
# is exactly what naive every-turn summarization does when the summary is prepended.
messages = [{"role":"system","content":SYSTEM}]
total_prompt = 0
total_cached = 0
for i, q in enumerate(USER_TURNS):
    # The dynamic header changes every turn — cache miss guaranteed.
    dynamic_header = f"[turn {i}, ts={time.time_ns()}]\n\n"
    messages[0] = {"role":"system","content": dynamic_header + SYSTEM}
    messages.append({"role":"user","content":q})
    answer, p, c = chat(messages)
    messages.append({"role":"assistant","content":answer})
    print(f"  prompt={p:5d}  cached={c:5d}  ({100*c/p:.0f}% hit)")
    total_prompt += p
    total_cached += c

print(f"  TOTAL prompt={total_prompt} cached={total_cached} hit-rate={100*total_cached/total_prompt:.0f}%")
```

The numbers will tell the story: the append-only run rides the cache once it warms up (typically 90%+ hits from turn 2 onward); the prepend-dynamic run sits at near-zero hits across every turn, because the bytes at the **start** of the prompt change each call and prefix caching can only match a contiguous prefix from byte 0.

A subtle but important refinement on lesson 03's rule:

- **Changes at the *end* of a stable prefix** don't destroy the whole cache. The cache still serves the unchanged head; you only re-pay for the bytes after the change.
- **Changes at the *start*** kill the entire cache. There is no "skip to the matching part."

That asymmetry is why prepending timestamps, request IDs, or regenerated summaries to a system prompt is so costly. Summarization specifically: if you put the summary **before** the stable system prompt, the cache dies. If you put it **after**, the model sees two system messages (slightly worse for model quality) but the original system's cache survives.

The clean pattern is what the next section lays out.

## The interaction, in one rule

You can have **summarization** or **caching** at the boundary you summarize, not both. So summarize as **rarely** as possible. Concretely:

- **Coarse boundaries only.** Summarize when a task is *done* — not mid-tool-loop.
- **Off-band.** If you can, summarize the prior session as part of starting a new one; the new session's cache then builds from a clean, summary-included prefix.
- **Pay the one-time cost.** When you do summarize, accept that the next call will be a cache miss. Don't double-pay by summarizing every turn.

## Design rules that fall out

1. **System prompt + tool definitions: byte-stable, sorted, no timestamps.** This is the prefix that does the heavy lifting.
2. **Append-only mid-task.** Within a single user task — the period from when a question arrives until the agent answers — never mutate the message list. Append assistant messages, append tool results, that's it. The cache hit rate during this window will be high.
3. **Compact between tasks, not within.** Once the agent has answered, you can compact aggressively before the next user question — you're going to pay one cache miss either way, so do it once and not three times.
4. **Strip large tool results selectively.** A 50 KB rows-of-JSON result that you'll never need again can be replaced with a marker `"[24 rows returned]"` after the model has produced its final answer. Do it between tasks, not within.

## When summarization wins anyway

Caching is not free either — you pay something for cached tokens, just less. If your conversation is genuinely about to overflow the model's context window, the cost of a cache miss is irrelevant: you must summarize or fail.

In other words, the rules above are about **when both options exist**. When the context window forces your hand, summarize and move on.

## A back-of-envelope

Suppose you have a 10-turn agent with a 3 KB stable prefix. Tokens per call: ~750 (prefix) + growing tail.

- **Append-only, cache warm:** turns 2..10 pay ~50% on the prefix and full on the tail. Total cost ≈ 1× prefix + 4.5× prefix ≈ 5.5× prefix.
- **Summarize every turn:** turn 2 onward pays full on the prefix because each turn rewrites it. Total cost ≈ 10× prefix.

Almost **2× difference** on prefix cost for the same conversation. The exact ratio varies with cache TTL, model, and tail size — but "summarize less to cache more" is robust.

## What we just learned

- Summarization and prefix caching pull in opposite directions: one mutates the prefix, the other rewards stability.
- Within a single task, append-only is the cheap path; the cache rewards it.
- Across tasks, summarize once at the boundary — accept one miss, then build the next task's cache cleanly.
- Tool definitions and system prompts should be byte-stable across calls.

That's it for context management. Next: safety guards on a tool-using agent — the other thing that goes wrong in production.
