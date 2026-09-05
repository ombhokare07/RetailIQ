from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict
import pandas as pd


class DataServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class RetailData:
    products: pd.DataFrame
    stores: pd.DataFrame
    sales: pd.DataFrame
    inventory: pd.DataFrame


class DataService:
    REQUIRED = {
        "products": {"product_id", "product_name", "category", "cost_price", "selling_price", "supplier", "lead_time_days"},
        "stores": {"store_id", "store_name", "city"},
        "sales": {"sale_id", "date", "store_id", "product_id", "units_sold", "revenue"},
        "inventory": {"inventory_id", "date", "store_id", "product_id", "current_stock", "reorder_level"},
    }

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)

    def _read(self, name: str) -> pd.DataFrame:
        path = self.data_dir / f"{name}.csv"
        if not path.exists():
            raise DataServiceError(f"Required data file is missing: {path}")
        try:
            frame = pd.read_csv(path, dtype={
                column: str for column in self.REQUIRED[name]
                if column.endswith("_id") or column in {"product_name", "category", "supplier", "store_name", "city"}
            })
        except Exception as exc:
            raise DataServiceError(f"Could not read {path.name}: {exc}") from exc
        missing = self.REQUIRED[name] - set(frame.columns)
        if missing:
            raise DataServiceError(f"{path.name} is missing columns: {sorted(missing)}")
        return frame

    def load_all(self) -> RetailData:
        return RetailData(
            products=self._read("products"),
            stores=self._read("stores"),
            sales=self._read("sales"),
            inventory=self._read("inventory"),
        )

    def summary(self) -> Dict[str, int]:
        data = self.load_all()
        return {
            "products": len(data.products),
            "stores": len(data.stores),
            "sales_rows": len(data.sales),
            "inventory_rows": len(data.inventory),
        }
