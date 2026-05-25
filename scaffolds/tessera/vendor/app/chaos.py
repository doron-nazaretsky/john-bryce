"""Late-correction chaos for the tlc-publisher.

Single behaviour: with probability LATE_CORRECTION_RATE (rolled on each new
month-boundary publish), re-PUT a previously-published month's parquet with
a small deterministic mutation. A handful of rows have their
`base_passenger_fare` nudged by a seeded RNG, the parquet is genuinely
rewritten, and the resulting object has a new ETag.

The mutation is real — no faking. Students reading via boto3 or pyspark
will see different bytes and a new ETag, exactly as if a real provider
re-published a corrected file.
"""
from __future__ import annotations

import io
import os
import random
import tempfile
from pathlib import Path
from typing import Any, Callable

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


LATE_CORRECTION_RATE = float(os.environ.get("VENDOR_LATE_CORRECTION_RATE", "0"))


def _log(msg: str) -> None:
    print(f"[chaos] {msg}", flush=True)


def apply_late_correction(
    *,
    s3,
    bucket: str,
    cache_dir: Path,
    published_months: list[str],
    rng: random.Random,
    put_month_file: Callable,
) -> dict[str, Any] | None:
    """Mutate a previously-published month's parquet and re-PUT it.

    Returns a dict describing the mutation, or None if no eligible file was
    found.
    """
    if not published_months:
        return None
    ym = rng.choice(published_months)
    src = cache_dir / f"fhvhv_tripdata_{ym}.parquet"
    if not src.exists():
        _log(f"cannot mutate {ym}: {src} missing")
        return None

    _log(f"applying late correction to {ym}")

    try:
        table = pq.read_table(src)
    except Exception as e:
        _log(f"read failed for {ym}: {e}")
        return None

    n_rows = table.num_rows
    if n_rows == 0:
        return None

    # Pick ~50 deterministic row indices to mutate.
    n_mutate = min(50, n_rows)
    indices = sorted(rng.sample(range(n_rows), n_mutate))

    if "base_passenger_fare" not in table.column_names:
        _log(f"{ym}: no base_passenger_fare column; skipping")
        return None

    col = table.column("base_passenger_fare")
    py_values = col.to_pylist()
    nudges: list[tuple[int, float, float]] = []
    for idx in indices:
        old = py_values[idx]
        if old is None:
            continue
        # Deterministic small nudge: +/- $0.50 .. $2.50.
        delta = round(rng.uniform(-2.5, 2.5), 2)
        if delta == 0.0:
            delta = 0.25
        new_val = float(old) + delta
        py_values[idx] = new_val
        nudges.append((idx, float(old), new_val))

    if not nudges:
        return None

    # Replace the column.
    new_col = pa.array(py_values, type=col.type)
    new_table = table.set_column(
        table.column_names.index("base_passenger_fare"), "base_passenger_fare", new_col
    )

    # Write to a tmp file, then upload.
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False, dir=str(cache_dir)) as tmp:
        tmp_path = Path(tmp.name)
    try:
        pq.write_table(new_table, tmp_path, compression="snappy")
        # Atomically replace the cached copy so subsequent corrections build
        # on the corrected file (and any restart picks up the mutated bytes).
        tmp_path.replace(src)
    except Exception as e:
        _log(f"write/replace failed: {e}")
        tmp_path.unlink(missing_ok=True)
        return None

    new_etag = put_month_file(s3, ym)

    _log(
        f"{ym} corrected: {len(nudges)} rows nudged on base_passenger_fare; "
        f"new etag {new_etag}"
    )
    return {
        "month": ym,
        "rows_mutated": len(nudges),
        "new_etag": new_etag,
        "sample": nudges[:5],
    }
