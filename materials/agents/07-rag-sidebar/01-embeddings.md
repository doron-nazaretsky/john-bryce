---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# Embeddings, in one notebook

The data agent answers questions whose answers are **in the database**. But many questions an end user asks are not — they are about policy, documentation, internal knowledge that does not have a `payment` table to query. The way agents handle that is **retrieval-augmented generation (RAG)**: pull the relevant unstructured text into the context and let the model read it.

The retrieval part is built on **embeddings**: turning text into vectors so "similar in meaning" becomes "close in space."

## What an embedding is

An embedding is a fixed-length vector of floats produced by an embedding model from a piece of text. Texts with similar meaning produce vectors that are close together by some distance metric (usually cosine distance). The vector is dense — every dimension carries some signal; you cannot read it directly.

OpenAI's `text-embedding-3-small` produces 1536-dim vectors. We use that throughout.

```{code-cell} python
import os
from openai import OpenAI
client = OpenAI()

def embed(text: str) -> list[float]:
    r = client.embeddings.create(model="text-embedding-3-small", input=text)
    return r.data[0].embedding

vec = embed("A short sentence about cats.")
print(f"dimensions: {len(vec)}")
print(f"first 6 floats: {[round(v, 4) for v in vec[:6]]}")
```

Two things to notice:

- 1536 floats per piece of text — that is what we store and search.
- The floats look arbitrary. They are. The structure only appears when you compare two vectors.

## "Close in meaning" = "close in space"

Let's prove it. Three sentences: two about cats, one about Postgres. The cat sentences should be closer to each other than either is to the Postgres one.

```{code-cell} python
import numpy as np

def cosine(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

cats_1 = embed("Cats are small carnivorous mammals often kept as pets.")
cats_2 = embed("The domestic cat is a popular companion animal.")
pg     = embed("PostgreSQL is an open-source relational database.")

print(f"cats_1  vs  cats_2  : {cosine(cats_1, cats_2):.4f}")
print(f"cats_1  vs  postgres: {cosine(cats_1, pg):.4f}")
print(f"cats_2  vs  postgres: {cosine(cats_2, pg):.4f}")

assert cosine(cats_1, cats_2) > cosine(cats_1, pg), "Expected cats to be closer to each other than to Postgres."
print("\nAs expected: the two cat sentences are closer in vector space.")
```

This is the whole engine. Cosine similarity ranges from -1 (opposite) to 1 (identical direction). For `text-embedding-3-small` you'll typically see values around 0.5–0.7 for "the same topic" (our two cat sentences land at ~0.59), 0.2–0.4 for "loosely related," and below ~0.2 for "unrelated" (the cats-vs-Postgres pairs at ~0.10–0.15).

Don't memorize thresholds — they vary by model and domain. In practice you embed everything once, then for a query you rank candidates by similarity and take the top K. The absolute scores don't matter; the ordering does.

## What can be embedded

Embedding models accept text — usually up to a few thousand tokens per input. Common things to embed:

- **Documents** — chunked into ~500-token paragraphs for retrieval.
- **User questions** — at query time, to find similar documents.
- **Code** — works, but specialized code-embedding models exist.
- **Database row text** — e.g., film titles + descriptions if you want fuzzy search over them.

Out of scope:

- **Numeric features** — for those use traditional vector indexes / k-NN over your own features, not LLM embeddings.
- **Images** — use a multimodal embedding model; the API shape is the same.

## What embeddings are not

A few clarifications worth making, since the term "embedding" is overloaded:

- **Not a search engine.** An embedding is just a vector; *searching* with it requires a vector index (next lesson — pgvector). You build the index; the embedding model doesn't.
- **Not deterministic across model versions.** `text-embedding-3-small` vectors are not comparable to `text-embedding-3-large` vectors, or to last year's `ada-002`. Pick a model and stick with it for a corpus; if you upgrade, you re-embed everything.
- **Not free.** Embedding 1M tokens costs ~$0.02 at `text-embedding-3-small` rates. Cheap, but worth tracking if your corpus is huge.

## A back-of-envelope for cost

```{code-cell} python
import tiktoken
enc = tiktoken.encoding_for_model("text-embedding-3-small")

corpus_size_words = 1_000_000
tokens_per_word = 1.3       # English average
total_tokens = corpus_size_words * tokens_per_word
price_per_m = 0.02          # $/1M tokens — text-embedding-3-small

print(f"Embedding 1M words ≈ {total_tokens:,.0f} tokens")
print(f"Estimated cost: ${total_tokens / 1_000_000 * price_per_m:.4f}")
```

Even a million words of company knowledge embeds for the price of a coffee. The cost driver is query-time inference, not embedding the corpus.

## What we just learned

- An embedding turns text into a fixed-length vector; semantically similar texts produce vectors close together by cosine similarity.
- The structure only appears in comparisons — you cannot read the dimensions directly.
- Pick one embedding model per corpus; vectors don't transfer across models.
- Embedding a corpus is cheap; serving high-volume queries is what costs money.

Next: store those vectors in Postgres and let the agent retrieve from them.
