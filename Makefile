# ─── John Bryce Data Engineering Teaching Platform ──────────────────────────
#
# Convention:
#   make docs           — workspace only (MyST site + Jupyter, no sidecars)
#   make lab-<name>     — workspace + lesson-specific sidecar services
#   make down           — stop whichever lab is currently running
#   make reset          — stop and remove all containers, networks, and volumes
#   make shell          — open a bash shell in the running workspace container
#
# Lab architecture:
#   Every lab merges labs/base/compose.yml (workspace) with labs/<name>/compose.yml
#   (sidecars + workspace overrides). The LAB build arg installs per-lab Python deps.
# ────────────────────────────────────────────────────────────────────────────

.PHONY: docs lab-preflight lab-orm lab-sql lab-nosql lab-replica-set lab-sharded lab-distributed lab-web \
        lab-redis lab-redis-sentinel lab-redis-cluster \
        lab-neo4j lab-neo4j-cluster \
        lab-streaming lab-monitoring \
        new-project test-scaffolds \
        down reset shell convert \
        replica-set-init sharded-init sql-restore redis-cluster-init neo4j-cluster-init \
        help

BASE := -f labs/base/compose.yml

# ─── Default target ─────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  make docs                 Start workspace only (MyST docs + Jupyter)"
	@echo "  make lab-orm              Start workspace + PostgreSQL (ORM lesson)"
	@echo "  make lab-sql              Start workspace + MSSQL (SQL lesson)"
	@echo "  make lab-nosql            Start workspace + standalone MongoDB"
	@echo "  make lab-replica-set      Start workspace + 3-node MongoDB replica set"
	@echo "  make lab-sharded          Start workspace + MongoDB sharded cluster"
	@echo "  make lab-distributed      Start workspace + gateway + worker + Redis"
	@echo "  make lab-web              Start workspace with FastAPI deps (Web APIs lesson)"
	@echo "  make lab-redis            Start workspace + single Redis (KV lessons 01-03)"
	@echo "  make lab-redis-sentinel   Start workspace + 3 Redis nodes + Sentinel (KV lesson 04)"
	@echo "  make lab-redis-cluster    Start workspace + 6-node Redis Cluster (KV lesson 05)"
	@echo "  make lab-neo4j            Start workspace + single Neo4j (Graph lessons 01-06)"
	@echo "  make lab-neo4j-cluster    Start workspace + 3-node Neo4j causal cluster (Graph lesson 07)"
	@echo "  make lab-streaming        Start 3-broker Kafka (KRaft) + Spark cluster (Streaming lessons)"
	@echo "  make lab-monitoring       Start full observability stack + Spark cluster + Kafka + Postgres (Monitoring lesson)"
	@echo ""
	@echo "  make new-project          Scaffold a capstone project into a new directory (pass ARGS=... for flags)"
	@echo "  make test-scaffolds       Verify scaffolds fail correctly, then pass once solutions are overlaid"
	@echo ""
	@echo "  make down                 Stop the running lab"
	@echo "  make reset                Stop + remove all containers and volumes"
	@echo "  make shell                Open bash in the workspace container"
	@echo ""
	@echo "  make replica-set-init     Initialize MongoDB replica set (after lab-replica-set)"
	@echo "  make sharded-init         Initialize MongoDB sharded cluster (after lab-sharded)"
	@echo "  make redis-cluster-init   Initialize Redis Cluster (after lab-redis-cluster)"
	@echo "  make neo4j-cluster-init   Initialize Neo4j Cluster (after lab-neo4j-cluster)"
	@echo "  make sql-restore          Restore AdventureWorks/Northwind databases (after lab-sql)"
	@echo ""
	@echo "  make convert FILE=path    Convert a MyST lesson to py:percent (instructor only)"
	@echo ""

# ─── Docs / workspace only ──────────────────────────────────────────────────

docs:
	docker compose $(BASE) up -d --build --remove-orphans
	@echo "MyST docs: http://localhost:3000"
	@echo "Jupyter:   http://localhost:8888"

# ─── Lab environments ───────────────────────────────────────────────────────

# Shared pre-flight: tear down any running lab before starting a new one.
lab-preflight: down

lab-orm: lab-preflight
	docker compose $(BASE) -f labs/orm/compose.yml up -d --build --remove-orphans
	@echo "PostgreSQL available at localhost:5432"
	@echo "MyST docs: http://localhost:3000"

lab-sql: lab-preflight
	docker compose $(BASE) -f labs/sql/compose.yml up -d --build --remove-orphans
	@echo "MSSQL available at localhost:1433 (SA / see .env or default password)"
	@echo "Run 'make sql-restore' to restore AdventureWorks and Northwind databases."
	@echo "MyST docs: http://localhost:3000"

lab-nosql: lab-preflight
	docker compose $(BASE) -f labs/nosql/compose.yml up -d --build --remove-orphans
	@echo "MongoDB available at localhost:27017"
	@echo "MyST docs: http://localhost:3000"

lab-replica-set: lab-preflight
	docker compose $(BASE) -f labs/replica-set/compose.yml up -d --build --remove-orphans
	@echo "Waiting for Mongo nodes to start..."
	sleep 5
	$(MAKE) replica-set-init
	@echo "MyST docs: http://localhost:3000"

