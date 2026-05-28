# Agents lab

Backs `materials/agents/` — the AI agent development lesson built around a
"talk to your data" SQL agent over Pagila and a small RAG sidebar.

## What's in the box

| Service | Purpose | URL / Port |
|---|---|---|
| `workspace` | Jupyter + MyST docs (inherited from `labs/base`) | http://localhost:8888 (token: `local-dev`), http://localhost:3000 |
| `postgres` | Pagila + pgvector for both the SQL agent and the RAG demo | localhost:5432 |

## Required environment

Set `OPENAI_API_KEY` in your host shell (or a `.env` file at the repo root):

    export OPENAI_API_KEY=sk-...

Optional overrides:

| Var | Default | Notes |
|---|---|---|
| `OPENAI_MODEL` | `gpt-4o-mini` | Cheap default; lessons that need a stronger model say so |
| `POSTGRES_DB` | `pagila` | |
| `POSTGRES_USER` | `postgres` | |
| `POSTGRES_PASSWORD` | `postgres` | |

## Usage

    make agents-seed-fetch    # one-time: fetches pagila-schema.sql + pagila-data.sql
    make lab-agents           # boots workspace + postgres + seeds Pagila on first run

The first `lab-agents` run takes ~30s while Pagila seeds. Subsequent runs are
fast — the volume `agents_postgres_data` persists the database.

## Smoke tests

Once the lab is up, verify the gates from the lesson plan:

    # 1. Containers healthy
    docker compose -f labs/base/compose.yml -f labs/agents/compose.yml ps

    # 2. Pagila tables exist
    docker exec -i postgres psql -U postgres -d pagila -c '\dt'

    # 3. Pagila is seeded (expect 1000)
    docker exec -i postgres psql -U postgres -d pagila -c 'SELECT count(*) FROM film;'

    # 4. pgvector works
    docker exec -i postgres psql -U postgres -d pagila \
        -c "SELECT '[1,2,3]'::vector;"

    # 5. Python deps installed
    docker exec -i workspace python -c "import openai, psycopg, pgvector, mcp, tiktoken; print('ok')"

    # 6. Jupyter reachable
    curl -s "http://localhost:8888/api?token=local-dev"

    # 7. OpenAI key works (skipped if unset)
    docker exec -i workspace python -c "
    import os
    if not os.getenv('OPENAI_API_KEY'):
        print('SKIP: OPENAI_API_KEY not set')
    else:
        from openai import OpenAI
        print('models:', len(list(OpenAI().models.list())))
    "

A green run on all seven gates is the entry criterion for writing lesson
content.

## Cost notes for instructors

The full module execute-pass spends roughly **$0.10–$0.25 per student** at
`gpt-4o-mini` rates (mostly the data-agent block and RAG embedding). The
open exercise in block 09 can push higher if students iterate; cap the
class with a shared key or per-student budget.
