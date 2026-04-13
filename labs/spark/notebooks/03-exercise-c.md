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

# Exercise C — Zone profile documents to MongoDB

**Story:** The frontend team wants one document per pickup zone with everything needed to render a zone-detail page in a single read. Your job: build that document shape with Spark and land it in MongoDB.

**Target document** (one per zone in `taxi.zone_profiles`):

```json
{
  "_id": 132,
  "zone_name": "JFK Airport",
  "borough": "Queens",
  "top_destinations": [{"zone_id": 230, "trips": 12345}, ...],   // top 5
  "hourly_demand": [101, 88, 76, ...],                            // length 24, indexed by hour
  "payment_breakdown": {"credit": 4321, "cash": 999, "other": 50}
}
```

**Tasks:**

1. Compute the four pieces (zone metadata, top destinations, hourly demand, payment breakdown) as separate SparkSQL views.
2. Combine them into one DataFrame with the document shape above. **You will need PySpark DataFrame API here** (`F.struct`, `F.collect_list`, a window for top-N by zone) — this is the one place SQL alone is awkward.
3. Write to MongoDB using the Spark connector:
   ```python
   df.write.format("mongodb") \
     .option("connection.uri", "mongodb://spark-mongo:27017") \
     .option("database", "taxi") \
     .option("collection", "zone_profiles") \
     .mode("overwrite").save()
   ```

Validate by calling `validate_exercise_c()` — pulls a sample doc with `pymongo` and asserts shape.

```{code-cell}
import os, sys
sys.path.insert(0, "..")
from helpers import validate_exercise_c

from pyspark.sql import SparkSession, functions as F, Window

spark = (SparkSession.builder
    .appName("exercise-c")
    .getOrCreate())

MONGO_URI = os.environ["MONGO_URI"]

spark.read.parquet("../data/medium/").createOrReplaceTempView("trips")
(spark.read.option("header", True).option("inferSchema", True)
    .csv("../data/zones.csv")
    .createOrReplaceTempView("zones"))

print("Driver UI:", spark.sparkContext.uiWebUrl)
```

## Step 1 — Per-zone hourly demand (24-element array)

Hint: build (zone, hour, trips) in SQL, then pivot or use `F.collect_list` ordered by hour.

```{code-cell}
# Your code here.
hourly_demand = None  # DataFrame: zone_id, hourly_demand (array<int> length 24)
```

## Step 2 — Top 5 destinations per zone

Hint: row_number() window over (PULocationID order by trips desc), filter rn <= 5, then `F.collect_list(F.struct("zone_id", "trips"))`.

```{code-cell}
# Your code here.
top_destinations = None  # DataFrame: zone_id, top_destinations (array<struct<zone_id, trips>>)
```

## Step 3 — Payment breakdown per zone

Map TLC `payment_type` codes (1=credit, 2=cash, others=other) into a struct/dict with three counts.

```{code-cell}
# Your code here.
payment_breakdown = None  # DataFrame: zone_id, payment_breakdown (struct<credit, cash, other>)
```

## Step 4 — Assemble the documents and write to Mongo

```{code-cell}
# Your code here. Join the four pieces on zone_id, alias zone_id -> _id, then:
#
# (profiles.write.format("mongodb")
#     .option("connection.uri", MONGO_URI)
#     .option("database", "taxi")
#     .option("collection", "zone_profiles")
#     .mode("overwrite").save())
```

```{code-cell}
validate_exercise_c()
```
