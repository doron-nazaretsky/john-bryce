---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# Prompt caching: how it works, how to see it

The most important cost lever in modern LLM APIs is **prefix caching** — the API recognizes when the start of your prompt matches a recent one and serves the cached tokens at a steep discount. For an agent that sends ~80% of the same prefix every turn (system prompt, tool definitions, accumulating history), this is the difference between a viable agent and a budget catastrophe.

This lesson explains the mechanics and shows you the metric to watch.

## How OpenAI's prefix caching works

OpenAI caches **prompt prefixes automatically** — no flag, no opt-in — under three conditions:

1. The prompt is **≥ 1024 tokens** long. Shorter prompts are not cached.
2. The cache lookup matches **from the start**, in 128-token blocks. If byte 1 differs, the cache misses entirely.
3. The cache TTL is short (~5–10 minutes typical; degrades under load). Hot agents stay hot; idle agents lose the cache.

When a hit happens, you pay a discounted rate on the cached portion of the prompt — roughly **50%** off for `gpt-4o-mini` and `gpt-4o` (the exact percentage drifts; check the current pricing page). The completion is billed normally.

Anthropic does the same thing but **explicitly** — you mark blocks with `cache_control: ephemeral` and it caches those. Same mental model, different ergonomics.

## Seeing the cache hit

The response object exposes the count of cached tokens. Let's force a cache hit and read the field.

```{code-cell} python
import os
from openai import OpenAI
client = OpenAI()

# Build a deliberately long, stable system prompt. We need ≥ 1024 tokens for OpenAI
# to consider caching the prefix at all. The exact text doesn't matter — only that
# we send the EXACT same prefix on the second call.
PREFIX = (
    "You are a careful assistant. " * 50 +
    "Follow these long-winded rules carefully:\n" +
    "\n".join(f"Rule {i}: do nothing surprising or out of character." for i in range(100))
)

def call(question):
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":PREFIX},
            {"role":"user","content":question},
        ],
        temperature=0,
    )
    u = r.usage
    cached = u.prompt_tokens_details.cached_tokens if u.prompt_tokens_details else 0
    return r.choices[0].message.content, u.prompt_tokens, cached

# First call — populates the cache.
a1, p1, c1 = call("Say hi.")
print(f"call 1: prompt={p1} cached={c1}")

# Second call — same prefix, different user question. Expect cached > 0.
a2, p2, c2 = call("Now say bye.")
print(f"call 2: prompt={p2} cached={c2}")

assert c2 > 0, "Expected a cache hit on the second call (same long prefix)."
print(f"\nCache hit on call 2: {c2} of {p2} prompt tokens were cached ({100*c2/p2:.0f}%).")
```

That assertion is the **proof point** the lesson plan requires. If it ever stops passing, either OpenAI changed something, or your prefix is no longer stable.

## What "cache hit" pays you back

```{code-cell} python
PRICE_PER_M_INPUT = 0.15      # USD per 1M input tokens for gpt-4o-mini (approx)
PRICE_PER_M_CACHED = 0.075    # USD per 1M cached input tokens — 50% off

uncached_cost = p2 / 1_000_000 * PRICE_PER_M_INPUT
realistic_cost = (p2 - c2) / 1_000_000 * PRICE_PER_M_INPUT + c2 / 1_000_000 * PRICE_PER_M_CACHED
print(f"Without caching, call 2 would cost ~${uncached_cost*1e6:.2f} per million such calls.")
print(f"With caching,    call 2 actually costs ~${realistic_cost*1e6:.2f} per million such calls.")
print(f"Saved on call 2: {(1 - realistic_cost/uncached_cost)*100:.1f}%")
```

The savings on one call look small in absolute dollars. The point is that in a 10-turn agent, this discount compounds across every turn after the first.

## What invalidates the cache

A cache miss happens when **any byte** of the prefix differs. Things that you might not realize change the prefix:

- **Reordering tool definitions** in the `tools` array. The serialized JSON differs.
- **Adding a tool to the catalog.** Inserts new bytes in the middle.
- **Modifying the system prompt.** Even adding a date stamp at the top zeroes you out.
- **Updating a tool description.** Bytes inside the cached region changed.
- **Summarizing old turns.** This rewrites a chunk of the middle of `messages`, which sits in the cached prefix. (Lesson 04.)

This is why "small" changes to your agent code can cause a sudden cost spike. If your token bill suddenly doubles after a "harmless refactor," look at what you changed in the first 1024 tokens of your prompts.

## What does NOT invalidate the cache

A few things you might fear that are fine:

- **Appending a new user message.** The cached prefix is unchanged; you just extend it.
- **Appending tool results to the message list.** Same — the cache extends.
- **Changing the *user* turn at the very end.** Only the new bytes are not cached.

In other words: **append-only conversations are cache-friendly**. Mutations to the middle are cache-killers. That observation is the whole subject of lesson 04.

## Designing for the cache

Some pragmatic rules that emerge:

1. **Keep system prompt and tool definitions byte-stable.** Pick wording, freeze it. Don't dynamically generate the system prompt if you can help it.
2. **Order tool definitions consistently.** Sort them. Don't `tools=[...]` from a `dict.values()` iterator whose order varies.
3. **Put dynamic content at the end**, never at the start. The user's turn is dynamic; that's fine because the cache covers everything before it.
4. **Make the prefix big enough to be cacheable.** Padding a 600-token prompt to 1100 to clear the 1024 threshold can actually save money if you call it often.

## What we just learned

- OpenAI caches prefixes automatically when prompts are ≥ 1024 tokens; you see `cached_tokens` in `usage.prompt_tokens_details`.
- Hits give ~50% off the cached portion; misses are full price.
- The cache is **byte-exact from the start**, so anything that touches the first part of the prompt invalidates it.
- Append-only growth is cheap; mutations in the middle are expensive.

Next: the tradeoff that emerges when you summarize aggressively *and* rely on caching.
