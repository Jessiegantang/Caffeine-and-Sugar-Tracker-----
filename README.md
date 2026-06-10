# DrinkMind

DrinkMind is a composition-aware nutrition estimation agent for caffeine and
sugar tracking. It combines natural-language drink parsing, a unified nutrition
pipeline, trusted knowledge lookup, deterministic Composition Estimation, saved
explainability, and a human feedback review loop.

## Key Features

- Natural-language drink parsing for common drink logging messages.
- Unified nutrition pipeline used by manual logging and agent-assisted logging.
- SQL and RAG knowledge priority for reviewed product nutrition data.
- Composition Estimation fallback for drinks without a trusted exact match.
- Explainability persistence and replay through `composition_json` and
  `explainability_json` on `DrinkLog`.
- Human Feedback Loop for correcting one estimate and optionally submitting it
  as reviewable evidence.
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
python init_rag.py
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
priority, result shape, confidence ranges, and explainability payloads.

## Demo Flow

See `docs/demo_script.md` for a complete executable demo:

1. Start backend and frontend.
2. Log a coconut latte and show Composition Estimation.
3. Open the Nutrition Explainability panel.
4. Replay saved explainability from a historical log.
5. Submit nutrition feedback.
6. Review the generated feedback evidence.
7. Approve evidence into the knowledge base.
8. Log the same drink again and show `SQL_EXACT_MATCH` priority.
9. Run the quality gate.

## Project Structure

```text
backend/
  main.py                         FastAPI API routes and persistence wiring
  agent.py                        Legacy enrichment, SQL/RAG lookup, chat helpers
  database.py                     SQLAlchemy models and lightweight migrations
  agents/
    composition_agent.py          Deterministic component-based estimator
    nutrition_pipeline.py         Stable nutrition estimation contract
    nutrition_agent.py            Orchestrator-facing nutrition boundary
    orchestrator.py               LangGraph agent routing
    knowledge_acquisition_agent.py Candidate/evidence review helpers
    memory_agent.py               User preference memory
    risk_agent.py                 Daily caffeine/sugar risk checks
    health_plan_agent.py          7-day plan generation and progress
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

## Legacy Tools

Historical repair, dump, search, and debug scripts are kept in `tools/legacy/`
so the project root stays focused on the current app entry points.
