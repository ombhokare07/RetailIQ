from __future__ import annotations

import math


def donor_surplus_units(
    *,
    current_stock: int,
    avg_daily_sales: float | None,
    donor_min_days_cover: float,
) -> tuple[int, int]:
    """Return (surplus_units, reserve_units) for a potential donor store.

    Donor inventory is never reduced below the configured minimum days of cover.
    If demand is unknown, the donor is considered unsafe for deterministic transfer.
    """
    if avg_daily_sales is None or avg_daily_sales < 0:
        return 0, 0
    reserve_units = math.ceil(float(avg_daily_sales) * float(donor_min_days_cover))
    surplus = max(0, int(current_stock) - reserve_units)
    return surplus, reserve_units


def is_transfer_candidate(
    *,
    recipient_risk: str,
    recipient_reorder_qty: int | None,
    donor_risk: str,
    donor_surplus: int,
    minimum_transfer_units: int,
) -> bool:
    if recipient_risk not in {"critical", "high"}:
        return False
    if recipient_reorder_qty is None or recipient_reorder_qty <= 0:
        return False
    if donor_risk in {"critical", "high", "unknown"}:
        return False
    return donor_surplus >= int(minimum_transfer_units)
