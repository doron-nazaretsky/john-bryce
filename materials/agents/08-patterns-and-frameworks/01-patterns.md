# Patterns built on the loop

The loop from block 02 is the entire engine. Everything you read about in agent literature — ReAct, planner-executor, reflection, multi-agent, tree-of-thought — is the same loop with a different system prompt or a different tool catalog. Knowing the patterns by name helps you read what other teams build and decide which shape your problem needs.

## ReAct (Reasoning + Acting)

The default style of our agents in this module. The model "thinks" (in its own message content) and "acts" (via tool calls) in alternation. The pattern is what you get for free with the loop + a tool catalog; no special prompting is needed.

When to recognize it: any agent where you see the model emit a sentence of reasoning before or after a tool call, then another tool call, then more reasoning. That's ReAct.

When it's the right pattern: most data agents, code agents, support agents — anywhere the model needs to interleave thinking and acting without a global plan.

## Planner-executor

The model is asked to **plan** first — output a numbered list of steps to take — then executes the plan one step at a time. Splits the work into:

1. **Planner call.** One LLM call, no tools, just produces a plan.
2. **Executor loop.** The ReAct loop from block 02, with the plan in the system prompt as a checklist.
3. **Optional re-planner.** After K steps, ask the model "given what you've learned, do you want to revise the plan?"

```{mermaid}
flowchart TD
    U[user question] --> P["planner LLM<br/>plan: [step 1, step 2, ...]"]
    P --> E["executor loop<br/>follows the plan; each step may use tools"]
    E --> F[final answer]
```

When to use it: tasks with **multiple sub-questions** ("compile a report on X covering A, B, and C") where the model otherwise loses track of what it still owes the user. The plan gives it a checklist.

When NOT to use it: short tasks. The planner call is overhead; for "how many films do we have?" it's pure waste.

## Reflection / self-critique

After producing a draft answer, the model is asked to **review its own answer** against the question. If it spots a flaw, it goes back into the loop and tries again.

```{mermaid}
flowchart TD
    L[normal loop] --> D[draft answer]
    D --> R["reflection LLM call:<br/>'Does this fully answer the question? List flaws.'"]
    R --> Q{flaws?}
    Q -- no --> Ret[return draft]
    Q -- yes --> Feed[feed flaws back as a user message]
    Feed --> L
```

When to use it: tasks where wrong answers are costly **and** the model can plausibly catch its own mistakes (math, code, multi-constraint problems). Empirical results are mixed — the model that wrote the answer is the same model judging it, so blind spots are correlated.

When NOT to use it: simple tasks (doubles your bill for no gain) or tasks where wrongness can't be detected from the answer alone (the model can't verify it called the right tool).

## Multi-agent

Several agents, each with a narrow role, coordinated by either a router agent or a shared message bus. Common shapes:

- **Router → specialist.** A small "dispatcher" agent decides which specialist handles the request; the specialist runs its own ReAct loop.
- **Manager → workers.** A manager agent breaks the work into chunks, fans out to worker agents (often in parallel), and aggregates results.
- **Debate / critic.** Two agents take opposing positions and converge through dialogue.

When to use it: only when a single agent has too many tools to choose well, or when work can usefully be parallelized. The mainstream agent in 2025+ is still a single ReAct loop with maybe a dozen tools; multi-agent is the exception, not the default.

## Tree-of-thought / branching

The agent explores multiple candidate next steps in parallel, evaluates each, and prunes. Most useful for problems where the search space is large and you can score partial solutions cheaply (e.g., puzzles, code synthesis). Almost never used in production data agents.

## Choosing a pattern

Decision flow that works:

1. **Start with ReAct.** Plain loop, three tools, a good system prompt. Most problems end here.
2. **If the agent forgets sub-questions** → planner-executor.
3. **If wrong answers are expensive and detectable** → add reflection.
4. **If the tool catalog grows past ~15 tools** → consider router + specialist agents.
5. **If you're building puzzle solvers** → look at tree-of-thought; otherwise skip it.

A useful sanity check: every pattern above is **the same loop wrapped or chained**. If you can implement it on top of `run_agent` from block 02, you understand it. If you cannot, the pattern probably has hidden state and that hidden state is where the bugs will live.

## What we just learned

- ReAct = the plain loop from block 02; the default.
- Planner-executor adds a checklist for multi-step tasks.
- Reflection adds a self-critique pass; mixed empirical value.
- Multi-agent is for narrow specialists or genuine parallelism — not the default in 2025.
- Patterns are wrappers around the loop, not replacements for it.

Next: how popular frameworks express the same loop with less typing — and whether the convenience is worth the lock-in.
