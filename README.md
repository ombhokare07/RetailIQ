TRACK_ID=PS03

# RetailIQ — Multilingual Sales & Inventory Copilot

RetailIQ is a decision-support application for small multi-store retailers. It works over committed sales, inventory, product, and store data and is engineered so deterministic Python logic owns business facts and calculations, while Gemini is reserved for language interpretation and grounded explanation in a later milestone.

## Run

Python 3.11 is required.

```bash
pip install -r requirements.txt
python app.py
```

Open: http://localhost:8000

Interactive API docs: http://localhost:8000/docs

## Environment

```text
GEMINI_API_KEY
```

The current application starts without a Gemini key and makes no network call at startup.

## Current functionality — Phase 2

- Single-command FastAPI entry point on port 8000
- Deterministic synthetic retail dataset for 3 stores, 50 products, and 120 days
- Stockout risk with 7-day demand velocity, days of cover, supplier lead time, and suggested reorder quantity
- Overstock detection using configurable days-of-cover thresholds
- Slow-moving and zero-sales inventory detection
- Sales spike/drop detection against a non-overlapping historical baseline
- Transparent 0-100 inventory health score
- Evidence records, calculation formulas, assumptions, and source row IDs with every material finding
- Explicit `unknown` behaviour when required data/history is missing rather than inventing a recommendation
- Dashboard summary API with attention counts and 30-day sales figures
- Unit/API tests covering the deliberately seeded normal and difficult scenarios

## Key Phase 2 endpoints

```text
GET /health
GET /api/data/summary
GET /api/dashboard/summary
GET /api/dashboard/assumptions
GET /api/inventory/stockout-risk
GET /api/inventory/overstock
GET /api/inventory/slow-movers
GET /api/inventory/health
GET /api/sales/anomalies
```

All analytics endpoints accept optional store/product filters where relevant. Open `/docs` for the live request schema.

## Data generated

Committed sample files live under `data/raw/` and deliberate scenario manifests under `data/demo/`.

The dataset includes explicit cases for critical stockout, near stockout, overstock, slow-moving stock, sales spike, sales drop, zero sales, insufficient history, transfer opportunity, and an incomplete inventory field.

## Architecture principle

**Gemini handles language interpretation and explanation. Python owns facts, calculations, business rules, and decisions.**

RetailIQ never asks an LLM to invent current stock, revenue, demand velocity, days of cover, reorder quantity, anomaly percentages, or inventory health scores.

## Demo video

Add final Devfolio demo video link here before submission.
