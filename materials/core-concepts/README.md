# Core Concepts Reference Library

**Every technology is a bundle of well-known building blocks, assembled to solve a specific problem.**

Once you understand how replication, partitioning, or consensus works in general, learning any new system becomes a matter of asking: *which concepts did they pick, and why?* A Redis cluster, a Cassandra keyspace, and a Kafka topic are not different things -- they're the same dozen concepts configured differently.

This directory is a **tool-agnostic reference library**. It is not a sequential module to be taught front-to-back. It is a resource you encounter gradually: when a SQL lesson mentions B-trees, you follow the link here to understand the general concept, then return to the SQL lesson to see how it applies specifically to relational indexes.

---

## How to Use This Library

1. **Follow links from course materials** -- every time a concept appears in the SQL or NoSQL course, it links here
2. **Read the problem first** -- each file starts with the real-world problem that makes the concept necessary
3. **Return to the course material** -- the course material explains *why this specific tool chose this concept* and how it applies in context
4. **Come back when you see it again** -- the same concept appears in multiple tools; each appearance makes the concept more concrete

---

## Learning Path (Dependency Order)

The concepts build on each other. If you're reading this fresh, follow this order:

```
01-complexity-and-performance
  ├── Big O Notation                    ← foundation for everything else
  └── I/O and Storage Fundamentals      ← explains why data structures matter

02-data-structures
  ├── Hash Tables                       ← needs Big O
  ├── Trees for Storage                 ← needs Big O + I/O
  ├── LSM-Trees and SSTables            ← needs Trees + I/O
  ├── Probabilistic Structures          ← needs Big O
  └── Graphs and Traversal             ← needs Big O (adjacency complexity)

03-scaling
  ├── Vertical vs Horizontal            ← needs nothing, start here for scaling
  ├── Consistent Hashing                ← needs Hash Tables
  ├── Partitioning Strategies           ← needs Consistent Hashing
  └── Graph Partitioning               ← needs Graphs + Partitioning Strategies

04-distributed-systems
  ├── CAP Theorem                       ← needs Partitioning (to understand why partitions happen)
  ├── ACID vs BASE                      ← needs CAP Theorem
  ├── Consistency Models                ← needs ACID vs BASE
  └── Quorum and Tunable Consistency    ← needs Consistency Models + Replication Patterns

05-replication-and-availability
  ├── Replication Patterns              ← needs CAP Theorem
  ├── Consensus and Failover            ← needs Replication Patterns + Quorum
  └── Write-Ahead Logs                  ← needs I/O Fundamentals + Replication

06-architecture-patterns
  ├── Schema Strategies                 ← needs all of 01-04
  ├── Query Routing Patterns            ← needs Partitioning Strategies
  └── Polyglot Persistence              ← needs all of 01-06 (capstone)

07-application-patterns
  ├── Caching Patterns                  ← needs Hash Tables + I/O Fundamentals
  ├── Pub/Sub and Messaging             ← needs I/O Fundamentals
  └── Sync vs Async I/O                 ← needs nothing; useful background for Pub/Sub
```

---

## Concept-to-Technology Matrix

The same concepts appear across every data technology. This matrix shows where each concept is used -- the specific *how* and *why* is in each course's materials.