lab-sharded: lab-preflight
	docker compose $(BASE) -f labs/sharded/compose.yml up -d --build --remove-orphans
	@echo "Waiting for cluster nodes to start..."
	sleep 10
	$(MAKE) sharded-init
	@echo "MyST docs: http://localhost:3000"

lab-distributed: lab-preflight
	docker compose $(BASE) -f labs/distributed/compose.yml up -d --build --remove-orphans
	@echo "Gateway API: http://localhost:8000"
	@echo "Redis:       localhost:6379"
	@echo "MyST docs:   http://localhost:3000"

lab-web: lab-preflight
	docker compose $(BASE) -f labs/web/compose.yml up -d --build --remove-orphans
	@echo "MyST docs: http://localhost:3000"

lab-redis: lab-preflight
	docker compose $(BASE) -f labs/redis/compose.yml up -d --build --remove-orphans
	@echo "Redis available at localhost:6379"
	@echo "MyST docs: http://localhost:3000"

lab-redis-sentinel: lab-preflight
	docker compose $(BASE) -f labs/redis-sentinel/compose.yml up -d --build --remove-orphans
	@echo "Redis nodes:     redis-1:6379, redis-2:6379, redis-3:6379"
	@echo "Redis sentinels: redis-sentinel-1:26379 (quorum of 3)"
	@echo "MyST docs:       http://localhost:3000"

lab-redis-cluster: lab-preflight
	docker compose $(BASE) -f labs/redis-cluster/compose.yml up -d --build --remove-orphans
	@echo "Waiting for cluster nodes to start..."
	sleep 8
	$(MAKE) redis-cluster-init
	@echo "MyST docs: http://localhost:3000"

lab-neo4j: lab-preflight
	docker compose $(BASE) -f labs/neo4j/compose.yml up -d --build --remove-orphans
	@echo "Neo4j browser: http://localhost:7474  (neo4j / password)"
	@echo "Bolt:          localhost:7687"
	@echo "MyST docs:     http://localhost:3000"

lab-neo4j-cluster: lab-preflight
	docker compose $(BASE) -f labs/neo4j-cluster/compose.yml up -d --build --remove-orphans
	$(MAKE) neo4j-cluster-init
	@echo "MyST docs: http://localhost:3000"

lab-streaming: lab-preflight
	docker compose $(BASE) -f labs/streaming/compose.yml up -d --build --remove-orphans
	@echo "MyST docs (workspace):      http://localhost:3000"
	@echo "JupyterLab (spark):         http://localhost:8888  (Spark driver, local[*] mode)"
	@echo "Kafka brokers (in-cluster): kafka-1:9092, kafka-2:9092, kafka-3:9092"
	@echo "Kafka brokers (host):       localhost:19092, localhost:19093, localhost:19094"
	@echo "Spark UI:                   http://localhost:4040  (while a query is running)"
	@echo "Kafka UI (Kafbat):          http://localhost:18080  (topics, partitions, consumer-group lag)"

lab-monitoring: lab-preflight
	docker compose $(BASE) -f labs/monitoring/compose.yml up -d --build --remove-orphans
	@echo "MyST docs (workspace):      http://localhost:3000"
	@echo "JupyterLab (workspace):     http://localhost:8888"
	@echo "Grafana:                    http://localhost:3001  (admin / admin)"
	@echo "Prometheus:                 http://localhost:9090"
	@echo "Spark master UI:            http://localhost:8080"
	@echo "Spark worker UIs:           http://localhost:8081, http://localhost:8082"
	@echo "Postgres (host):            localhost:5432  (user app / password app / db clicks)"
	@echo "Kafka brokers (in-cluster): kafka-1:9092, kafka-2:9092"
	@echo "Kafka brokers (host):       localhost:19092, localhost:19093"

# ─── Project scaffolds ──────────────────────────────────────────────────────

new-project:
	@uv run python3 scripts/new-project.py $(ARGS)

test-scaffolds:
	@uv run python3 scripts/test_scaffolds.py $(ARGS)

# ─── Common operations ──────────────────────────────────────────────────────

down:
	@for d in labs/*/; do \
		f="$$d/compose.yml"; \
		[ -f "$$f" ] && docker compose $(BASE) -f "$$f" down 2>/dev/null || true; \
	done
	docker compose $(BASE) down 2>/dev/null || true

reset:
	@for d in labs/*/; do \
		f="$$d/compose.yml"; \
		[ -f "$$f" ] && docker compose $(BASE) -f "$$f" down -v --remove-orphans 2>/dev/null || true; \
	done
	docker compose $(BASE) down -v --remove-orphans 2>/dev/null || true

shell:
	docker exec -it $$(docker ps --filter "name=workspace" -q | head -1) bash

# ─── Lab-specific helpers ────────────────────────────────────────────────────

replica-set-init:
	bash labs/replica-set/init.sh

sharded-init:
	bash labs/sharded/init.sh

sql-restore:
	bash labs/sql/restore.sh

redis-cluster-init:
	bash labs/redis-cluster/init.sh

neo4j-cluster-init:
	bash labs/neo4j-cluster/init.sh

# ─── Instructor convenience ──────────────────────────────────────────────────

convert:
	@[ -n "$(FILE)" ] || (echo "Usage: make convert FILE=materials/python/01-orm/01-lesson.md" && exit 1)
	jupytext --from md:myst --to py:percent $(FILE)
	@echo "Created $$(echo $(FILE) | sed 's/\.md$$/.py/')"
	@echo "Remember: discard this file after use -- it is not the source of truth."
