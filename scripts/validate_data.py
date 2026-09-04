from __future__ import annotations
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

REQUIRED = {
    "products": ["product_id", "product_name", "category", "cost_price", "selling_price", "supplier", "lead_time_days"],
    "stores": ["store_id", "store_name", "city"],
    "sales": ["sale_id", "date", "store_id", "product_id", "units_sold", "revenue"],
    "inventory": ["inventory_id", "date", "store_id", "product_id", "current_stock", "reorder_level"],
}


def validate(raw_dir: Path = RAW):
    errors = []
    warnings = []
    frames = {}
    for name, cols in REQUIRED.items():
        path = Path(raw_dir) / f"{name}.csv"
        if not path.exists():
            errors.append(f"Missing file: {path}")
            continue
        df = pd.read_csv(path)
        frames[name] = df
        missing = [c for c in cols if c not in df.columns]
        if missing:
            errors.append(f"{path.name}: missing columns {missing}")

    if errors:
        return errors, warnings

    p, s, sales, inv = frames["products"], frames["stores"], frames["sales"], frames["inventory"]
    for col, df, label in [("product_id", p, "products"), ("store_id", s, "stores"), ("sale_id", sales, "sales"), ("inventory_id", inv, "inventory")]:
        if df[col].duplicated().any():
            errors.append(f"{label}: duplicate values in {col}")

    known_products = set(p.product_id)
    known_stores = set(s.store_id)
    if not set(sales.product_id).issubset(known_products): errors.append("sales: unknown product_id values")
    if not set(sales.store_id).issubset(known_stores): errors.append("sales: unknown store_id values")
    if not set(inv.product_id).issubset(known_products): errors.append("inventory: unknown product_id values")
    if not set(inv.store_id).issubset(known_stores): errors.append("inventory: unknown store_id values")

    if (sales.units_sold < 0).any(): errors.append("sales: negative units_sold found")
    if (sales.revenue < 0).any(): errors.append("sales: negative revenue found")
    if (inv.current_stock < 0).any(): errors.append("inventory: negative current_stock found")
    if (p.cost_price <= 0).any() or (p.selling_price <= 0).any(): errors.append("products: prices must be positive")
    if (p.selling_price < p.cost_price).any(): warnings.append("products: selling price below cost exists")

    price_map = p.set_index("product_id").selling_price
    expected = sales.product_id.map(price_map) * sales.units_sold
    mismatch = (sales.revenue - expected).abs() > 0.011
    if mismatch.any(): errors.append(f"sales: {int(mismatch.sum())} revenue rows are inconsistent")

    for name, df in [("sales", sales), ("inventory", inv)]:
        parsed = pd.to_datetime(df.date, errors="coerce")
        if parsed.isna().any(): errors.append(f"{name}: invalid date values found")

    missing_reorder = int(inv.reorder_level.isna().sum())
    if missing_reorder:
        warnings.append(f"inventory: {missing_reorder} reorder_level value(s) missing; this is a seeded incomplete-data scenario")

    return errors, warnings


def main():
    errors, warnings = validate()
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        sys.exit(1)
    print("VALIDATION PASSED")


if __name__ == "__main__":
    main()
