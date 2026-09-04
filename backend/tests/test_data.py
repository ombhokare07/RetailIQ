from pathlib import Path
import hashlib
import pandas as pd
from scripts.generate_demo_data import generate_dataset
from scripts.validate_data import validate


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_generation_schema_and_counts(tmp_path):
    data_root = tmp_path / "data"
    manifest = generate_dataset(data_root)
    assert manifest["products"] == 50
    assert manifest["stores"] == 3
    assert manifest["sales_rows"] > 17000
    assert manifest["inventory_rows"] > 17000
    products = pd.read_csv(data_root / "raw" / "products.csv")
    sales = pd.read_csv(data_root / "raw" / "sales.csv")
    assert {"product_id", "selling_price", "lead_time_days"}.issubset(products.columns)
    assert {"sale_id", "units_sold", "revenue"}.issubset(sales.columns)


def test_generation_is_deterministic(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    generate_dataset(a)
    generate_dataset(b)
    for name in ["products.csv", "stores.csv", "sales.csv", "inventory.csv"]:
        assert digest(a / "raw" / name) == digest(b / "raw" / name)


def test_validation_accepts_seeded_missing_edge_case(tmp_path):
    root = tmp_path / "data"
    generate_dataset(root)
    errors, warnings = validate(root / "raw")
    assert errors == []
    assert any("reorder_level" in w for w in warnings)
