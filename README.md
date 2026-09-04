TRACK_ID=PS03

# RetailIQ — Multilingual Sales & Inventory Copilot

RetailIQ is a decision-support application for small multi-store retailers. It works over committed sales, inventory, product, and store data and is designed so that deterministic Python/DuckDB logic owns business facts and calculations, while Gemini is reserved for language interpretation and grounded explanation in later milestones.

## Run

Python 3.11 is required.

```bash
pip install -r requirements.txt
python app.py
```

Open: http://localhost:8000

## Environment

```text
GEMINI_API_KEY
```

The Phase 1 application starts without a Gemini key and makes no network call at startup.

## Phase 1 functionality

- Single-command FastAPI entry point on port 8000
- Health endpoints
- Deterministic synthetic retail dataset for 3 stores, 50 products, and 120 days
- Explicit seeded normal, stockout, overstock, slow-moving, spike, drop, zero-sales, new-product, transfer-opportunity, and incomplete-data cases
- CSV validation and a reusable data service
- Tests for startup, schemas, deterministic generation, and validation

## Data generated

Committed sample files live under `data/raw/` and scenario manifests under `data/demo/`.

## Architecture principle

**Gemini handles language and explanation. Python/DuckDB owns facts, calculations, business rules, and decisions.**

## Demo video

Add final Devfolio demo video link here before submission.