| Concept | PostgreSQL | MongoDB | Cassandra | Redis | Neo4j | Kafka (future) | Spark (future) |
|---------|-----------|---------|-----------|-------|-------|----------------|----------------|
| **Big O / Complexity** | Query planner cost models; index seek = O(log n), scan = O(n) | Same -- index seek vs collection scan | Same -- partition lookup vs full scatter | Hash lookup O(1); sorted set O(log n) | Traversal O(1) per hop (pointer); index scan O(log n) for starting nodes | Consumer lag as O(n) offset traversal | Catalyst optimizer cost model |
| **I/O & Storage** | Row-oriented pages (HEAP); columnar in foreign tables | BSON documents in WiredTiger pages | Column-family storage; SSTable files on disk | In-memory (RAM) -- I/O hierarchy reversed | Native graph store; nodes + relationships + properties in linked page files | Sequential log files on disk | Columnar (Parquet/ORC) for shuffle and output |
| **Hash Tables** | Hash join operator; hash indexes (PostgreSQL 10+) | Not primary -- uses B-trees | Not primary -- consistent hashing at cluster level | Core data structure -- entire keyspace is a hash map | Property lookups within a node use hash-map semantics | Consumer group partition assignment | Hash partitioning for shuffle; hash join |
| **B-Trees / Trees for Storage** | Primary storage structure (heap + B-tree indexes) | WiredTiger B-tree for all collection indexes | Not used -- LSM-tree instead | Sorted sets use a skip list (similar to B-tree) | B-tree indexes on node/relationship properties for scan starting points | Not applicable | Not applicable |
| **Graphs and Traversal** | Not applicable (relational model) | Not applicable | Not applicable | Not applicable | **Core model** -- nodes, edges, index-free adjacency, BFS/DFS traversal | Not applicable | GraphX for distributed graph computation |
| **LSM-Trees / SSTables** | Not used (B-tree based) | Not used (WiredTiger B-tree) | Core storage engine (commit log + memtable + SSTable) | Not used -- in-memory | Not used | Log segments are SSTable-like (immutable, compacted) | Not applicable |
| **Probabilistic Structures** | Bloom filters in bitmap index scan; HLL in pg_hll | Not built-in | Bloom filters per SSTable for read optimization | HyperLogLog (`PFADD`/`PFCOUNT`) built-in | Not built-in | Not built-in | BloomFilter join pre-filter; approx_count_distinct |
| **Vertical vs Horizontal** | Primarily vertical; Citus extension for horizontal | Horizontal via sharding; replica sets for read scale | Horizontal by design; peer-to-peer ring | Vertical for single instance; Redis Cluster for horizontal | Primarily vertical; causal clustering for read scale; Fabric for manual sharding | Horizontal by design; add brokers and partitions | Horizontal -- Spark is a distributed engine |
| **Consistent Hashing** | Not used | Not used (uses range sharding + balancer) | Token ring -- consistent hashing is the core distribution mechanism | Hash slots (16,384 slots; variation of consistent hashing) | Not used | Not used directly | Not used directly |
| **Partitioning** | Table partitioning (range, list, hash); partition pruning | Sharding (range or hash) per collection | Partition key required; row assigned to token range | Cluster uses hash slots across nodes | Graph partitioning is NP-hard; Fabric routes subgraphs manually | Topics partitioned across brokers; partition key = message key | Spark partitions the RDD/DataFrame across executors |
| **Graph Partitioning** | Not applicable | Not applicable | Not applicable | Not applicable | **Core challenge** -- edge-cut and vertex-cut strategies; Fabric for manual sharding | Not applicable | GraphX uses vertex-cut partitioning |
| **CAP Theorem** | CA (single node) -- P not applicable | CP (default) -- refuses reads during partition | AP (default) -- serves stale reads, tunes per query | CA (single) / CP (cluster -- partially available during partition) | CP -- refuses writes when Raft majority lost; reads from secondaries continue | AP -- producers keep writing; consumers tolerate lag | Not directly applicable |
| **ACID vs BASE** | Full ACID by default; MVCC for isolation | ACID for single-document; BASE for replica reads | BASE by default; tunable per operation | Atomic per command; no multi-key transactions (base) | Full ACID per transaction; Raft guarantees durability | BASE -- at-least-once or exactly-once per config | Not transactional by default; Delta Lake adds ACID |
| **Consistency Models** | Serializable (max), Read Committed (default) | Linearizable, Majority, Local per read concern | ONE, QUORUM, ALL per operation | Single-threaded = atomic per command; eventual across replicas | Causal consistency via bookmarks; read-your-own-writes guarantee | At-most-once, at-least-once, exactly-once semantics | Not applicable (batch processing) |
| **Quorum** | Not applicable (single node) | `w: majority` write concern; `majority` read concern | `ONE`, `QUORUM`, `ALL` consistency levels -- the canonical implementation | Not used (single-threaded) | Raft majority of primaries required before commit | ISR (in-sync replicas) -- producer acks=all is quorum | Not applicable |
| **Replication Patterns** | Primary-secondary (streaming replication); Patroni for failover | Primary-secondary (replica sets); automatic election | Peer-to-peer (leaderless); any node accepts writes | Primary-secondary; Redis Sentinel or Cluster | Primary-secondary (causal clustering: core primaries + read secondaries) | Leader-follower per partition; ISR list for durability | Not applicable (stateless) |
| **Consensus / Failover** | External (Patroni + etcd or Consul manages election) | Built-in (Raft-inspired election in replica set) | Not needed -- leaderless; no primary to elect | Redis Sentinel (quorum of sentinels), or Cluster mode | Built-in Raft for leader election among primaries | Controller election via ZooKeeper or KRaft (built-in Raft) | Not applicable |
| **Write-Ahead Logs** | WAL (PostgreSQL core durability and replication mechanism) | Oplog (replication) + WiredTiger journal (durability) | Commit log (durability) + hints for hinted handoff | AOF (Append-Only File) for durability; RDB for snapshots | Transaction log (durability + replication stream to secondaries) | Log segments ARE the data -- Kafka IS a distributed WAL | Write-ahead logs in Delta Lake / Iceberg |
| **Schema Strategies** | Schema-on-write (DDL enforced); normalized (3NF common), star schema for analytics | Schema-on-read (flexible documents); denormalized (embed related data) | Schema-on-write for column families; heavily denormalized per query | Schema-free (values are opaque bytes) | Schema-optional; labels and relationship types are conventions, not enforced DDL | Schema-on-write with Avro/Protobuf/JSON Schema registry | Schema-on-read (infer from data) or schema-on-write (DDL) |
| **Query Routing** | No routing (single node); with Citus: coordinator routes | mongos routes targeted vs scatter-gather based on shard key | Coordinator routes targeted or scatter-gather by partition key | Client-side routing via hash slots | Driver routing (read → any primary/secondary; write → leader); Fabric for cross-shard | Producer routes by key; consumer group manages partition assignment | Spark planner decides: broadcast vs shuffle join |
| **Polyglot Persistence** | Often the "primary store of truth" in polyglot architectures | Often the flexible secondary store for heterogeneous data | Time-series / write-heavy workloads in polyglot setup | Cache layer and session store in polyglot setup | Graph traversal layer; often alongside a relational or document DB for tabular data | Event backbone / message bus connecting stores | Analytics computation layer over multiple storage backends |
| **Caching Patterns** | Not applicable (persistent store) | Not applicable (persistent store) | Not applicable (persistent store) | Core use case -- cache-aside, write-through, TTL, eviction policies | Not applicable (persistent graph store) | Not applicable | Not applicable |
| **Pub/Sub Patterns** | LISTEN/NOTIFY (basic pub/sub) | Change streams (event-driven consumers) | Not built-in | Built-in pub/sub (fire-and-forget) + Streams (durable, consumer groups) | Not built-in | Core model -- topics, consumer groups, at-least-once delivery | Not applicable |

