# Agents lab seed

Files in this directory are mounted read-only into the Postgres container at
`/docker-entrypoint-initdb.d/` and executed alphabetically on first startup
(empty data volume).

| Order | File | Source | Purpose |
|---|---|---|---|
| 00 | `00-extensions.sql` | repo | Enables `vector` extension for pgvector |
| 01 | `01-pagila-schema.sql` | upstream — fetched | Pagila schema (tables, views, functions) |
| 02 | `02-pagila-data.sql` | upstream — fetched | Pagila row data (~1000 films, etc.) |
| 03 | `03-docs.sql` | repo | Small `docs` table for the RAG sidebar (block 07) |

The Pagila files are fetched from `devrimgunduz/pagila` by the
`agents-seed-fetch` Make target and are git-ignored. Run:

    make agents-seed-fetch

This runs automatically before `make lab-agents`.

## Re-seeding

The seed only runs on first startup. To re-seed:

    make reset           # drops the agents_postgres_data volume
    make lab-agents
