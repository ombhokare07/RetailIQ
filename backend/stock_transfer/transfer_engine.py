from __future__ import annotations

from backend.stock_transfer.source_store_finder import find_source_stores
from backend.stock_transfer.transfer_cost import estimate_transfer_cost
from backend.stock_transfer.transfer_optimizer import optimize_transfer_quantity


def calculate_transfer_recommendations(
    context,
    stockout_items: list[dict],
    *,
    donor_min_days_cover: float,
    minimum_transfer_units: int,
    fixed_transfer_cost: float,
    per_unit_transfer_cost: float,
) -> list[dict]:
    """Build safe cross-store transfer recommendations from deterministic metrics."""
    product_lookup = {
        str(row.product_id): row for row in context.products.itertuples(index=False)
    }
    recommendations: list[dict] = []

    for recipient in stockout_items:
        if recipient.get("risk") not in {"critical", "high"}:
            continue
        reorder_qty = recipient.get("recommended_reorder_qty")
        avg_daily_sales = recipient.get("avg_daily_sales")
        if reorder_qty is None or reorder_qty <= 0 or not avg_daily_sales:
            continue
        if recipient.get("unknown_fields"):
            continue

        donors = find_source_stores(
            stockout_items,
            recipient_store_id=str(recipient["store_id"]),
            product_id=str(recipient["product_id"]),
            donor_min_days_cover=donor_min_days_cover,
            minimum_transfer_units=minimum_transfer_units,
        )
        if not donors:
            continue

        product = product_lookup.get(str(recipient["product_id"]))
        cost_price = float(getattr(product, "cost_price", 0.0) or 0.0)
        selling_price = float(getattr(product, "selling_price", 0.0) or 0.0)

        donor_options: list[dict] = []
        for donor in donors:
            optimization = optimize_transfer_quantity(
                recipient_current_stock=int(recipient["current_stock"]),
                recipient_avg_daily_sales=float(avg_daily_sales),
                recipient_reorder_qty=int(reorder_qty),
                donor_current_stock=int(donor["current_stock"]),
                donor_avg_daily_sales=float(donor.get("avg_daily_sales") or 0),
                donor_surplus_units=int(donor["donor_surplus_units"]),
                donor_reserve_units=int(donor["donor_reserve_units"]),
            )
            quantity = int(optimization["transfer_quantity"])
            if quantity < int(minimum_transfer_units):
                continue

            transfer_cost = estimate_transfer_cost(
                quantity,
                fixed_cost=fixed_transfer_cost,
                per_unit_cost=per_unit_transfer_cost,
            )
            donor_options.append(
                {
                    "source_store_id": donor["store_id"],
                    "source_store_name": donor["store_name"],
                    "source_city": donor.get("city"),
                    "source_stock": donor["current_stock"],
                    "source_avg_daily_sales": donor.get("avg_daily_sales"),
                    "source_days_cover": donor.get("days_cover"),
                    "source_surplus_units": donor["donor_surplus_units"],
                    **optimization,
                    "estimated_transfer_cost": transfer_cost,
                    "near_term_purchase_deferred": round(quantity * cost_price, 2),
                    "inventory_retail_value_moved": round(quantity * selling_price, 2),
                    "evidence": {
                        "recipient": recipient.get("evidence"),
                        "donor": donor.get("evidence"),
                    },
                }
            )

        if not donor_options:
            continue

        donor_options = sorted(
            donor_options,
            key=lambda x: (
                -int(x["fully_covers_reorder_need"]),
                int(x["remaining_reorder_need"]),
                float(x["estimated_transfer_cost"]),
                -int(x["source_surplus_units"]),
            ),
        )
        best = donor_options[0]

        recommendations.append(
            {
                "recommendation_id": f"TR-{recipient['store_id']}-{recipient['product_id']}",
                "action": "transfer",
                "recipient_store_id": recipient["store_id"],
                "recipient_store_name": recipient["store_name"],
                "recipient_city": recipient.get("city"),
                "product_id": recipient["product_id"],
                "product_name": recipient["product_name"],
                "category": recipient.get("category"),
                "recipient_risk": recipient["risk"],
                "recipient_current_stock": recipient["current_stock"],
                "recipient_avg_daily_sales": recipient["avg_daily_sales"],
                "recipient_days_cover": recipient["days_cover"],
                "supplier_lead_time_days": recipient.get("lead_time_days"),
                "recipient_reorder_need": recipient["recommended_reorder_qty"],
                "recommended_source_store_id": best["source_store_id"],
                "recommended_source_store_name": best["source_store_name"],
                "recommended_transfer_quantity": best["transfer_quantity"],
                "recipient_after_days_cover": best["recipient_after_days_cover"],
                "donor_after_days_cover": best["donor_after_days_cover"],
                "estimated_transfer_cost": best["estimated_transfer_cost"],
                "near_term_purchase_deferred": best["near_term_purchase_deferred"],
                "reason": (
                    "Recipient is at stockout risk while another store has inventory above "
                    "the configured donor safety reserve. RetailIQ recommends rebalancing "
                    "before placing an emergency purchase."
                ),
                "assumptions": [
                    f"Donor retains at least {donor_min_days_cover:g} days of forecast demand after transfer.",
                    "Recent demand velocity continues during the comparison horizon.",
                    "Transfer costs are configured estimates, not live carrier quotes.",
                ],
                "alternative_sources": donor_options,
                "evidence": best["evidence"],
            }
        )

    risk_rank = {"critical": 0, "high": 1}
    return sorted(
        recommendations,
        key=lambda x: (
            risk_rank.get(x["recipient_risk"], 9),
            x["recipient_days_cover"] if x["recipient_days_cover"] is not None else 9999,
            x["recipient_store_id"],
            x["product_id"],
        ),
    )
