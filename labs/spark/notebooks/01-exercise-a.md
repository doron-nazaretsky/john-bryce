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

# Exercise A — Exploratory analytics with SparkSQL

**Story:** You just joined the analytics team for an NYC taxi platform. Before building any pipelines, you want to understand the data: when do people ride, where do they ride from, how do tips behave?

**Tasks** — write SparkSQL for each:

1. **Trips per hour of day** — pickup hour (0..23), trip count, sorted by hour.
2. **Top 10 pickup zones by total revenue** — join on the `zones` view to get the human-readable zone name and borough.
3. **Tip-percentage percentiles by payment type** — for each `payment_type`, compute the 25th / 50th / 75th percentile of `tip_amount / fare_amount * 100` (filter out fares <= 0 to avoid divide-by-zero).

**Final write:** persist your *trips-per-hour* result (or another result of your choice) as **partitioned parquet** under `data/outputs/exercise_a/` partitioned by `year` and `month` (derive these from `tpep_pickup_datetime`).

**Expected output shape (Task 1):**
```
+----+----------+
|hour|trip_count|
+----+----------+
|   0|     12345|
|   1|      9876|
...
```

Validate by calling `validate_exercise_a(df)` at the bottom — it checks the result is non-empty, grouping keys are non-null, and metric columns are non-negative.

```{code-cell}
import sys
sys.path.insert(0, "..")
from helpers import validate_exercise_a

from pyspark.sql import SparkSession

spark = (SparkSession.builder
    .appName("exercise-a")
    .getOrCreate())

trips = spark.read.parquet("../data/small/")
trips.createOrReplaceTempView("trips")

zones = (spark.read
    .option("header", True)
    .option("inferSchema", True)
    .csv("../data/zones.csv"))
zones.createOrReplaceTempView("zones")

print("Driver UI:", spark.sparkContext.uiWebUrl)
trips.printSchema()
```

## Task 1 — Trips per hour of day

```{code-cell}
# Your SparkSQL here.
trips_per_hour = spark.sql("""
    -- TODO
""")
trips_per_hour.show(24)
```

## Task 2 — Top 10 pickup zones by revenue

```{code-cell}
# Your SparkSQL here.
top_zones = spark.sql("""
    -- TODO: join trips with zones, sum total_amount, top 10
""")
top_zones.show()
```

## Task 3 — Tip % percentiles by payment type

```{code-cell}
# Your SparkSQL here. Hint: percentile_approx(metric, array(0.25, 0.5, 0.75))
tip_percentiles = spark.sql("""
    -- TODO
""")
tip_percentiles.show()
```

## Final step — partitioned parquet write

Write `trips_per_hour` (or any task result) to `data/outputs/exercise_a/` partitioned by `year` and `month`.

```{code-cell}
# Your write here. Example shape:
# (df_with_year_month
#     .write
#     .mode("overwrite")
#     .partitionBy("year", "month")
#     .parquet("data/outputs/exercise_a/"))
```

```{code-cell}
validate_exercise_a(trips_per_hour)
```
