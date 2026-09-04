from __future__ import annotations


def roi_percent(*, benefit: float, cost: float) -> float | None:
    if cost <= 0:
        return None
    return round(((float(benefit) - float(cost)) / float(cost)) * 100.0, 2)
