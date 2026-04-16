# Data Engineering Course

A local self-served teaching platform for data engineering, DBA, and DevOps lessons.

## Quick Start

```bash
# Copy environment template
cp .env.example .env

# Start the docs site (workspace only, no databases)
make docs
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Lab Environments

Each lesson module that requires a database or service has a dedicated lab:


| Command                | Environment                            |
| ---------------------- | -------------------------------------- |
| `make docs`            | Workspace only (MyST docs + Jupyter)   |
| `make lab-orm`         | Workspace + PostgreSQL (ORM lessons)   |
| `make lab-sql`         | Workspace + SQL Server (SQL lessons)   |
| `make lab-nosql`       | Workspace + standalone MongoDB         |
| `make lab-replica-set` | Workspace + 3-node MongoDB replica set |
| `make lab-sharded`     | Workspace + MongoDB sharded cluster    |
| `make lab-distributed` | Workspace + gateway + worker + Redis   |


Only one lab runs at a time. Use `make down` to stop the current lab before switching.

## Common Commands

```bash
make down           # Stop the running lab
make reset          # Stop and remove all containers and volumes
make shell          # Open a bash shell in the workspace container
```

### After starting specific labs

```bash
# Restore SQL Server databases (after make lab-sql)
make sql-restore

# Initialize replica set (after make lab-replica-set)
# (automatically called by make lab-replica-set, but available manually)
make replica-set-init

# Initialize sharded cluster (after make lab-sharded)
# (automatically called by make lab-sharded, but available manually)
make sharded-init
```

## Dev Container

Open this repository in VS Code or Cursor with the Dev Containers extension to automatically boot the workspace container. The MyST docs site and Jupyter server start automatically.

To start a specific lab from within the Dev Container, open the terminal and run `make lab-<name>`.

## Authoring Lessons

Lesson materials are MyST Markdown files under `materials/`. Each `{code-cell} python` block is executable in the browser via the embedded Jupyter kernel.

To add a new lesson that requires sidecar services:

1. Create `labs/compose.<name>.yml` with the workspace + required services
2. Add a `make lab-<name>` target to the `Makefile`
3. Document the required lab at the top of the lesson with a `{note}` directive

### Instructor convenience: notebook export

To experiment with a lesson as a notebook (not committed):

```bash
make convert FILE=materials/python/01-orm/01-python-database-fundamentals.md
```

This creates a temporary `.py` file in py:percent format. Discard it after use.

## Course Modules

- **Core Concepts** — Big O, data structures, scaling, distributed systems, replication, architecture patterns
- **Git** — Fundamentals through real-world workflows
- **SQL** — Fundamentals through schema design (uses `make lab-sql`)
- **Python / ORM** — SQLAlchemy, Alembic, testing (uses `make lab-orm`)
- **Python Essentials** — Project setup, data structures, OOP, typing
- **Python / Web** — FastAPI, Pydantic, REST APIs
- **NoSQL** — Types, MongoDB basics, replication, sharding (uses `make lab-nosql`, `lab-replica-set`, `lab-sharded`)
- **Docker** — Containers, Compose, distributed systems (uses `make lab-distributed`)
- **Capstone Projects** — Self-contained scaffolds under `scaffolds/` (scaffold with `make new-project`)

## Capstone Projects

Capstone scaffolds live under `scaffolds/<name>/`. Each is self-contained: Docker
compose stack, student code, tests, stage briefs, and a `.post-init.py` hook.
Scaffold one into a fresh directory with:

```bash
make new-project                         # interactive: picks scaffold + target
make new-project ARGS="--list"           # list available scaffolds
make new-project ARGS="--scaffold nosql-ecommerce --target ~/code/shopflow"
```

Available scaffolds:

- `nosql-ecommerce` — four-database (PostgreSQL + MongoDB + Redis + Neo4j) polyglot pipeline
- `spark-etl` — incremental file-drop ETL on a Spark standalone cluster

