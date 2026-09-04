from __future__ import annotations


def estimate_transfer_cost(
    quantity: int,
    *,
    fixed_cost: float,
    per_unit_cost: float,
) -> float:
    if quantity <= 0:
        return 0.0
    return round(float(fixed_cost) + (int(quantity) * float(per_unit_cost)), 2)
