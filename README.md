# DrinkMind

DrinkMind is a composition-aware nutrition estimation agent for caffeine and
sugar tracking. It combines natural-language drink parsing, a unified nutrition
pipeline, trusted knowledge lookup, deterministic Composition Estimation, saved
explainability, and a human feedback review loop.

## Key Features

- Natural-language drink parsing for common drink logging messages.
- LangGraph StateGraph nutrition workflow used by manual logging and
  agent-assisted logging.
- SQL and RAG knowledge priority for reviewed product nutrition data.
- Composition Estimation fallback for drinks without a trusted exact match,
  backed by ingredient-level range rules.
- Backward-compatible best estimates in `caffeine` and `sugarContent`, with
  optional `caffeine_range`, `sugar_range`, component-level ranges, and
  `uncertainty_drivers` when composition estimation is used.
- Explainability persistence and replay through `composition_json` and
  `explainability_json` on `DrinkLog`. The product UI defaults to a friendly
  Estimate Result view, while LangGraph traces, retrieval score, raw reasoning,
  components, and verification details remain folded under technical details.
- Human Feedback Loop for correcting one estimate through a simplified form and
  optionally submitting it as reviewable evidence.
- Knowledge Acquisition review flow from `ProductCandidate` and
  `NutritionEvidence` into `DrinkKnowledge`.
- Composition eval report and PowerShell quality gate for regression checks.

## How To Run

Install frontend dependencies:

```bash
npm install
```

Install backend dependencies:

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Configure environment variables:

```bash
copy backend\.env.example backend\.env
```

Then edit `backend\.env` and set any API keys you want to use. Do not commit
`.env`.

Initialize the local knowledge base:

```bash
cd backend
python -m scripts.init_rag
```

Start the backend:

```bash
cd backend
uvicorn main:app --reload
```

The API runs at `http://127.0.0.1:8000`.

Start the frontend in another terminal:

```bash
npm run dev
```

The Vite app prints the local URL, usually `http://localhost:5173`.

On Windows PowerShell, the demo helper can start both services:

```powershell
.\scripts\start_demo.ps1
```

## Quality Gate

Run the full local quality gate from the project root:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\quality_gate.ps1
```

The gate runs:

- Backend unittest discovery.
- Composition eval report.
- Frontend build.

## Testing And Eval

Run all backend tests:

```powershell
cd backend
venv\Scripts\python.exe -m unittest discover -s tests
```

Run only the nutrition agent tests:

```powershell
cd backend
venv\Scripts\python.exe -m unittest tests.test_nutrition_agent
```

Run the Composition Estimation eval:

```powershell
cd backend
venv\Scripts\python.exe tests\run_composition_eval_report.py
```

The eval suite checks deterministic composition behavior, SQL knowledge
priority, result shape, confidence ranges, component-level range fields, and
explainability payloads.

## Nutrition Workflow

Nutrition estimation is now an explicit LangGraph `StateGraph` inside
`backend/workflows/nutrition_pipeline.py`. The public contract remains
`estimate_drink_nutrition(drink, db)`, and both `/api/log_drink` and
`/api/agent/act` enter the same workflow through that function.

Graph nodes:

- `normalize_input`
- `lookup_knowledge`
- `route_estimation`
- `use_knowledge_result`
- `composition_decompose`
- `composition_estimate`
- `verify_result`
- `build_explainability`

Knowledge path:

```text
normalize_input -> lookup_knowledge -> route_estimation ->
use_knowledge_result -> verify_result -> build_explainability
```

Composition path:

```text
normalize_input -> lookup_knowledge -> route_estimation ->
composition_decompose -> composition_estimate -> verify_result ->
build_explainability
```

`lookup_knowledge` uses `knowledge.knowledge_lookup.enrich_drink_data`; SQL/RAG
internals now live under `backend/knowledge`. For demos and debugging, the
result explainability includes `explainability.graph_trace` and
`explainability.verification`.

Composition Estimation now uses ingredient-level range rules. The top-level
`caffeine` and `sugarContent` fields remain best estimates for existing callers.
Composition results can also include `caffeine_range`, `sugar_range`,
`components[].caffeine_range_mg`, `components[].sugar_range_g`, and
`composition.uncertainty_drivers`. Explainability should be read as a best
estimate plus a likely range and the main sources of uncertainty, not as a
lab-precise nutrition label.

The frontend keeps this product-facing: users see an Estimate Result first.
Technical details such as LangGraph workflow, retrieval score, raw reasoning,
component lists, and verification remain available but folded by default.

## Demo Flow

See `docs/demo_script.md` for a complete executable demo:

1. Start backend and frontend.
2. Log a coconut latte and show Composition Estimation.
3. Open the Estimate Result panel and expand technical details if needed.
4. Replay saved explainability from a historical log.
5. Submit nutrition feedback.
6. Review the generated feedback evidence.
7. Approve evidence into the knowledge base.
8. Log the same drink again and show `SQL_EXACT_MATCH` priority.
9. Run the quality gate.

## Project Structure

```text
backend/
  main.py                         FastAPI app bootstrap and router registration
  api/                            API schemas and routers
  services/                       Business services called by routers
  db/
    database.py                   SQLAlchemy models, session, and lightweight migrations
  agents/
    nutrition_agent.py            Orchestrator-facing nutrition boundary
    orchestrator.py               LangGraph agent routing
    memory_agent.py               User preference memory
    health_plan_agent.py          7-day plan generation and progress
  rules/                          Deterministic nutrition and risk rules
  knowledge/                      Knowledge lookup, Chroma/RAG, and acquisition
  workflows/                      LangGraph workflows
  scripts/                        Backend maintenance scripts
  tests/                          Unit tests and composition eval fixtures

docs/
  architecture.md                 Current implementation architecture
  composition_eval.md             Eval design and coverage
  feedback_loop.md                Human Feedback Loop details
  demo_script.md                  End-to-end demo flow

src/
  components/                     Frontend panels and database review UI
  api.js                          Frontend API client

scripts/
  quality_gate.ps1                Backend tests, eval report, frontend build
  start_demo.ps1                  Local demo startup helper
```
