# ShopFlow — Project Introduction

## Getting Started

You should already be inside a fresh copy of this scaffold — produced by
running `make new-project` (or `scripts/new-project.py`) from the course
repo. If not, run it now and pick `nosql-ecommerce`.

From the scaffold root:

```bash
cp .env.example .env
docker compose up -d            # postgres, mongo, redis, neo4j
uv sync                          # install Python dependencies
```

No manual database creation needed — the test framework handles it automatically.

Once setup is complete, read the rest of this document, then move to the
Phase 1 brief at `stages/01-taking-orders/lesson.md`.

---

## The Business

ShopFlow is an online retailer that sells five product categories: **electronics, clothing, books, food, and home goods**.

Customers browse a product catalog, place orders, and receive a confirmation. Sellers manage inventory. The business tracks what was sold, at what price, to whom — and wants to use that history to improve the customer experience.

The company has grown from a handful of products and a few dozen daily orders to tens of thousands of products and hundreds of thousands of orders per month. The data problems they face have grown with them.

---

## Why You Are Here

ShopFlow's engineering team has built a web API that accepts customer requests and routes them to the right data operation. That API is already running — you can open it in a browser, see every endpoint, and call it.

But the API returns `501 Not Implemented` for every operation. Nothing is actually stored or retrieved yet. The data layer — the code that talks to databases — has been left for you to implement.

Your job over this project is to build that data layer, phase by phase, as the business demands it.

---

## The Story

ShopFlow is preparing to launch. The engineering team has three months before the first customers arrive, and a simple mandate: **make it work, make it correct, then make it fast**.

What "work" means will change as the business grows. Each phase of this project introduces a new set of business demands — things the system cannot currently do — and you will design and implement the solution.

The questions you will face are not "how do I write this query." The questions are:

- Where does this data belong?
- What guarantees does this operation need?
- What happens when the business has ten times as many products and orders?
- Is this storage choice still correct at that scale, or does it break?

Work through each phase in order. The problems in Phase 2 only exist because the system from Phase 1 is running.

---

## How the Project Works

The API is structured around a single class called `DBAccess`. Every web request ends up calling one method on this class. You implement those methods. The API calls them. The tests verify them.

You will not touch the web layer. You will not write HTTP handlers, parse request bodies, or format JSON responses. That's all done for you. You write Python functions that read from and write to databases.

---

## Project Structure

```
src/ecommerce_pipeline/
    postgres_models.py     ← YOU MODIFY (ORM models)
    db_access.py           ← YOU MODIFY (data access methods)
    reset.py               ← PROVIDED (don't touch)
    db.py                  ← PROVIDED (database connections)
    api/                   ← PROVIDED (web routes)
    models/                ← PROVIDED (request/response models)
scripts/
    migrate.py             ← YOU MODIFY (create tables, indexes, constraints)
    seed.py                ← YOU MODIFY (load data into databases)
    setup.py               ← PROVIDED (convenience: reset + migrate + seed)
seed_data/                 ← PROVIDED (JSON data files to load)
tests/                     ← PROVIDED (don't touch)
```

You modify exactly four files across all phases:
1. `postgres_models.py` — your ORM model definitions
2. `db_access.py` — the DBAccess methods
3. `scripts/migrate.py` — creates your database structures
4. `scripts/seed.py` — loads data into your databases

---

## Workflow

Every phase follows the same development loop:

1. **Design** — Read the method signatures and acceptance criteria. Decide what data goes where.
2. **Migrate** — Implement your migration logic, then run: `uv run python -m scripts.migrate`
3. **Seed** — Load the seed data into your databases: `uv run python -m scripts.seed`
4. **Implement** — Write the DBAccess methods one at a time.
5. **Test** — Run the relevant tests: `uv run pytest tests/test_phase1.py -v`
6. **Try the API** — Start the server and test interactively: `uv run uvicorn ecommerce_pipeline.api.app:app --reload`, then open `http://localhost:8000/docs`

---

## CLI Commands

| Command | What it does |
|---------|-------------|
| `uv run python -m scripts.migrate` | Drop everything and recreate database structures from your code |
| `uv run python -m scripts.seed` | Load seed data (requires migrate first) |
| `uv run python -m scripts.setup` | All-in-one: reset + migrate + seed |
| `uv run pytest tests/test_phase1.py -v` | Run Phase 1 tests |
| `uv run pytest tests/test_phase2.py -v` | Run Phase 2 tests |
| `uv run pytest tests/test_phase3.py -v` | Run Phase 3 tests |
| `uv run pytest tests/ -v` | Run all tests |

---

## How to Reset

| Situation | Command |
|-----------|---------|
| Changed your ORM models and need to recreate tables | `uv run python -m scripts.migrate` |
| Want a fully clean database with fresh data | `uv run python -m scripts.setup` |
| Something is deeply broken | `docker compose down -v && docker compose up -d` |

---

## The API

The web API is fully built and running. Start it and open `/docs` in your browser to see every endpoint, what it expects, and what it returns. You can test any endpoint interactively from that page.

Every endpoint returns `501 Not Implemented` until you implement the corresponding DBAccess method.

---

## Data Models

The data shapes your DBAccess methods receive and return are defined as Pydantic models in two files:

- **`models/requests.py`** — input models (e.g., `OrderItemRequest` with `product_id` and `quantity`)
- **`models/responses.py`** — output models (e.g., `ProductResponse`, `OrderResponse`, `OrderSnapshotResponse`)

Open these files to see the exact fields and types. Your DBAccess methods accept and return these models directly — the method signatures tell you everything you need.
