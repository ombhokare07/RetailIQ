TRACK_ID=PS03

# RetailIQ — Multilingual Sales & Inventory Copilot

RetailIQ is a decision-support application for small multi-store retailers. It works over committed sales, inventory, product, and store data. Deterministic Python logic owns business facts, calculations, recommendations, simulations, and financial estimates; Gemini is reserved for language interpretation and grounded explanation in a later milestone.

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

## Current functionality — Phase 4

Phase 4 keeps all prior deterministic analytics, smart-transfer, and financial-impact features and adds the **Retail Decision Twin**:

- Simulates **No Action**, **Supplier Reorder**, and **Smart Inter-Store Transfer** for a store/product pair.
- Compares expected demand served, unserved units, stockout timing, ending inventory, service level, execution cost, cash committed, and estimated operating loss.
- Uses product lead time for supplier reorders and a configurable internal-transfer arrival assumption.
- Supports demand-shock what-if questions through a configurable multiplier such as 1.5× demand.
- Ranks scenarios deterministically: service protection first, then operating loss/cost/cash trade-offs.
- Labels demand shocks as assumptions, not forecasts.
- Refuses to simulate the deliberately incomplete seeded case instead of guessing missing fields.
- Keeps a human manager in control: RetailIQ recommends but never executes a purchase or transfer.

## Flagship innovations implemented so far

1. Cross-Store Smart Stock Transfer
2. Financial Impact Intelligence
3. Retail Decision Twin / What-If Simulator

Explainable AI and multilingual Gemini interaction are planned for the next milestone.

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
GET /api/simulation/compare
GET /api/simulation/demand-shock
```

### Example Decision Twin

```text
/api/simulation/compare?store_id=S001&product_id=P001
```

### Example demand shock

```text
/api/simulation/demand-shock?store_id=S001&product_id=P001&demand_multiplier=1.5
```

## Data generated

Committed sample files live under `data/raw/` and deliberate scenario manifests under `data/demo/`.

The dataset includes explicit cases for critical stockout, near stockout, overstock, slow-moving stock, sales spike, sales drop, zero sales, insufficient history, cross-store transfer opportunity, and an incomplete inventory field.

## Architecture principle

**Gemini handles language interpretation and explanation. Python owns facts, calculations, business rules, simulations, and decisions.**

RetailIQ never asks an LLM to invent stock, revenue, demand velocity, days of cover, reorder quantities, transfer quantities, financial impact, or simulated scenario outcomes.

## Demo video

Add final Devfolio demo video link here before submission.
