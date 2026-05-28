---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# Pgvector: storage + retrieval in Postgres

We already have Postgres. With the `pgvector` extension (enabled by the lab on first boot), we can store embeddings, index them, and search by similarity — all in SQL. No separate vector database to manage.

The lab seeds a small `docs` table with six rows of company policy text (membership tiers, late fee policy, hours, etc.) and an empty `embedding` column we will fill. By the end of this lesson the agent will be able to answer "what's the late fee policy?" by pulling from the docs table.

## What the docs table looks like

```{code-cell} python
import os, psycopg, json
from openai import OpenAI
client = OpenAI()

ADMIN_URL = os.environ["DATABASE_URL"]

with psycopg.connect(ADMIN_URL) as conn, conn.cursor() as cur:
    cur.execute("SELECT id, title, length(body) FROM docs ORDER BY id;")
    for row in cur.fetchall():
        print(row)
```

Six small docs. The `embedding` column is currently NULL — we have to fill it. This is the **indexing** step: do it once at corpus-load time, not per query.

## Embedding and storing

We embed each row's body and store the resulting vector in the `embedding` column. The `pgvector` Python library knows how to pass `list[float]` to a `vector(1536)` column.

```{code-cell} python
from pgvector.psycopg import register_vector
import psycopg

import numpy as np

def embed(text: str) -> np.ndarray:
    r = client.embeddings.create(model="text-embedding-3-small", input=text)
    return np.array(r.data[0].embedding, dtype=np.float32)

with psycopg.connect(ADMIN_URL) as conn:
    register_vector(conn)            # teaches psycopg about the vector type
    with conn.cursor() as cur:
        cur.execute("SELECT id, body FROM docs WHERE embedding IS NULL")
        for doc_id, body in cur.fetchall():
            vec = embed(body)
            cur.execute("UPDATE docs SET embedding = %s WHERE id = %s", (vec, doc_id))
    conn.commit()

print("Embeddings populated.")
```

A few production notes for the same operation at scale:

- **Batch the embeddings.** The API accepts a list of inputs and returns one vector per input in a single round-trip; we kept the demo simple but in real corpora you batch ~100 inputs per call.
- **Idempotent.** The `WHERE embedding IS NULL` filter means re-running this cell is safe — it embeds only what's missing.
- **Re-embed on model upgrade.** If you switch from `text-embedding-3-small` to `-large`, every existing vector is now stale.

## Querying — top-K nearest neighbor

Pgvector adds operators that compute distance between vectors. `<=>` is cosine distance (smaller = more similar). The query pattern is `ORDER BY embedding <=> %s LIMIT K`.

```{code-cell} python
def search_docs(query: str, k: int = 3):
    vec = embed(query)
    with psycopg.connect(ADMIN_URL) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, body, (embedding <=> %s::vector) AS distance
                FROM docs
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (vec, vec, k))
            return cur.fetchall()

hits = search_docs("If I return a movie a week late, what does it cost me?")
for doc_id, title, body, distance in hits:
    print(f"  [{distance:.3f}] {title}: {body[:80]}...")
```

The top hit should be the **Late fee policy** row. That's the verification gate the lesson plan asked for:

```{code-cell} python
top_hit = search_docs("If I return a movie a week late, what does it cost me?", k=1)[0]
assert top_hit[1] == "Late fee policy", \
    f"Expected top hit to be 'Late fee policy', got: {top_hit[1]!r}"
print(f"OK — top-1 NN matched ground truth: {top_hit[1]!r}")
```

## When the corpus is bigger, add an index

Six rows do not need an index — the database scans them all in microseconds. But once you have thousands or millions of vectors, you want an **approximate** nearest-neighbor index. Pgvector ships two:

- **IVFFlat** — invert-list on clustered centroids. Good for static corpora; needs `ANALYZE` after data changes.
- **HNSW** — small-world graph. Newer, generally faster and more accurate; higher memory.

For most workloads in 2025+ pick HNSW:

```sql
CREATE INDEX ON docs USING hnsw (embedding vector_cosine_ops);
```

