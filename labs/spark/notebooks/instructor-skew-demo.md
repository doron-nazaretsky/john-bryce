---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.19.1
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# Instructor — Skew reveal and mitigation (companion to Exercise D)

Run this on the projector once students have attempted Exercise D and are stuck on the perf question.

Outline:

1. Diagnose: re-run D's query, then inspect task-duration distribution.
2. Mitigation 1 — **salting** the hot key.
3. Mitigation 2 — **AQE skew handling** (`spark.sql.adaptive.enabled=true` + `spark.sql.adaptive.skewJoin.enabled=true`). Spark 3.5 has AQE on by default; D pinned it off so skew was visible.
4. Discuss tradeoffs.

```{code-cell}
import time
from pyspark.sql import SparkSession, functions as F

spark = (SparkSession.builder
    .appName("instructor-skew")
    .getOrCreate())

trips = spark.read.parquet("../data/large/")
trips.createOrReplaceTempView("trips")
```

## 1. Reproduce the skewed query

```{code-cell}
t0 = time.time()
skewed = spark.sql("""
    SELECT PULocationID, payment_type,
           COUNT(*)        AS trip_count,
           AVG(fare_amount) AS avg_fare
    FROM trips
    GROUP BY PULocationID, payment_type
""")
_ = skewed.count()
print(f"AQE off, no salting: {time.time()-t0:.1f}s — open the stage view, look at task-duration min vs max")
```

## 2. Mitigation — salt the hot key

Add a random salt 0..N-1 to the grouping key, aggregate twice (once with salt, once without).

```{code-cell}
N = 16
salted = (trips
    .withColumn("salt", (F.rand() * N).cast("int"))
    .groupBy("PULocationID", "payment_type", "salt")
    .agg(F.count("*").alias("c"), F.sum("fare_amount").alias("s"))
    .groupBy("PULocationID", "payment_type")
    .agg(F.sum("c").alias("trip_count"),
         (F.sum("s") / F.sum("c")).alias("avg_fare")))

t0 = time.time()
_ = salted.count()
print(f"salted (N={N}): {time.time()-t0:.1f}s — task durations should be much more uniform")
```

## 3. Mitigation — AQE skew handling

```{code-cell}
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")

t0 = time.time()
_ = spark.sql("""
    SELECT PULocationID, payment_type,
           COUNT(*) AS trip_count, AVG(fare_amount) AS avg_fare
    FROM trips GROUP BY PULocationID, payment_type
""").count()
print(f"AQE on: {time.time()-t0:.1f}s — note coalesced partitions in the SQL tab")
```
