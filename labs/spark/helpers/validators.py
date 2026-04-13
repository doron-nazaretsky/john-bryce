"""Property-check validators for the Spark lab exercises.

Each validator prints a short success banner and raises AssertionError on failure.
Property checks (not exact-value checks) so students who make small reasonable
choices about column ordering / naming still pass.
"""

from __future__ import annotations

import os


# ---------- Exercise A: exploratory analytics on parquet ----------

def validate_exercise_a(df) -> None:
    """Validate the exploratory metrics DataFrame produced in Exercise A.

    Expected: a non-empty DataFrame with at least a grouping key column and a
    numeric metric column. Grouping keys must be non-null and metric values
    plausible (non-negative).
    """
    cols = df.columns
    assert len(cols) >= 2, f"Expected >=2 columns, got {cols}"
    n = df.count()
    assert n > 0, "Result is empty"

    # First column should be the grouping key, must be free of nulls.
    key = cols[0]
    nulls = df.filter(df[key].isNull()).count()
    assert nulls == 0, f"Grouping key '{key}' has {nulls} nulls"

    # Look for at least one numeric column with non-negative values.
    numeric_types = {"int", "bigint", "double", "float", "decimal", "long"}
    numeric_cols = [
        f.name for f in df.schema.fields
        if any(t in f.dataType.simpleString().lower() for t in numeric_types)
    ]
    assert numeric_cols, f"No numeric metric columns found in {cols}"
    for c in numeric_cols:
        bad = df.filter(df[c] < 0).count()
        assert bad == 0, f"Column '{c}' has {bad} negative values"

    # Optional: parquet output should exist if students ran the write step.
    out = "data/outputs/exercise_a"
    if os.path.isdir(out):
        partitions = [d for d in os.listdir(out) if not d.startswith("_")]
        assert partitions, f"{out} exists but has no partitions"

    print(f"[validate_exercise_a] OK — {n} rows, columns={cols}")


# ---------- Exercise B: aggregates landed in Postgres ----------

def validate_exercise_b() -> None:
    """Connect to Postgres and assert both target tables have data and basic
    aggregate invariants hold.
    """
    import psycopg2

    conn = psycopg2.connect(
        host=os.environ.get("PG_HOST", "spark-postgres"),
        port=int(os.environ.get("PG_PORT", "5432")),
        user=os.environ.get("PG_USER", "spark"),
        password=os.environ.get("PG_PASSWORD", "spark"),
        dbname=os.environ.get("PG_DB", "taxi"),
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM zone_daily_stats")
            zds = cur.fetchone()[0]
            assert zds > 0, "zone_daily_stats is empty"

            cur.execute("SELECT count(*) FROM hourly_demand")
            hd = cur.fetchone()[0]
            assert hd > 0, "hourly_demand is empty"

            cur.execute("SELECT count(DISTINCT hour) FROM hourly_demand")
            distinct_hours = cur.fetchone()[0]
            assert 1 <= distinct_hours <= 24, (
                f"hourly_demand has {distinct_hours} distinct hours (expected 1..24)"
            )

            cur.execute("SELECT min(trip_count), min(total_revenue) FROM zone_daily_stats")
            min_trips, min_rev = cur.fetchone()
            assert min_trips >= 0, f"trip_count has negative min ({min_trips})"
            assert float(min_rev) >= 0, f"total_revenue has negative min ({min_rev})"

        print(
            f"[validate_exercise_b] OK — zone_daily_stats={zds:,} rows, "
            f"hourly_demand={hd:,} rows"
        )
    finally:
        conn.close()


# ---------- Exercise C: zone profile documents in Mongo ----------

def validate_exercise_c() -> None:
    """Pull a sample doc from taxi.zone_profiles and assert its shape."""
    from pymongo import MongoClient

    uri = os.environ.get("MONGO_URI", "mongodb://spark-mongo:27017")
    client = MongoClient(uri)
    try:
        coll = client["taxi"]["zone_profiles"]
        n = coll.count_documents({})
        assert n > 0, "taxi.zone_profiles is empty"

        doc = coll.find_one()
        for key in ("_id", "zone_name", "borough", "top_destinations",
                    "hourly_demand", "payment_breakdown"):
            assert key in doc, f"Missing key '{key}' in sample doc: {list(doc)}"

        assert isinstance(doc["top_destinations"], list) and doc["top_destinations"], \
            "top_destinations must be a non-empty list"
        assert isinstance(doc["hourly_demand"], list) and len(doc["hourly_demand"]) == 24, \
            f"hourly_demand must have length 24 (got {len(doc['hourly_demand'])})"
        assert isinstance(doc["payment_breakdown"], dict) and doc["payment_breakdown"], \
            "payment_breakdown must be a non-empty dict/document"

        print(f"[validate_exercise_c] OK — {n} zone documents, sample _id={doc['_id']}")
    finally:
        client.close()


# ---------- Exercise D: correctness only (perf discovery is the point) ----------

def validate_exercise_d(df) -> None:
    """Validate the per-(zone, payment_type) result set from Exercise D.
    Checks shape and non-negativity only — performance is the teaching point.
    """
    cols = [c.lower() for c in df.columns]
    needed_any_zone = {"pulocationid", "zone_id"}
    needed_any_pay  = {"payment_type"}
    assert any(c in cols for c in needed_any_zone), (
        f"Expected a pickup-zone column, got {df.columns}"
    )
    assert any(c in cols for c in needed_any_pay), (
        f"Expected a payment_type column, got {df.columns}"
    )

    n = df.count()
    assert n > 0, "Exercise D result is empty"

    # At least one numeric metric, all non-negative.
    numeric_cols = [
        f.name for f in df.schema.fields
        if any(t in f.dataType.simpleString().lower()
               for t in ("int", "bigint", "double", "float", "decimal", "long"))
    ]
    assert numeric_cols, "Expected at least one numeric metric column"
    for c in numeric_cols:
        bad = df.filter(df[c] < 0).count()
        assert bad == 0, f"Column '{c}' has {bad} negative values"

    print(f"[validate_exercise_d] OK — {n} rows, columns={df.columns}")
