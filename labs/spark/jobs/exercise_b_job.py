"""Exercise B as a standalone spark-submit payload.

Used by the instructor demo: same logic as 02-exercise-b.ipynb, but packaged
so it can be submitted to the cluster without a notebook driver:

    docker exec spark-jupyter spark-submit \\
        --master spark://spark-master:7077 \\
        /home/jovyan/work/jobs/exercise_b_job.py

Reads tiered TLC parquet from data/medium/ and writes two aggregates to
Postgres via JDBC.
"""

from __future__ import annotations

import os

from pyspark.sql import SparkSession


def main() -> None:
    pg_url      = os.environ.get("PG_URL", "jdbc:postgresql://spark-postgres:5432/taxi")
    pg_user     = os.environ.get("PG_USER", "spark")
    pg_password = os.environ.get("PG_PASSWORD", "spark")
    data_path   = os.environ.get("TAXI_DATA", "data/medium")

    spark = (SparkSession.builder
        .appName("exercise-b-submit")
        .config("spark.executor.memory", "800m")
        .config("spark.executor.cores", "1")
        .config("spark.driver.memory", "1g")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate())

    trips = spark.read.parquet(data_path)
    trips.createOrReplaceTempView("trips")

    zones = (spark.read
             .option("header", True)
             .option("inferSchema", True)
             .csv("data/zones.csv"))
    zones.createOrReplaceTempView("zones")

    zone_daily = spark.sql("""
        SELECT
            t.PULocationID                                AS zone_id,
            CAST(t.tpep_pickup_datetime AS DATE)          AS stat_date,
            COUNT(*)                                      AS trip_count,
            ROUND(SUM(t.total_amount), 2)                 AS total_revenue,
            ROUND(AVG(CASE WHEN t.fare_amount > 0
                           THEN t.tip_amount / t.fare_amount * 100
                      END), 3)                            AS avg_tip_pct
        FROM trips t
        WHERE t.tpep_pickup_datetime IS NOT NULL
          AND t.PULocationID IS NOT NULL
        GROUP BY t.PULocationID, CAST(t.tpep_pickup_datetime AS DATE)
    """)

    hourly = spark.sql("""
        SELECT
            t.PULocationID                                AS zone_id,
            HOUR(t.tpep_pickup_datetime)                  AS hour,
            COUNT(*)                                      AS trips
        FROM trips t
        WHERE t.tpep_pickup_datetime IS NOT NULL
          AND t.PULocationID IS NOT NULL
        GROUP BY t.PULocationID, HOUR(t.tpep_pickup_datetime)
    """)

    common_jdbc_opts = {
        "url": pg_url,
        "user": pg_user,
        "password": pg_password,
        "driver": "org.postgresql.Driver",
        "batchsize": "5000",
        "numPartitions": "4",
    }

    (zone_daily.repartition(4)
        .write.format("jdbc")
        .options(dbtable="zone_daily_stats", **common_jdbc_opts)
        .mode("overwrite")
        .save())

    (hourly.repartition(4)
        .write.format("jdbc")
        .options(dbtable="hourly_demand", **common_jdbc_opts)
        .mode("overwrite")
        .save())

    print("exercise_b_job: wrote zone_daily_stats and hourly_demand to Postgres")
    spark.stop()


if __name__ == "__main__":
    main()