---

## File Index

### 01 — Complexity and Performance
- [Big O Notation](01-complexity-and-performance/01-big-o-notation.md)
- [I/O and Storage Fundamentals](01-complexity-and-performance/02-io-and-storage-fundamentals.md)

### 02 — Data Structures
- [Hash Tables](02-data-structures/01-hash-tables.md)
- [Trees for Storage](02-data-structures/02-trees-for-storage.md)
- [LSM-Trees and SSTables](02-data-structures/03-lsm-trees-and-sstables.md)
- [Probabilistic Structures](02-data-structures/04-probabilistic-structures.md)
- [Graphs and Traversal](02-data-structures/05-graphs-and-traversal.md)

### 03 — Scaling
- [Vertical vs Horizontal Scaling](03-scaling/01-vertical-vs-horizontal.md)
- [Partitioning Strategies](03-scaling/02-partitioning-strategies.md)
- [Consistent Hashing](03-scaling/03-consistent-hashing.md)
- [Graph Partitioning](03-scaling/04-graph-partitioning.md)

### 04 — Distributed Systems
- [CAP Theorem](04-distributed-systems/01-cap-theorem.md)
- [ACID vs BASE](04-distributed-systems/02-acid-vs-base.md)
- [Consistency Models](04-distributed-systems/03-consistency-models.md)
- [Quorum and Tunable Consistency](04-distributed-systems/04-quorum-and-tunable-consistency.md)

### 05 — Replication and Availability
- [Replication Patterns](05-replication-and-availability/01-replication-patterns.md)
- [Consensus and Failover](05-replication-and-availability/02-consensus-and-failover.md)
- [Write-Ahead Logs](05-replication-and-availability/03-write-ahead-logs.md)

### 06 — Architecture Patterns
- [Schema Strategies](06-architecture-patterns/01-schema-strategies.md)
- [Query Routing Patterns](06-architecture-patterns/02-query-routing-patterns.md)
- [Polyglot Persistence](06-architecture-patterns/03-polyglot-persistence.md)

### 07 — Application Patterns
- [Caching Patterns](07-application-patterns/01-caching-patterns.md)
- [Pub/Sub and Messaging](07-application-patterns/02-pubsub-and-messaging.md)
- [Synchronous vs Asynchronous I/O](07-application-patterns/03-sync-vs-async-communication.md)
