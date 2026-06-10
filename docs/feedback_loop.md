# Human Feedback Loop

## Purpose

The Human Feedback Loop lets a user correct one nutrition estimate and turn that correction into reviewable evidence for future estimates. It solves the gap between a one-off Composition Estimation result and a durable, trusted knowledge match.

The loop has two goals:

- Make the current `DrinkLog` accurate immediately, so daily totals and history reflect the user's correction.
- Keep the shared knowledge base protected by routing user feedback through the existing acquisition review flow before it can become `DrinkKnowledge`.

## User Correction Flow

1. A user logs a drink or opens a historical drink log.
2. The Nutrition Explainability panel shows the current estimate, method, confidence, composition details, and knowledge match state.
3. If the current result has a `log_id`, the panel shows a correction form.
4. The user edits `brand`, `name`, `type`, `volume`, `caffeine`, `sugarContent`, and an optional evidence note.
5. The user chooses whether to update only the current log, submit reviewable evidence, or both.
6. The frontend calls `POST /api/logs/{log_id}/nutrition_feedback`.
7. The backend updates the log if requested and creates pending evidence if requested.
8. A reviewer can approve the evidence through the existing Knowledge Acquisition UI.
9. After approval, future estimates for the same product can use `SQL_EXACT_MATCH` instead of Composition Estimation.

## `apply_to_log` vs `submit_as_evidence`

`apply_to_log=true` updates only the specific `DrinkLog` selected by the user. This makes today's totals, history, and replayed explainability accurate immediately.

`submit_as_evidence=true` creates or reuses a `ProductCandidate` and creates a `NutritionEvidence` row with `source_type="user_feedback"`. The evidence remains pending review and is not imported into `DrinkKnowledge` automatically.

These flags are independent:

- `apply_to_log=true`, `submit_as_evidence=false`: fix this one log only.
- `apply_to_log=false`, `submit_as_evidence=true`: submit evidence for review without changing the existing log.
- `apply_to_log=true`, `submit_as_evidence=true`: fix this log and add evidence to the review queue.

## Backend API

### `POST /api/logs/{log_id}/nutrition_feedback`

Request example:

```json
{
  "corrected": {
    "brand": "Cotti",
    "name": "Coconut Latte",
    "type": "coffee",
    "volume": 500,
    "caffeine": 120,
    "sugarContent": 18
  },
  "source_type": "user_feedback",
  "source_note": "Package label says caffeine 120mg, sugar 18g",
  "apply_to_log": true,
  "submit_as_evidence": true
}
```

Response example:

```json
{
  "status": "success",
  "log": {
    "id": "log_123",
    "brand": "Cotti",
    "name": "Coconut Latte",
    "type": "coffee",
    "volume": 500,
    "caffeine": 120,
    "sugarContent": 18,
    "explainability": {
      "feedback": {
        "corrected": {
          "brand": "Cotti",
          "name": "Coconut Latte",
          "type": "coffee",
          "volume": 500,
          "caffeine": 120,
          "sugarContent": 18
        },
        "source_note": "Package label says caffeine 120mg, sugar 18g",
        "source_type": "user_feedback",
        "previous": {
          "brand": "Cotti",
          "name": "Coconut Latte",
          "type": "coffee",
          "volume": 500,
          "caffeine": 95,
          "sugarContent": 14
        },
        "delta": {
          "volume": 0,
          "caffeine": 25,
          "sugarContent": 4
        },
        "high_delta": false
      }
    }
  },
  "candidate": {
    "id": "cand_abc123",
    "brand": "Cotti",
    "name": "Coconut Latte",
    "type": "coffee",
    "status": "evidence_ready"
  },
  "evidence": {
    "id": "ev_def456",
    "candidate_id": "cand_abc123",
    "source_type": "user_feedback",
    "status": "pending_review",
    "extracted": {
      "volume": 500,
      "caffeine": 120,
      "sugar": 18,
      "abv": null
    }
  }
}
```

Validation:

- `volume`: 10-2000 ml
- `caffeine`: 0-800 mg
- `sugarContent`: 0-150 g
- `type`: known drink type
- `source_note`: required when `submit_as_evidence=true`

## Data Flow

### `DrinkLog`

Stores one consumed drink. Feedback can update `brand`, `name`, `type`, `volume`, `caffeine`, and `sugarContent`. Feedback metadata is stored inside `explainability_json.feedback`.

