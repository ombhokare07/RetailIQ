TRACK_ID=PS03

# RetailIQ — Multilingual Sales & Inventory Copilot

RetailIQ is a decision-support application for small multi-store retailers. It works over committed sales, inventory, product, and store data. Deterministic Python logic owns business facts, calculations, recommendations, simulations, and financial estimates. Gemini is used only for language interpretation when deterministic routing is insufficient and for grounded explanation after Python has produced the evidence.

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

The judge supplies this environment variable. Never commit a key. The application starts without a Gemini key and makes **no network call at startup**. When Gemini is unavailable or fails, RetailIQ returns a deterministic multilingual fallback instead of crashing.

Optional model override:

```text
GEMINI_MODEL
```

## Current functionality — Phase 6

Phase 6 delivers the complete single-process RetailIQ experience: deterministic analytics, Decision Twin, financial intelligence, grounded multilingual Gemini copilot, explainability, and the committed production dashboard served by FastAPI.

Supported languages:

- English
- Hindi
- Marathi

Supported copilot tasks include:

- What needs attention today?
- Which products may run out?
- Which products are overstocked or slow-moving?
- Which products show a sales spike/drop?
- How did a product or store perform?
- Is there a safe inter-store transfer?
- What is the financial impact?
- Compare transfer vs supplier reorder vs no action.
- What if demand increases?
- Why did sales change? RetailIQ reports the measured change but refuses to invent a cause when causal evidence is absent.

## GenAI grounding design

RetailIQ deliberately does **not** let Gemini query raw data freely or calculate retail metrics.

```text
User question
    ↓
Language detection + entity resolution
    ↓
Intent/tool selection
    ↓
Deterministic Python analytics / decision engine / simulation
    ↓
Evidence packet with exact record IDs + facts + unknowns
    ↓
Gemini grounded explanation (optional)
    ↓
Numeric/fact-reference guard
    ↓
Structured response
```

Every copilot response includes the deterministic tool result, evidence citations to committed record IDs, unknown fields, and safeguards. If Gemini introduces a numeric value not present in the deterministic facts, the narrative is rejected and RetailIQ falls back to the deterministic response.

### Why no vector database/embedding retrieval in PS03?

PS03 works over exact structured sales/inventory records. RetailIQ uses direct deterministic record retrieval because exact product/store metrics are safer and more auditable than semantic retrieval for these calculations. No alternate embedding provider is used. If an embedding-based feature is added later, it must use the allowed Gemini embedding model rather than an external provider.

## Difficult cases intentionally handled

- Ambiguous product references such as `bread` return clarification candidates instead of silently choosing Brown Bread or White Bread.
- Missing inventory fields produce an `unknown`/`insufficient_data` result rather than fabricated values.
- `Why did Brown Bread sales fall in Pune?` reports the measured sales change but explicitly states that promotion, competitor, weather, and customer-behaviour evidence is absent, so cause cannot be established.
- Gemini missing/timeout/model failure does not break deterministic analytics or multilingual fallback answers.

## Key endpoints

```text
GET  /health
GET  /api/data/summary
GET  /api/dashboard/summary
GET  /api/dashboard/assumptions
GET  /api/inventory/stockout-risk
GET  /api/inventory/overstock
GET  /api/inventory/slow-movers
GET  /api/inventory/health
GET  /api/sales/anomalies
GET  /api/products/{product_id}/performance
GET  /api/stores/{store_id}/performance
GET  /api/transfers/recommendations
GET  /api/financial/summary
GET  /api/financial/revenue-risk
GET  /api/financial/overstock-capital
GET  /api/financial/transfer-benefits
GET  /api/simulation/compare
GET  /api/simulation/demand-shock
GET  /api/copilot/status
POST /api/copilot/query
```

## Copilot examples

English:

```json
{"message":"Which products may run out in Pune?"}
```

Hindi:

```json
{"message":"पुणे में कौन से प्रोडक्ट का स्टॉक खत्म होने वाला है?","language":"hi"}
```

Marathi:

```json
{"message":"पुणे स्टोअरमध्ये कोणते प्रॉडक्ट लवकर संपणार आहेत?","language":"mr"}
```

Difficult causal case:

```json
{"message":"Why did Brown Bread sales fall in Pune?"}
```

Decision Twin:

```json
{"message":"What should I do about Amul Milk in Pune: transfer, reorder, or wait?"}
```

Demand shock:

```json
{"message":"What if demand for Amul Milk in Pune increases by 50%?"}
```

## Data generated

Committed sample files live under `data/raw/` and deliberate scenario manifests under `data/demo/`.

The dataset includes explicit cases for critical stockout, near stockout, overstock, slow-moving stock, sales spike, sales drop, zero sales, insufficient history, cross-store transfer opportunity, and an incomplete inventory field.

## Architecture principle

**Gemini handles language interpretation and grounded explanation. Python owns facts, calculations, business rules, simulations, and decisions.**

RetailIQ never asks an LLM to invent stock, revenue, demand velocity, days of cover, reorder quantities, transfer quantities, financial impact, or simulated scenario outcomes.

## Demo video

Add final Devfolio demo video link here before submission.

## Phase 6 — committed frontend dashboard

RetailIQ now includes a self-contained production dashboard in `frontend/dist/`. No Node.js, npm install, CDN, frontend dev server, or second terminal is required by judges. FastAPI serves the committed frontend build and the API from the same process.

Dashboard sections:

- Overview with live revenue, inventory health, stockout attention and transfer opportunity metrics.
- Inventory cockpit for stockout risk, overstock and slow movers.
- Sales Signals for deterministic spike/drop detection.
- Smart Transfers showing donor safety, transfer quantity, logistics estimate and purchase cash deferred.
- Decision Twin for no-action vs supplier-reorder vs smart-transfer what-if simulation.
- Financial Impact translating operational findings into revenue risk, blocked capital and transfer benefit.
- Grounded multilingual AI Copilot with English/Hindi/Marathi, evidence, unknowns and safeguard visibility.

Judge run path remains exactly:

```bash
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:8000`.

### Gemini model

RetailIQ is designed to use:

```text
gemini-2.5-flash-lite
