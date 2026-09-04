from __future__ import annotations
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd

SEED = 42
END_DATE = pd.Timestamp("2026-09-04")
DAYS = 120

STORES = [
    ("S001", "RetailIQ Pune Central", "Pune"),
    ("S002", "RetailIQ Mumbai West", "Mumbai"),
    ("S003", "RetailIQ Nashik City", "Nashik"),
]

CATALOG = [
    ("Dairy", ["Amul Milk 1L", "Curd 500g", "Paneer 200g", "Butter 100g", "Cheese Slices"]),
    ("Bakery", ["Brown Bread", "White Bread", "Burger Buns", "Rusk", "Tea Cake"]),
    ("Beverages", ["Cola 750ml", "Orange Drink 1L", "Mineral Water 1L", "Mango Drink 1L", "Energy Drink 250ml"]),
    ("Snacks", ["Salted Chips", "Masala Chips", "Namkeen Mix", "Roasted Peanuts", "Popcorn"]),
    ("Personal Care", ["Shampoo 200ml", "Soap 4 Pack", "Toothpaste 150g", "Face Wash 100ml", "Hair Oil 200ml"]),
    ("Home Care", ["Detergent 1kg", "Dishwash Gel", "Floor Cleaner 1L", "Toilet Cleaner", "Fabric Conditioner"]),
    ("Staples", ["Basmati Rice 5kg", "Wheat Flour 5kg", "Sugar 1kg", "Salt 1kg", "Toor Dal 1kg"]),
    ("Breakfast", ["Corn Flakes 500g", "Oats 1kg", "Peanut Butter", "Jam 500g", "Poha 1kg"]),
    ("Frozen", ["Frozen Peas 500g", "French Fries 750g", "Veg Nuggets", "Ice Cream Tub", "Frozen Paratha"]),
    ("Household", ["Tissue Roll Pack", "Garbage Bags", "Aluminium Foil", "Kitchen Towels", "Batteries AA 4 Pack"]),
]
SUPPLIERS = ["Maharashtra Foods", "Metro Wholesale", "FreshLink Distribution", "Prime FMCG", "Western Traders"]


