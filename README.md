TRACK_ID=PS03

# RetailIQ — Multilingual Sales & Inventory Copilot

RetailIQ is a decision-support application for small multi-store retailers. It works over committed sales, inventory, product, and store data. Deterministic Python logic owns business facts, calculations, recommendations, and financial estimates; Gemini is reserved for language interpretation and grounded explanation in a later milestone.

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

The application starts without a Gemini key and makes no network call at startup.

## Current functionality — Phase 3

Phase 3 keeps all Phase 2 analytics and adds two flagship innovations:

- **Cross-Store Smart Transfer** — finds stockout-risk stores, identifies safe donor stores holding the same product, protects donor safety stock, calculates a transfer quantity, and compares before/after days of cover.
- **Financial Impact Intelligence** — estimates revenue/gross-margin exposure from likely stockouts, capital tied up in excess stock, transfer cost, near-term purchase deferred, and the estimated benefit of transfer recommendations.
- Every recommendation includes formulas, assumptions, and source evidence.
- Transfer recommendations never reduce a donor below the configured 21-day demand reserve.
- Missing or insufficient data is exposed rather than guessed.
- Financial figures are labelled as scenario estimates and never represented as live supplier/carrier quotes.

## Key endpoints

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
GET /api/products/{product_id}/performance
GET /api/stores/{store_id}/performance
GET /api/transfers/recommendations
GET /api/financial/summary
GET /api/financial/revenue-risk
GET /api/financial/overstock-capital
GET /api/financial/transfer-benefits
```

## Data generated

Committed sample files live under `data/raw/` and deliberate scenario manifests under `data/demo/`.

The dataset includes explicit cases for critical stockout, near stockout, overstock, slow-moving stock, sales spike, sales drop, zero sales, insufficient history, cross-store transfer opportunity, and an incomplete inventory field.

## Architecture principle

**Gemini handles language interpretation and explanation. Python owns facts, calculations, business rules, and decisions.**

RetailIQ never asks an LLM to invent stock, revenue, demand velocity, days of cover, reorder quantities, transfer quantities, or financial impact.

## Demo video

Add final Devfolio demo video link here before submission.
