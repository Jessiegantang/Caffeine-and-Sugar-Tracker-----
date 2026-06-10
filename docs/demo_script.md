# DrinkMind Demo Script

This script uses only currently implemented flows. It is designed for a local
interview or portfolio demo on Windows PowerShell.

## 1. Start Backend And Frontend

From the project root:

```powershell
.\scripts\start_demo.ps1
```

If you prefer separate terminals:

```powershell
cd backend
.\venv\Scripts\python.exe -m uvicorn main:app --reload
```

Then in another terminal:

```powershell
npm run dev
```

Open the Vite URL printed by the frontend, usually `http://localhost:5173`.

## 2. Log A Coconut Latte And Show Composition Estimation

In the app, log a coconut latte that does not already have a reviewed exact
knowledge match. A useful demo input is:

```text
brand: DemoCafe
name: Coconut Latte
type: coffee
sugar: three
volume: 500
```

Submit the drink through the normal logging flow.

Expected result:

- The drink is saved in history.
- The nutrition result includes caffeine and sugar totals.
- If no trusted SQL/RAG match exists for that product, the method should show
  Composition Estimation behavior rather than a product knowledge match.

## 3. Open The Nutrition Explainability Panel

Open the Nutrition Explainability panel after the estimate appears.

Show:

- Method and source.
- Confidence.
- Estimated caffeine and sugar.
- Whether a knowledge match was used.
- Components such as espresso, coconut milk/base, syrup, assumptions, and
  warnings when Composition Estimation is used.
- `explainability.graph_trace`, which shows the LangGraph nodes executed.
- `explainability.verification`, which shows non-mutating verification warnings
  and issues for the estimate.

Explain the key point:

```text
DrinkMind now runs nutrition estimation through a LangGraph StateGraph. It does
not only output final caffeine/sugar numbers; it stores the workflow trace and
reasoning shape needed to replay and inspect the estimate later.
```

The graph nodes are:

```text
normalize_input
lookup_knowledge
route_estimation
use_knowledge_result
composition_decompose
composition_estimate
verify_result
build_explainability
```

For a knowledge-backed estimate, the path is:

```text
normalize_input -> lookup_knowledge -> route_estimation ->
use_knowledge_result -> verify_result -> build_explainability
```

For a Composition Estimation fallback, the path is:

```text
normalize_input -> lookup_knowledge -> route_estimation ->
composition_decompose -> composition_estimate -> verify_result ->
build_explainability
```

`lookup_knowledge` currently reuses `enrich_drink_data`, so SQL/RAG lookup
behavior is preserved rather than fully split out of `backend/agent.py`.

## 4. Replay Saved Explainability From A Historical Log

Click the saved drink in the historical log list.

Expected result:

- The Nutrition Explainability panel is rebuilt from the saved log.
- It uses `composition_json` and `explainability_json`.
- The estimator is not re-run just to display the historical reasoning.

This demonstrates explainability persistence/replay.

## 5. Submit Nutrition Feedback

In the Nutrition Explainability panel, use the correction form for the saved
drink.

Example correction:

```text
brand: DemoCafe
name: Coconut Latte
type: coffee
volume: 500
caffeine: 120
sugarContent: 18
Evidence note: Demo label says 120mg caffeine and 18g sugar per 500ml cup.
```

Select:

```text
Apply to this log
Add to review queue
```

Submit the feedback.

Expected result:

- The current `DrinkLog` values update immediately.
- The explainability panel shows feedback metadata.
- The frontend shows that feedback was added to the review queue.

## 6. Show Feedback Evidence In The Review Queue

Open the database or knowledge acquisition review area.

Show:

- A `ProductCandidate` for the corrected product, or a reused matching
  candidate.
- A `NutritionEvidence` row with `source_type=user_feedback`.
- Extracted nutrition values such as volume, caffeine, and sugar.

Explain the trust boundary:

```text
Feedback fixes the user's saved log immediately, but it does not directly
pollute reusable product knowledge.
```

## 7. Approve Evidence Into The Knowledge Base

In the review UI, approve the feedback evidence.

Expected result:

- The evidence is imported into `DrinkKnowledge`.
- ChromaDB is synchronized for retrieval.
- The approved knowledge can now be used by future estimates.

## 8. Log The Same Drink Again And Show SQL_EXACT_MATCH Priority

Log the same corrected product again:

```text
brand: DemoCafe
name: Coconut Latte
type: coffee
sugar: three
volume: 500
```

Expected result:

- The nutrition method should prefer `SQL_EXACT_MATCH` when the brand/name match
  is accepted.
- Composition Estimation is skipped because reviewed product knowledge has
  higher priority.
- The explainability panel should show the matched knowledge ID.
- `explainability.graph_trace` should show the knowledge path:
  `normalize_input -> lookup_knowledge -> route_estimation ->
  use_knowledge_result -> verify_result -> build_explainability`.

This closes the loop:

```text
Composition estimate -> human correction -> reviewed evidence -> knowledge base
-> future SQL exact match.
```

## 9. Run The Quality Gate

From the project root:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\quality_gate.ps1
```

Expected result:

- Backend unittest passes.
- Composition eval report passes.
- Frontend build passes.
- The script prints `Quality gate passed.`

If demo time is short, run the targeted backend test first:

```powershell
cd backend
.\venv\Scripts\python.exe -m unittest tests.test_nutrition_agent
```