Trade-off, briefly: HNSW indexes are **approximate**. You may not get the *exact* top-K every time. For RAG this is fine — the model is robust to small noise in the candidate set. For exact NN (legal compliance, audit), use the exact `<=>` scan without an index.

## Wiring it into the agent

The last step is a new tool, `search_knowledge_base`, that the agent can call when a question is about policy / docs and not about the operational tables:

```{code-cell} python
def search_knowledge_base(query: str) -> str:
    """Search internal company docs for relevant text."""
    hits = search_docs(query, k=3)
    return json.dumps([
        {"title": title, "snippet": body[:300], "distance": round(d, 3)}
        for _id, title, body, d in hits
    ])

TOOLS = [
    {"type":"function","function":{
        "name":"search_knowledge_base",
        "description":(
            "Search internal company knowledge base (policies, hours, procedures). "
            "Use this when the user's question is about company policy or rules, "
            "NOT about transactional data like films, customers, or rentals. "
            "Returns the top 3 most relevant doc snippets with similarity scores."
        ),
        "parameters":{"type":"object",
                      "properties":{"query":{"type":"string"}},
                      "required":["query"], "additionalProperties":False}}},
]

TOOL_IMPL = {"search_knowledge_base": search_knowledge_base}
```

Same loop pattern as the rest of the module — `call_llm` for the round-trip, `run_tool_call` for one dispatch, then the loop body:

```{code-cell} python
def call_llm(messages):
    r = client.chat.completions.create(
        model="gpt-4o-mini", messages=messages, tools=TOOLS,
        parallel_tool_calls=False, temperature=0)
    return r.choices[0].message

def run_tool_call(tc):
    args = json.loads(tc.function.arguments)
    result = TOOL_IMPL[tc.function.name](**args)
    print(f"  {tc.function.name}({args}) -> {result[:120]}...")
    return {"role":"tool","tool_call_id":tc.id,"content":result}

SYSTEM = ("You are a customer support assistant. Use search_knowledge_base to "
          "answer policy questions, quoting the relevant doc. Be concise.")

messages = [
    {"role":"system","content":SYSTEM},
    {"role":"user","content":"How much do I get charged if I return a movie 3 days late?"},
]

for _ in range(5):
    msg = call_llm(messages)
    messages.append(msg)
    if not msg.tool_calls:
        print("FINAL:", msg.content)
        break
    for tc in msg.tool_calls:
        messages.append(run_tool_call(tc))
```

The trace shows the agent:

1. Calling `search_knowledge_base` with a paraphrase of the question.
2. Receiving the top-3 doc snippets. The model's chosen phrasing can change which one ranks first (you may see Refund policy or Late fee policy at the top depending on how the model paraphrased), but **the Late fee policy snippet is reliably in the returned top-3** — and that is what the model quotes from.
3. Producing a plain-English answer.

The answer should mention "$1.00 per day" — directly from the Late fee policy doc that came back in the result list. That is RAG: the model didn't memorize this; it read it from a retrieval call.

## Tool selection: when to use SQL vs. when to use RAG

Notice how the agent in this lesson has only the RAG tool — and in block 04 it had only SQL tools. A real customer-support agent would have **both**: SQL tools for transactional questions ("did Mary return rental 12345?") and RAG tools for policy questions ("what's the late fee?").

The model picks based on tool descriptions. Writing descriptions like "use this when the user asks about policy, NOT about transactional data" is exactly the kind of tool-selection hint block 02 covered. Get those descriptions right, and the model routes correctly. Get them vague, and the agent guesses — and you spend turns watching it fumble.

## What we just learned

- Embeddings are stored in `vector(1536)` columns; `<=>` is cosine distance; `ORDER BY embedding <=> %s LIMIT K` is the canonical query.
- Embed once at corpus-load time, batch in production, and re-embed on model upgrade.
- HNSW indexes give you fast approximate NN; small corpora don't need an index.
- RAG enters the agent as another tool — the model decides when to use it based on the description.

Next block: patterns built on top of this primitive (planner-executor, ReAct, reflection), a quick framework tour, and how to observe agent runs in production.