def build_products(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    pid = 1
    for category, names in CATALOG:
        for name in names:
            cost = round(float(rng.uniform(20, 800)), 2)
            margin = float(rng.uniform(1.12, 1.45))
            selling = round(cost * margin, 2)
            rows.append({
                "product_id": f"P{pid:03d}",
                "product_name": name,
                "category": category,
                "cost_price": cost,
                "selling_price": selling,
                "supplier": SUPPLIERS[(pid - 1) % len(SUPPLIERS)],
                "lead_time_days": int(rng.integers(1, 8)),
            })
            pid += 1
    return pd.DataFrame(rows)


def build_stores() -> pd.DataFrame:
    return pd.DataFrame(STORES, columns=["store_id", "store_name", "city"])


def scenario_multiplier(product_id: str, store_id: str, day_idx: int) -> float:
    # Last 7 days are indices DAYS-7 ... DAYS-1.
    recent = day_idx >= DAYS - 7
    if product_id == "P005" and store_id == "S003" and recent:
        return 2.6  # spike
    if product_id == "P006" and store_id == "S001" and recent:
        return 0.25  # drop
    if product_id == "P007" and store_id == "S002":
        return 0.0  # zero sales
    if product_id == "P004" and store_id == "S002":
        return 0.12  # slow mover
    return 1.0


def generate_dataset(output_root: Path) -> dict:
    output_root = Path(output_root)
    raw = output_root / "raw"
    demo = output_root / "demo"
    raw.mkdir(parents=True, exist_ok=True)
    demo.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(SEED)
    products = build_products(rng)
    stores = build_stores()
    dates = pd.date_range(END_DATE - pd.Timedelta(days=DAYS - 1), END_DATE, freq="D")

    base_demand = {p: float(rng.uniform(1.5, 15.0)) for p in products.product_id}
    sales_rows = []
    inventory_rows = []

    # Stable target inventory baselines, then scenario overrides on the final day.
    start_stock = {(s, p): int(rng.integers(80, 420)) for s in stores.store_id for p in products.product_id}
    current = dict(start_stock)

    for day_idx, date in enumerate(dates):
        for store_idx, store_id in enumerate(stores.store_id):
            store_factor = [1.05, 1.25, 0.85][store_idx]
            for _, prod in products.iterrows():
                product_id = prod.product_id

                # New product: only exists for final 5 days at S003.
                if product_id == "P050" and store_id == "S003" and day_idx < DAYS - 5:
                    continue

                weekly = 1.0 + 0.12 * np.sin(day_idx / 7 * 2 * np.pi)
                lam = max(0.0, base_demand[product_id] * store_factor * weekly * scenario_multiplier(product_id, store_id, day_idx))
                units = int(rng.poisson(lam)) if lam > 0 else 0
                revenue = round(units * float(prod.selling_price), 2)
                sales_rows.append({
                    "sale_id": f"SALE-{date:%Y%m%d}-{store_id}-{product_id}",
                    "date": date.date().isoformat(),
                    "store_id": store_id,
                    "product_id": product_id,
                    "units_sold": units,
                    "revenue": revenue,
                })

                # Simplified replenishment simulation for realistic stock trajectories.
                current[(store_id, product_id)] = max(0, current[(store_id, product_id)] - units)
                reorder_level = max(8, int(base_demand[product_id] * 7))
                if current[(store_id, product_id)] <= reorder_level and day_idx < DAYS - 2:
                    current[(store_id, product_id)] += max(50, int(base_demand[product_id] * 28))

                stock_value = current[(store_id, product_id)]
                if day_idx == DAYS - 1:
                    # Explicit final-state judging scenarios.
                    if product_id == "P001" and store_id == "S001": stock_value = 18   # critical
                    if product_id == "P001" and store_id == "S002": stock_value = 420  # transfer source / overstock
                    if product_id == "P002" and store_id == "S003": stock_value = 55   # near stockout
                    if product_id == "P003" and store_id == "S001": stock_value = 850  # overstock
                    if product_id == "P004" and store_id == "S002": stock_value = 600  # slow mover

                inventory_rows.append({
                    "inventory_id": f"INV-{date:%Y%m%d}-{store_id}-{product_id}",
                    "date": date.date().isoformat(),
                    "store_id": store_id,
                    "product_id": product_id,
                    "current_stock": stock_value,
                    # Incomplete edge case: missing threshold, deliberately allowed and documented.
                    "reorder_level": np.nan if (day_idx == DAYS - 1 and product_id == "P049" and store_id == "S001") else reorder_level,
                })

    sales = pd.DataFrame(sales_rows)
    inventory = pd.DataFrame(inventory_rows)

    products.to_csv(raw / "products.csv", index=False)
    stores.to_csv(raw / "stores.csv", index=False)
    sales.to_csv(raw / "sales.csv", index=False)
    inventory.to_csv(raw / "inventory.csv", index=False)

    stockout = pd.DataFrame([
        {"scenario_id": "SC-STOCK-001", "type": "critical_stockout", "store_id": "S001", "product_id": "P001", "description": "Low Pune stock with strong recent sales."},
        {"scenario_id": "SC-STOCK-002", "type": "near_stockout", "store_id": "S003", "product_id": "P002", "description": "Nashik stock is intentionally near its reorder horizon."},
        {"scenario_id": "SC-TRANSFER-001", "type": "transfer_opportunity", "store_id": "S002", "product_id": "P001", "description": "Mumbai has excess P001 while Pune is critically low."},
    ])
    overstock = pd.DataFrame([
        {"scenario_id": "SC-OVER-001", "type": "overstock", "store_id": "S001", "product_id": "P003", "description": "Explicit high final inventory."},
        {"scenario_id": "SC-SLOW-001", "type": "slow_mover", "store_id": "S002", "product_id": "P004", "description": "Low demand with high final inventory."},
    ])
    anomaly = pd.DataFrame([
        {"scenario_id": "SC-ANOM-001", "type": "sales_spike", "store_id": "S003", "product_id": "P005", "description": "Recent 7-day demand multiplier 2.6x."},
        {"scenario_id": "SC-ANOM-002", "type": "sales_drop", "store_id": "S001", "product_id": "P006", "description": "Recent 7-day demand multiplier 0.25x."},
        {"scenario_id": "SC-ZERO-001", "type": "zero_sales", "store_id": "S002", "product_id": "P007", "description": "No sales for full history."},
        {"scenario_id": "SC-NEW-001", "type": "insufficient_history", "store_id": "S003", "product_id": "P050", "description": "Only final 5 days exist."},
        {"scenario_id": "SC-MISSING-001", "type": "incomplete_data", "store_id": "S001", "product_id": "P049", "description": "Latest reorder_level is deliberately missing; system must report uncertainty."},
    ])
    stockout.to_csv(demo / "stockout_scenarios.csv", index=False)
    overstock.to_csv(demo / "overstock_scenarios.csv", index=False)
    anomaly.to_csv(demo / "anomaly_scenarios.csv", index=False)

    manifest = {
        "seed": SEED,
        "end_date": END_DATE.date().isoformat(),
        "history_days": DAYS,
        "products": len(products),
        "stores": len(stores),
        "sales_rows": len(sales),
        "inventory_rows": len(inventory),
    }
    (demo / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = parser.parse_args()
    result = generate_dataset(args.output_root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
