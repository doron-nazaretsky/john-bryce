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

# Exercise D — Per-zone payment-type stats

**Task:** For the **large** data tier (12 months, ~85 M rows), compute for every `(PULocationID, payment_type)` pair:

- `trip_count`
- `avg_fare` (mean of `fare_amount`)

Write SparkSQL. Show the top 20 rows by `trip_count`.

**While the job runs, open the Driver UI (<http://localhost:4040>):**

- Click into the running stage. Look at the **Summary Metrics** section — Min, 25th, Median, 75th, Max **task duration**.
- How long did the slowest task take versus the median?
- Why might that be? What in the data could cause it?

Validate by calling `validate_exercise_d(df)` — checks correctness only.

```{code-cell}
import sys
sys.path.insert(0, "..")
from helpers import validate_exercise_d

from pyspark.sql import SparkSession

spark = (SparkSession.builder
    .appName("exercise-d")
    .getOrCreate())

spark.read.parquet("../data/large/").createOrReplaceTempView("trips")
print("Driver UI:", spark.sparkContext.uiWebUrl)
```

```{code-cell}
# Your SparkSQL here.
result = spark.sql("""
    -- TODO
""")
result.orderBy("trip_count", ascending=False).show(20)
```

```{code-cell}
validate_exercise_d(result)
```

## Reflection

Write your observations about task durations from the Spark UI here.

_Your notes:_
