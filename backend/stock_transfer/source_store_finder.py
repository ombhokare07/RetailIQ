from __future__ import annotations

from backend.stock_transfer.transfer_validator import donor_surplus_units


def find_source_stores(
    stockout_items: list[dict],
    *,
    recipient_store_id: str,
    product_id: str,
    donor_min_days_cover: float,
    minimum_transfer_units: int,
) -> list[dict]:
    candidates: list[dict] = []
    for item in stockout_items:
        if item.get("product_id") != product_id:
            continue
        if item.get("store_id") == recipient_store_id:
            continue
        if item.get("risk") in {"critical", "high", "unknown"}:
            continue

        surplus, reserve = donor_surplus_units(
            current_stock=int(item.get("current_stock") or 0),
            avg_daily_sales=item.get("avg_daily_sales"),
            donor_min_days_cover=donor_min_days_cover,
        )
        if surplus < int(minimum_transfer_units):
            continue

        candidates.append(
            {
                **item,
                "donor_surplus_units": surplus,
                "donor_reserve_units": reserve,
                "donor_min_days_cover": float(donor_min_days_cover),
            }
        )

    return sorted(
        candidates,
        key=lambda x: (
            -int(x["donor_surplus_units"]),
            -(float(x.get("days_cover") or 0)),
            str(x.get("store_id")),
        ),
    )
