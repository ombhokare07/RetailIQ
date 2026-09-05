"""Validated local CSV snapshots; restart always selects the committed demo."""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from threading import RLock
from uuid import uuid4

import numpy as np
import pandas as pd

from backend.core.config import ROOT_DIR
from backend.services.data_service import DataService

MAX_FILE_BYTES = 12 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_ROWS = 100_000
MAX_CATALOG_ROWS = 500
DEMO_DIR = ROOT_DIR / "data" / "raw"


class DatasetWorkspace:
    def __init__(self, runtime_dir: Path | None = None):
        self.runtime_dir = runtime_dir or ROOT_DIR / "data" / "runtime" / "datasets"
        self._active_path = DEMO_DIR
        self._active_id = "demo"
        self._validated: dict[str, dict] = {}
        self._lock = RLock()

    @property
    def active_path(self) -> Path:
        with self._lock:
            return self._active_path

    def describe(self) -> dict:
        with self._lock:
            path, identifier = self._active_path, self._active_id
        service = DataService(path)
        data = service.load_all()
        return {
            "status": "ok",
            "active_dataset": {"id": identifier, "kind": "demo" if identifier == "demo" else "custom",
                               "name": "Committed demo dataset" if identifier == "demo" else "Local custom dataset"},
            "summary": service.summary(),
            "catalogs": {
                "stores": data.stores[["store_id", "store_name", "city"]].to_dict("records"),
                "products": data.products[["product_id", "product_name", "category"]].to_dict("records"),
            },
            "required_columns": {name: sorted(cols) for name, cols in DataService.REQUIRED.items()},
            "limits": {"max_file_bytes": MAX_FILE_BYTES, "max_total_bytes": MAX_TOTAL_BYTES,
                       "max_rows": MAX_ROWS, "max_catalog_rows": MAX_CATALOG_ROWS},
            "restart_policy": "Application restart returns to the committed demo dataset.",
        }

    def validate(self, files: dict[str, str]) -> dict:
        errors, warnings, frames, preview = [], [], {}, {}
        expected = {f"{name}.csv" for name in DataService.REQUIRED}
        if set(files) != expected:
            errors.append("Provide exactly stores.csv, products.csv, sales.csv and inventory.csv.")
        if sum(len(value.encode("utf-8")) for value in files.values()) > MAX_TOTAL_BYTES:
            errors.append("The combined CSV upload exceeds the 32 MiB limit.")
        if errors:
            return self._report(errors, warnings, frames, preview)
        for name, required in DataService.REQUIRED.items():
            value = files[f"{name}.csv"].lstrip("\ufeff")
            if len(value.encode("utf-8")) > MAX_FILE_BYTES:
                errors.append(f"{name}.csv exceeds the 12 MiB file limit.")
                continue
            if "\x00" in value:
                errors.append(f"{name}.csv contains invalid binary content.")
                continue
            try:
                reader = csv.reader(io.StringIO(value), strict=True)
                header = next(reader)
                if len(header) != len(set(header)):
                    raise ValueError("duplicate column names")
                if not required.issubset(header):
                    errors.append(f"{name}.csv is missing columns: {', '.join(sorted(required - set(header)))}.")
                    continue
                if set(header) != required:
                    errors.append(f"{name}.csv contains unsupported columns: {', '.join(sorted(set(header) - required))}.")
                    continue
                if any(len(row) != len(header) for row in reader):
                    raise ValueError("inconsistent number of columns")
                frame = pd.read_csv(io.StringIO(value), dtype=str, keep_default_na=False, nrows=MAX_ROWS + 1)
            except (ValueError, csv.Error, StopIteration, pd.errors.ParserError, pd.errors.EmptyDataError):
                errors.append(f"{name}.csv could not be parsed as a rectangular UTF-8 CSV table.")
                continue
            if frame.empty or len(frame) > MAX_ROWS:
                errors.append(f"{name}.csv must contain 1 to {MAX_ROWS} data rows.")
            if name in {"stores", "products"} and len(frame) > MAX_CATALOG_ROWS:
                errors.append(f"{name}.csv supports at most {MAX_CATALOG_ROWS} catalog rows.")
            for col in frame:
                frame[col] = frame[col].str.strip()
                if col != "reorder_level" and frame[col].eq("").any():
                    errors.append(f"{name}.{col}: missing critical values.")
                if frame[col].str.len().gt(250).any():
                    errors.append(f"{name}.{col}: values must be at most 250 characters.")
            identifier = {"products": "product_id", "stores": "store_id", "sales": "sale_id", "inventory": "inventory_id"}[name]
            if frame[identifier].duplicated().any():
                errors.append(f"{name}.{identifier}: duplicate IDs.")
            for col in [c for c in frame if c.endswith("_id")]:
                if not frame[col].str.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}").all():
                    errors.append(f"{name}.{col}: IDs must use letters, numbers, dot, dash or underscore.")
            numeric = {"products": ["cost_price", "selling_price", "lead_time_days"], "stores": [],
                       "sales": ["units_sold", "revenue"], "inventory": ["current_stock", "reorder_level"]}[name]
            for col in numeric:
                blank = frame[col].eq("")
                values = pd.to_numeric(frame[col], errors="coerce")
                invalid = (~np.isfinite(values)) & ~(blank if col == "reorder_level" else pd.Series(False, index=frame.index))
                if invalid.any():
                    errors.append(f"{name}.{col}: numeric finite values are required.")
                if values.lt(0).any():
                    errors.append(f"{name}.{col}: negative values are not allowed.")
                if col in {"cost_price", "selling_price", "lead_time_days"} and values.le(0).any():
                    errors.append(f"{name}.{col}: values must be positive.")
                if col in {"units_sold", "current_stock", "reorder_level", "lead_time_days"} and values.dropna().mod(1).ne(0).any():
                    errors.append(f"{name}.{col}: whole units/days are required.")
                maximum = 365 if col == "lead_time_days" else 1_000_000_000
                if values.gt(maximum).any():
                    errors.append(f"{name}.{col}: exceeds the supported maximum of {maximum}.")
                if col == "reorder_level" and blank.any():
                    warnings.append(f"inventory.reorder_level: {int(blank.sum())} missing values; affected recommendations will be withheld.")
                frame[col] = values
            if "date" in frame:
                dates = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="coerce")
                if dates.isna().any() or not frame["date"].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
                    errors.append(f"{name}.date: valid YYYY-MM-DD dates are required.")
                if frame.duplicated(["date", "store_id", "product_id"]).any():
                    errors.append(f"{name}: duplicate date/store/product relationships; provide one daily row per pair.")
            frames[name] = frame
            preview[name] = {"columns": list(frame.columns), "rows": json.loads(frame.head(5).to_json(orient="records"))}
        if len(frames) == 4 and not errors:
            products, stores = frames["products"], frames["stores"]
            for name in ("sales", "inventory"):
                for column, catalog in (("product_id", products), ("store_id", stores)):
                    if not frames[name][column].isin(catalog[column]).all():
                        errors.append(f"{name}.{column}: unknown catalog IDs.")
            inventory_pairs = set(zip(frames["inventory"].store_id, frames["inventory"].product_id))
            sales_pairs = set(zip(frames["sales"].store_id, frames["sales"].product_id))
            if not sales_pairs.issubset(inventory_pairs):
                errors.append("sales: every store/product pair needs inventory history.")
            if len(inventory_pairs) > 500:
                errors.append("inventory: at most 500 store/product positions are supported per local dataset.")
            if products.selling_price.lt(products.cost_price).any():
                warnings.append("Some product selling prices are below cost price.")
            if not errors:
                prices = products.set_index("product_id").selling_price
                expected_revenue = frames["sales"].product_id.map(prices) * frames["sales"].units_sold
                if frames["sales"].revenue.sub(expected_revenue).abs().gt(0.011).any():
                    errors.append("sales.revenue: inconsistent with units_sold × product selling_price.")
            warnings.append("Recent demand assumes missing sales days represent zero sales; incomplete inventory history withholds affected recommendations.")
        report = self._report(errors, warnings, frames, preview)
        if not errors:
            identifier = uuid4().hex
            directory = self.runtime_dir / identifier
            directory.mkdir(parents=True, exist_ok=False)
            for name, frame in frames.items():
                frame.to_csv(directory / f"{name}.csv", index=False, encoding="utf-8")
            with self._lock:
                self._validated[identifier] = {"path": directory, "report": report}
            report["dataset_id"] = identifier
        return report

    @staticmethod
    def _report(errors, warnings, frames, preview):
        return {"status": "invalid" if errors else "valid", "valid": not errors, "dataset_id": None,
                "errors": list(dict.fromkeys(errors)), "warnings": list(dict.fromkeys(warnings)),
                "summary": {"products": len(frames.get("products", [])), "stores": len(frames.get("stores", [])),
                            "sales_rows": len(frames.get("sales", [])), "inventory_rows": len(frames.get("inventory", []))},
                "preview": preview}

    def activate(self, identifier: str) -> dict:
        with self._lock:
            if not re.fullmatch(r"[a-f0-9]{32}", identifier) or identifier not in self._validated:
                raise ValueError("Validate these four CSV files successfully in this session before activation.")
            self._active_path = self._validated[identifier]["path"]
            self._active_id = identifier
        return self.describe()

    def reset(self) -> dict:
        with self._lock:
            self._active_path, self._active_id = DEMO_DIR, "demo"
        return self.describe()


workspace = DatasetWorkspace()
