# E-Commerce Polyglot Data Pipeline

Scaffold for the ShopFlow capstone. Full narrative is in `00-introduction.md`
and the per-phase briefs live under `stages/`.

## Quickstart

```bash
cp .env.example .env
docker compose up -d            # postgres, mongo, redis, neo4j
uv sync                          # install Python deps
uv run pytest tests/             # stubs fail with NotImplementedError — expected
```

Then open `00-introduction.md` and work through `stages/01-taking-orders/` →
`stages/02-surviving-scale/` → `stages/03-personalization/` in order.

You modify four files across all phases:

- `src/ecommerce_pipeline/postgres_models.py`
- `src/ecommerce_pipeline/db_access.py`
- `scripts/migrate.py`
- `scripts/seed.py`
