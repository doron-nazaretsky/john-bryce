## Intro
Build a Docker-based local environment for teaching Spark and SparkSQL. The setup must let students experience real distributed computing concepts (shuffles, stages, tasks, parallelism) on a single machine, and run honest benchmarks comparing SparkSQL vs pandas under identical resource constraints.

## Focus
- Real hands on experience so the students must write real spark code during the lesson, not just run existing code in cells.
- Theory is less of a focus here mainly they need to practice writing and running spark, we can use different approaches to invoking spark: spark-submit, interactive, native jupyter, spark cluster through jupyter, anything else?
- Monitoring written code execution to check out performance and what actually happens under the hood (to an extent of understanding the parallelism, shuffling and some Spark dag execution and cache concepts)


## Architecture
A docker-compose.yml with:
1 Spark master container (pinned to its own core, lightweight coordination role)
3 Spark worker containers (each pinned to a separate core via cpuset, each with mem_limit: 2g)
1 Jupyter notebook container with PySpark client connected to the cluster AND pandas installed locally (pinned to its own core, mem_limit: 2g — same constraints as each individual Spark worker)
CPU pinning via cpuset ensures parallelism is real (not time-sliced). Each worker gets a different logical core inside the Docker VM. The pandas container gets the same single core and same memory as one Spark worker — making performance comparisons honest.


## What the notebook should demonstrate
A single Jupyter notebook that runs both pandas and SparkSQL on the same logical queries, sweeping across dataset sizes to show crossover points:
Small scale (~100K–1M rows): pandas wins, Spark overhead is visible
Medium scale (~10M–50M rows): Spark catches up on multi-stage operations
Large scale (~100M+ rows or exceeding 2GB): pandas OOMs or crawls, Spark handles it via spill-to-disk across workers

## Benchmark categories 
(chosen because they are single-threaded in pandas, parallel in Spark):
Simple filter (pandas stays competitive longest)
High-cardinality groupby-aggregate (shuffle model shines)
Multi-table join (distributed advantage clearest)
Window function over large partition (memory pressure hits pandas hardest)

Avoid making headline demos out of simple numeric reductions (.sum(), .mean()) — pandas/NumPy can parallelize these via BLAS at the C level, which muddies the comparison.

## Spark UI teaching points
The Spark UI (port 4040) should be exposed to the host. Key concepts to surface:
DAG visualization and stage breakdown
Task distribution across executors
Shuffle read/write sizes
Partition pruning and broadcast vs sort-merge joins via EXPLAIN
Caching effects (CACHE TABLE / .cache())
Skew detection (intentionally skewed keys showing uneven task durations)

## Technical notes
Use Bitnami Spark Docker images (bitnami/spark) — they support master/worker topology out of the box
cpuset maps to virtual cores inside Docker's Linux VM, not directly to host physical cores — this is fine, parallelism is still real

## Open Questions For Discussion
- Where to get the right data, we could generate synthetic data with faker or numpy/random-based but I am not sure it would be easy to generate something meaningful, maybe using existing datasets? the problem with existing datasets is
that they are fixed size so maybe we can take for example a very big one and slice it to the small, medium, large categories dataset.
- What is the best way to expose this lesson to the students, since it should be a real hands on session where they write code it's not suitable for our materials execution model where the code is always readonly. I also would like to make them practice writing real ETL / ELT pipelines with a bit of APIs, Files, Databases (SQL, some NoSQL like mongo to spice things up)