### `ProductCandidate`

Represents a product that may become knowledge. Feedback evidence creates or reuses a candidate for the corrected `brand`, `name`, and `type`.

### `NutritionEvidence`

Stores reviewable evidence for a candidate. User feedback creates evidence with `source_type="user_feedback"` and English parseable `raw_evidence`, such as:

```text
user feedback for log_id=log_123 brand: Cotti name: Coconut Latte volume: 500ml caffeine: 120mg sugar: 18g note: Package label says caffeine 120mg, sugar 18g
```

### `DrinkKnowledge`

Stores approved product nutrition knowledge. User feedback does not write this table directly. It only reaches `DrinkKnowledge` after reviewer approval through `approve_evidence_to_knowledge`.

## Why Feedback Does Not Directly Write `DrinkKnowledge`

User feedback is useful but not automatically trusted. Direct writes would let accidental edits, guesses, typos, or malicious values pollute future estimates. The review step preserves the current trust boundary:

- Users can correct their own log immediately.
- Candidate and evidence rows are visible for review.
- Only approved evidence becomes reusable knowledge.
- Existing duplicate merge and confidence logic remains centralized in the acquisition flow.

## Why Approval Leads to `SQL_EXACT_MATCH`

When a reviewer approves feedback evidence, `approve_evidence_to_knowledge` creates or updates a `DrinkKnowledge` row. The nutrition pipeline calls `estimate_drink_nutrition`, which first runs the existing knowledge enrichment flow.

If the next drink has the same or compatible brand/name match:

1. `enrich_drink_data` finds the `DrinkKnowledge` row.
2. It returns `estimation_method="SQL_EXACT_MATCH"` with `matched_knowledge_id`.
3. `nutrition_pipeline` keeps SQL and RAG matches.
4. Composition Estimation is skipped because trusted knowledge has priority.

## Frontend Entry Points

### Nutrition Explainability Panel

The panel shows method, source, confidence, current estimate, knowledge match, composition details, reasoning, assumptions, warnings, and feedback metadata.

### Historical Log Replay

Clicking a historical log replays the saved nutrition explainability into the panel. If the log has an id, the correction form becomes available.

### Feedback Form

The form is shown only when the current result includes `log_id`. It includes:

- `brand`
- `name`
- `type`
- `volume`
- `caffeine`
- `sugarContent`
- `source_note`
- `apply_to_log`
- `submit_as_evidence`

After submit, the frontend refreshes logs when `apply_to_log=true`, updates totals, and displays feedback metadata. If evidence was created, it shows `Feedback added to review queue`.

## Tests and Acceptance

### Quality Gate

Run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\quality_gate.ps1
```

Expected result:

- Backend unittest passes.
- Composition eval report passes.
- Frontend build passes.
- The script prints `Quality gate passed.`

### API Tests

The API tests cover:

- Feedback updates `DrinkLog` values.
- `explainability_json` receives feedback metadata.
- `submit_as_evidence=false` creates no candidate or evidence.
- `submit_as_evidence=true` creates `ProductCandidate` and `NutritionEvidence`.
- Evidence extraction contains `volume`, `caffeine`, and `sugar`.
- Invalid ranges return 400.
- Missing `source_note` with `submit_as_evidence=true` returns 400.
- Approving feedback evidence creates or updates `DrinkKnowledge`.
- Future estimation for the same brand/name prefers `SQL_EXACT_MATCH`.

### Eval Report

The composition eval report remains the guardrail for the base Composition Estimation contract. Feedback should not change Composition Agent rules. The eval report should continue to show expected composition behavior and that SQL matches are kept when knowledge is available.

## Current Limits and Future Work

Current limits:

- No dedicated feedback history table.
- Feedback metadata is stored inside `explainability_json`.
- User feedback has no user identity, trust score, or reviewer attribution.
- The frontend form is intentionally lightweight and does not support image upload.
- Candidate reuse is based on simple brand/name/type matching.

Future work:

- Add reviewer notes and approval provenance.
- Add conflict detection for multiple feedback rows on the same product.
- Support attaching package or menu screenshots as evidence.
- Add a feedback history view.
- Add per-user trust levels or source reliability weighting.
- Add better normalization for brand aliases and multilingual product names.
