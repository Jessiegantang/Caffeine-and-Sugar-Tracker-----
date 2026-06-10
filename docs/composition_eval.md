# Composition Estimation Eval

This eval suite is a deterministic regression check for the rule-based
Composition Estimation Agent, ingredient-level range rules, and the shared
Nutrition Pipeline contract.

It is not a medical nutrition accuracy benchmark. The goal is to catch
unexpected behavior changes when component rules, pipeline selection logic, or
explainability output shape change.

Composition Estimation now returns backward-compatible best estimates while
also exposing likely ranges. `caffeine` and `sugarContent` remain the best
estimate fields. Composition results can also include `caffeine_range`,
`sugar_range`, component-level `caffeine_range_mg` / `sugar_range_g`, and
`uncertainty_drivers`.

## Fixture Coverage

The fixture lives at:

```text
backend/tests/fixtures/composition_eval_cases.json
```

Current cases cover:

- Coconut latte with partial sugar
- Coconut latte with no added sugar
- Americano with no sugar
- Americano with full sugar
- Latte with no added sugar
- Oat latte with half sugar
- Milk tea with half sugar
- Milk tea with full sugar
- Fruit tea with no added sugar
- Fruit tea with seven sugar
- Unknown drink with unknown sugar
- Missing volume fallback
- SQL exact knowledge match that must not be replaced by composition

## Checked Metrics

Each case can assert:

- Expected pipeline method
- Whether composition was used
- Whether a knowledge match was used
- Inferred drink type
- Required component names
- Caffeine range
- Sugar range
- Component-level caffeine and sugar range fields when composition is used
- Uncertainty drivers when composition is used
- Minimum confidence
- Reasoning list shape
- Explainability payload presence

Fixture ranges are intentionally broad. They are meant to catch regressions, not
force false precision. The output ranges explain likely uncertainty around the
best estimate, while SQL exact knowledge can still remain a single-point
reviewed value.

## Run

From the backend directory:

```powershell
venv\Scripts\python.exe -m unittest tests.test_composition_eval
```

Or run the full backend suite:

```powershell
venv\Scripts\python.exe -m unittest discover -s tests
```

The eval runner disables external vector retrieval and LLM calls so it remains
stable offline.
