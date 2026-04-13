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

# Bonus — `cache()` and the Storage tab

**Goal:** Observe what `cache()` actually does. Run the same expensive scan twice with and without caching; watch the Storage tab populate after the first action.

Steps:

1. Read `data/medium/`, filter for `trip_distance > 0`. Time `count()` twice in a row.
2. Now `cache()` the filtered DataFrame, call `count()` once to materialize, then time `count()` again. Open the **Storage** tab in the Driver UI to see the cached blocks.
3. `unpersist()` and verify the Storage tab clears.

```{code-cell}
import time
from pyspark.sql import SparkSession

spark = (SparkSession.builder
    .appName("bonus-cache")
    .getOrCreate())

df = spark.read.parquet("../data/medium/").filter("trip_distance > 0")

for label in ("cold", "warm"):
    t0 = time.time()
    n = df.count()
    print(f"{label}: {n} rows in {time.time()-t0:.2f}s")
```

```{code-cell}
df.cache()
df.count()  # materialize
for label in ("cached-1", "cached-2"):
    t0 = time.time()
    n = df.count()
    print(f"{label}: {n} rows in {time.time()-t0:.2f}s")

df.unpersist()
```
