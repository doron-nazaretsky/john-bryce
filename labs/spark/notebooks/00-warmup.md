---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.19.1
kernelspec:
  display_name: Python 3 (ipykernel)
  language: python
  name: python3
---

# Warm-up: Connect, UI tour, narrow vs wide

Goals (about 30 minutes):

1. Connect this notebook (the **driver**) to the standalone Spark cluster running in `spark-master` + 2 workers.
2. Open the Spark UIs and learn what's where:
   - **Master UI** at <http://localhost:8080> — shows registered workers, cores, memory.
   - **Driver UI** at <http://localhost:4040> — shows the current application's jobs, stages, tasks, storage, executors. Available only while a `SparkSession` is alive.
3. Run a **narrow** transformation (filter + count) and a **wide** transformation (groupBy + count) over the same data and contrast the stage / shuffle pictures.

> Spark Connect is an alternative client/server mode (driver runs remotely). We are using **classic mode** here: the driver is this Jupyter container, which talks RPC to the master. Same SparkSQL idioms either way.

```{code-cell} ipython3
from pyspark.sql import SparkSession

spark = (SparkSession.builder
    .appName("warmup")
    .getOrCreate())

print("Driver UI:", spark.sparkContext.uiWebUrl)
```

## Narrow transformation: filter + count

Expected: **one stage**, several tasks (one per input partition), `Shuffle Read/Write` columns are zero or empty in the UI.

```{code-cell} ipython3
n_long_trips = (spark.read.parquet("../data/small/")
                    .filter("trip_distance > 1")
                    .count())
print("long trips:", n_long_trips)
```

## Wide transformation: groupBy + count

Expected: **two stages** (a shuffle boundary in between), non-zero `Shuffle Write` on stage 0 and `Shuffle Read` on stage 1.

Output shape: a small DataFrame with two columns (`PULocationID`, `count`).

```{code-cell} ipython3
(spark.read.parquet("../data/small/")
    .groupBy("PULocationID")
    .count()
    .orderBy("count", ascending=False)
    .show(10))
```

## Reflection

Edit this cell and answer in one or two sentences:

> **Why does the second query create two stages while the first creates one?**

_Your answer here._
