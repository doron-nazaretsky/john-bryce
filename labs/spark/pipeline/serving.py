"""Student stubs — the two query functions that back the consumer contracts.

    total_revenue(d, h) -> float     # analyst query, budget ≤ 1s
    avg_revenue(h)      -> float     # backend query, budget ≤ a few ms (median)

These are *not* passed the `connections` dict directly. The implementation picks
connections up from the same `pipeline.config` the ETL job uses, so callers stay
tiny. The tests do likewise — they set the relevant env vars via fixtures and
call these functions as a black box.

`d` is an ISO-8601 date string (YYYY-MM-DD). `h` is an integer 0..23.
"""
from __future__ import annotations


def total_revenue(d: str, h: int) -> float:
    raise NotImplementedError("stage 3 — implement total_revenue")


def avg_revenue(h: int) -> float:
    raise NotImplementedError("stage 4 — implement avg_revenue")
