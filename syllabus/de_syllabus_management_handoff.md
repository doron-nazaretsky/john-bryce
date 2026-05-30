# DE Course Syllabus — Proposed Redesign (Management Handoff)

**Same envelope: 34 meetings / 153 hours (4.5h each).** This is a pure reallocation — no extra time requested. We cut DevOps-owned and legacy/analyst material and over-weighted topics, and reinvested in software-engineering depth, a proper relational deep-dive, data pipelines, data quality, and a protected capstone. The redesign also adds two narrative spines (one anchor project built end-to-end; distributed systems taught hands-on) and a local→cloud progression — directly addressing last cycle's feedback that topics felt fragmented and the cloud felt unfamiliar.

---

## Table 1 — Current syllabus and what changed

| Current module | Mtgs | Change | Where it goes in the new syllabus |
|---|--:|---|---|
| Git & Version Control | 1 | **Merged** | Into *Software Engineering with Python* (Git walk-through + self-learning kit) |
| Python Programming for DE | 7 | **Reframed, −1** | *Software Engineering with Python* (6) — pandas/NumPy/viz cut; added data structures & Big O, OOP/design patterns, testing/TDD, AI-assisted dev & SDD, ORM/migrations |
| Docker & Containerization | 1 | **Merged, moved to start** | Into *Foundations: Docker, Linux & Computing* |
| Advanced SQL | 1 | **Expanded ×3, reoriented** | *Relational Databases, Deep* (3) — DB internals, optimizer/EXPLAIN, indexes, MVCC. (Core SQL becomes a prerequisite) |
| Big Data Concepts & Architecture | 3 | **Reorganized, −1** | *Data Warehousing, OLAP & MPP* (2) — dimensional modeling + storage formats + MPP; Hadoop tour cut |
| NoSQL Databases | 4 | **Shrunk ×½** | *NoSQL & Specialized Stores* (2) — key-value + document; Elasticsearch dropped (redundant with monitoring) |
| Kubernetes for Data Engineers | 2 | **Cut** | Removed (DevOps-owned); brief EKS/K8s mention in Cloud & Spark |
| Big Data Pipelines & Orchestration | 3 | **Expanded & absorbed** | *Building Data Pipelines with Python* (5) — by-hand → Airflow → dbt ELT; Data Mesh & Intro-to-DS cut |
| Apache Spark | 3 | **Expanded +1, reframed** | *Distributed Processing — Spark* (4) — build-primitive-first + EMR scale-up; MLlib cut |
| Real-Time Streams & Message Queues | 3 | **Shrunk −1** | *Streaming & Event Data — Kafka* (2) — RabbitMQ & managed-Kafka dropped |
| Cloud Engineering – AWS | 3 | **Restructured & reordered** | *Cloud Data Engineering* (3) — concepts not AWS-specifics; lift pipeline to cloud + Terraform/CI-CD; now **before** Spark |
| Monitoring & Observability | 1 | **Reframed** | *DataOps: Observability & CI/CD* (1) |
| AI & Big Data – GenAI | 2 | **Re-pointed** | *AI for Data Engineers* (2) — Agents + DS pipelines/MLOps; "dev-with-AI" moved into Software Engineering |
| — | — | **NEW** | *Data Quality & Testing* (1) — biggest gap in the current course |
| — | — | **NEW (protected)** | *Capstone & Integration* (1) — previously buried inside the GenAI module |
| — | — | **NEW content** | OS/computing fundamentals (in Foundations); data structures & Big O (in Software Engineering) |

---

## Table 2 — New syllabus (standalone)

| # | Module | Mtgs | Hrs | Focus |
|--:|---|--:|--:|---|
| 1 | Foundations: Docker, Linux & Computing | 2 | 9 | Docker as the shared lab environment; OS/memory/CPU/disk/network & scaling fundamentals |
| 2 | Software Engineering with Python | 6 | 27 | Engineering through Python: data structures & Big O, OOP/patterns, testing/TDD, AI-assisted dev & SDD |
| 3 | Relational Databases, Deep | 3 | 13.5 | DB internals (Postgres), optimizer/EXPLAIN, indexes, transactions & MVCC |
| 4 | Data Warehousing, OLAP & MPP | 2 | 9 | OLTP vs OLAP, dimensional modeling, storage formats, MPP (distributed systems begins) |
| 5 | Building Data Pipelines with Python | 5 | 22.5 | Medallion pipelines by hand → Airflow → dbt ELT; idempotency, incrementality, scheduling |
| 6 | Cloud Data Engineering | 3 | 13.5 | Cloud concepts & services; lift the project to AWS (S3/ECS/Glue/Athena/MWAA) + Terraform/CI-CD |
| 7 | Distributed Processing — Spark | 4 | 18 | Build primitive Spark; architecture/tradeoffs; failure modes; migrate to PySpark on EMR at scale |
| 8 | Streaming & Event Data — Kafka | 2 | 9 | The distributed log; replication & delivery semantics; Kafka → Spark Structured Streaming hands-on |
| 9 | Data Quality & Testing | 1 | 4.5 | Quality dimensions, dbt tests + dbt-expectations, contracts/SLAs |
| 10 | DataOps: Observability & CI/CD | 1 | 4.5 | Operational observability (Grafana hands-on), alerting, CI/CD for pipelines |
| 11 | NoSQL & Specialized Stores | 2 | 9 | Key-value (Redis) + document (MongoDB): what each gives, access patterns, hands-on |
| 12 | AI for Data Engineers | 2 | 9 | Agents (tool-agnostic) + DS pipelines & basic MLOps |
| 13 | Capstone & Integration | 1 | 4.5 | Present & defend the end-to-end project; mock interviews; final readiness |
| | **Total** | **34** | **153** | |
