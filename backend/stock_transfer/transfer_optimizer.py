from __future__ import annotations

import math


def optimize_transfer_quantity(
    *,
    recipient_current_stock: int,
    recipient_avg_daily_sales: float,
    recipient_reorder_qty: int,
    donor_current_stock: int,
    donor_avg_daily_sales: float,
    donor_surplus_units: int,
    donor_reserve_units: int,
) -> dict:
    quantity = max(0, min(int(recipient_reorder_qty), int(donor_surplus_units)))

    recipient_before_cover = (
        float(recipient_current_stock) / float(recipient_avg_daily_sales)
        if recipient_avg_daily_sales > 0
        else None
    )
    recipient_after_cover = (
        (float(recipient_current_stock) + quantity) / float(recipient_avg_daily_sales)
        if recipient_avg_daily_sales > 0
        else None
    )
    donor_after_stock = int(donor_current_stock) - quantity
    donor_after_cover = (
        float(donor_after_stock) / float(donor_avg_daily_sales)
        if donor_avg_daily_sales > 0
        else None
    )

    return {
        "transfer_quantity": quantity,
        "recipient_before_days_cover": round(recipient_before_cover, 4)
        if recipient_before_cover is not None
        else None,
        "recipient_after_days_cover": round(recipient_after_cover, 4)
        if recipient_after_cover is not None
        else None,
        "donor_before_stock": int(donor_current_stock),
        "donor_after_stock": donor_after_stock,
        "donor_reserve_units": int(donor_reserve_units),
        "donor_after_days_cover": round(donor_after_cover, 4)
        if donor_after_cover is not None
        else None,
        "fully_covers_reorder_need": quantity >= int(recipient_reorder_qty),
        "remaining_reorder_need": max(0, int(recipient_reorder_qty) - quantity),
        "calculation": {
            "quantity_formula": "min(recipient_reorder_qty, donor_surplus_units)",
            "recipient_after_cover_formula": "(recipient_current_stock + transfer_quantity) / recipient_avg_daily_sales",
            "donor_after_cover_formula": "(donor_current_stock - transfer_quantity) / donor_avg_daily_sales",
        },
    }
