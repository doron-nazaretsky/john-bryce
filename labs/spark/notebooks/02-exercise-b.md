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

# Exercise B — BI aggregates to Postgres

**Story:** The BI team wants two daily/hourly summary tables in Postgres they can plug into their dashboard. You will produce them with SparkSQL and write them via JDBC.

**Targets** (schema already created by `init.sh`):

| Table | Columns | Grain |
|---|---|---|
| `zone_daily_stats` | `zone_id INT`, `stat_date DATE`, `trip_count BIGINT`, `total_revenue NUMERIC`, `avg_tip_pct NUMERIC` | one row per (zone, day) |
| `hourly_demand`    | `zone_id INT`, `hour INT`, `trips BIGINT`                                                              | one row per (zone, hour) |

**Tasks:**

1. Build the two DataFrames with SparkSQL from `data/medium/` (4 months) joined to the zone lookup.
2. Write them to Postgres with `df.write.jdbc(url, table, mode="overwrite")` using the simplest possible options.
3. **Open the Driver UI Executors tab.** How many tasks are writing? Why?
4. Improve the write: `repartition(N)` before the write and pass `numPartitions` + `batchsize` to the JDBC writer. Compare wall-clock time.

Validate by calling `validate_exercise_b()` — it queries Postgres directly and checks row counts + invariants.

```{code-cell}
import os, sys, time
sys.path.insert(0, "..")
from helpers import validate_exercise_b

from pyspark.sql import SparkSession

spark = (SparkSession.builder
    .appName("exercise-b")
    .getOrCreate())

PG_URL      = os.environ["PG_URL"]
PG_USER     = os.environ["PG_USER"]
PG_PASSWORD = os.environ["PG_PASSWORD"]

spark.read.parquet("../data/medium/").createOrReplaceTempView("trips")
(spark.read.option("header", True).option("inferSchema", True)
    .csv("../data/zones.csv")
    .createOrReplaceTempView("zones"))

print("Driver UI:", spark.sparkContext.uiWebUrl)
```

## Task 1 — Build `zone_daily_stats`

Expected columns (in this order): `zone_id`, `stat_date`, `trip_count`, `total_revenue`, `avg_tip_pct`.

```{code-cell}
# Your SparkSQL here.
zone_daily = spark.sql("""
    -- TODO
""")
zone_daily.show(5)
```

## Task 2 — Build `hourly_demand`

Expected columns: `zone_id`, `hour`, `trips`.

```{code-cell}
# Your SparkSQL here.
hourly = spark.sql("""
    -- TODO
""")
hourly.show(5)
```

## Task 3 — Naive write (one task)

Run this cell, then watch the Executors / Stages tabs. How many tasks are writing? Why?

```{code-cell}
# Naive write — your code:
# t0 = time.time()
# zone_daily.write.jdbc(PG_URL, "zone_daily_stats", mode="overwrite",
#                       properties={"user": PG_USER, "password": PG_PASSWORD,
#                                   "driver": "org.postgresql.Driver"})
# print("naive seconds:", round(time.time() - t0, 2))
```

## Task 4 — Parallel write

Repartition before the write and pass `numPartitions` + `batchsize`. Compare wall-clock against Task 3.

```{code-cell}
# Your improved write here.
# (zone_daily.repartition(4)
#     .write.format("jdbc")
#     .option("url", PG_URL)
#     .option("dbtable", "zone_daily_stats")
#     .option("user", PG_USER)
#     .option("password", PG_PASSWORD)
#     .option("driver", "org.postgresql.Driver")
#     .option("numPartitions", 4)
#     .option("batchsize", 5000)
#     .mode("overwrite")
#     .save())
```

```{code-cell}
validate_exercise_b()
```
