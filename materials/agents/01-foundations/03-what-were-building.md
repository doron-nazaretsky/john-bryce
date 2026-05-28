---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# What we are building

The module's running example is a **"talk to your data" SQL agent**. A user asks a question in English; the agent generates and runs SQL against Pagila; the answer comes back in English. By block 04 you will have built it; by block 08 you will have rebuilt it three different ways.

Before we touch any agent code, take a moment to know the database.

## Pagila in 30 seconds

Pagila is the canonical Postgres port of Sakila — a sample database for a fictional **video rental** company. It has:

- **Films**, **actors**, and which actors are in which films.
- **Customers** at one of two **stores**, each store with **staff**.
- **Inventory** copies of films at each store.
- **Rentals** of inventory by customers, returned (or not), and the resulting **payments**.

It is small enough to scan in a couple of minutes and rich enough to ask non-trivial questions of. It is also already familiar from the SQL module if you completed that — same shape, different DBMS.

## Connecting from a cell

The agents lab exposes Postgres at `postgres:5432` from inside the workspace
container, and at `localhost:5432` from your laptop. Inside cells we connect
via `psycopg` using the `DATABASE_URL` env var the lab compose file sets for us.

```{code-cell} python
import os
import psycopg

DATABASE_URL = os.environ["DATABASE_URL"]

with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
    cur.execute("SELECT current_database(), current_user, version();")
    print(cur.fetchone())
```

The connection object will get hidden inside a `Database` helper class in block 04 — for now we are just confirming the wiring.

## The schema we'll talk to

```{code-cell} python
import psycopg, os

with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
          AND table_name NOT LIKE 'payment_p%'   -- hide partition children
        ORDER BY table_name;
    """)
    for (name,) in cur.fetchall():
        print(name)
```

You should see ~16 tables — Pagila's core schema plus the `docs` table we added for the RAG sidebar in block 07. `payment` is a partitioned table — we hide its monthly partition children in the listing above for clarity. The agent we build will treat it as one logical table.

## A few sample queries we'll teach the agent to answer

Here are the kinds of questions a user will ask:

- "How many films do we have?"
- "Which customer has spent the most?"
- "What are the top 5 most-rented categories?"

We will not give the agent canned SQL for these. We will give it **tools** that let it inspect the schema and run arbitrary SELECTs — and the model will write the SQL itself, from the schema it discovers.

That distinction is the whole point of the module. Spelling out SQL in code scales poorly; teaching the model to read the schema and write its own SQL scales to any database it has never seen.

```{code-cell} python
import psycopg, os

questions = [
    ("How many films do we have?",
     "SELECT count(*) FROM film;"),
    ("Top 3 customers by total spend?",
     """SELECT c.customer_id, c.first_name, c.last_name, sum(p.amount) AS total
        FROM customer c
        JOIN payment  p USING (customer_id)
        GROUP BY c.customer_id, c.first_name, c.last_name
        ORDER BY total DESC
        LIMIT 3;"""),
    ("Top 3 categories by rental count?",
     """SELECT cat.name, count(*) AS rentals
        FROM category cat
        JOIN film_category fc ON fc.category_id = cat.category_id
        JOIN inventory     i  ON i.film_id      = fc.film_id
        JOIN rental        r  ON r.inventory_id = i.inventory_id
        GROUP BY cat.name
        ORDER BY rentals DESC
        LIMIT 3;"""),
]

with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
    for question, sql in questions:
        cur.execute(sql)
        print(f"Q: {question}")
        for row in cur.fetchall():
            print(f"   {row}")
        print()
```

Hold onto these three numbers — we will check that the agent reaches the same answers later.

## Why this example

- **Realism.** Pagila is normalized properly; joins are real, not toy.
- **Bounded scope.** ~14 tables. The model can see the schema in a single context window without us doing fancy retrieval tricks.
- **Reusability.** The exact same pattern works on any SQL database students might point an agent at on the job — Pagila is just a stand-in.
- **Capstone fit.** Final-project teams whose pipelines land in Postgres can lift this whole agent into the bonus deliverable with a different schema and almost no code change.

## What we just learned

- The running example is a "talk to your data" SQL agent over Pagila.
- Pagila is a small, normalized, video-rental schema (~14 tables) — small enough to fit the schema in one prompt, rich enough to be a real benchmark.
- We will not hard-code SQL — we will give the agent tools to discover the schema and run its own queries.
- We pinned three ground-truth answers; we will use them to verify the agent later.

Next block: the mechanic that makes any of this possible — **tool calling**.
