# DrinkMind Architecture

This document describes the current DrinkMind implementation. It focuses on the
real data paths in the app: manual drink logging, agent-assisted draft logging,
knowledge-prioritized nutrition estimation, Composition Estimation fallback with
ingredient-level range rules, saved explainability, and the Human Feedback Loop.

## 1. Current System Overview

```mermaid
flowchart LR
    User["User"] --> Frontend["Vite Frontend<br/>Dashboard, Chat, Explainability, DB Review"]
    Frontend --> API["FastAPI Backend"]

    API --> ManualLog["POST /api/log_drink"]
    API --> AgentAct["POST /api/agent/act"]
    API --> Feedback["POST /api/logs/{id}/nutrition_feedback"]
    API --> Review["Knowledge Acquisition APIs"]

    AgentAct --> Orchestrator["Agent Orchestrator<br/>backend/agents/orchestrator.py"]
    Orchestrator --> Intake["Intake Parser"]
    Orchestrator --> NutritionAgent["Nutrition Agent"]
    Orchestrator --> Risk["Risk Agent"]
    Orchestrator --> Memory["Memory Agent"]
    Orchestrator --> Plan["Health Plan Agent"]

    ManualLog --> Pipeline["estimate_drink_nutrition<br/>backend/agents/nutrition_pipeline.py"]
    NutritionAgent --> Pipeline

    Pipeline --> Graph["LangGraph Nutrition StateGraph"]
    Graph --> Enrichment["lookup_knowledge<br/>enrich_drink_data reuse"]
    Enrichment --> SQL["SQLite DrinkKnowledge<br/>exact/alias/product match"]
    Enrichment --> RAG["ChromaDB RAG<br/>knowledge retrieval"]
    Graph --> Composition["Composition Estimation Agent<br/>decompose + ingredient range rules"]
    Graph --> Result["Stable nutrition result<br/>best estimates + ranges + explainability"]

    ManualLog --> PersistLog["Persist DrinkLog<br/>composition_json + explainability_json"]
    Result --> PersistLog

    AgentAct --> Draft["Return agent_state<br/>final_action=fill_log_form"]
    Result --> Draft

    Feedback --> Candidate["ProductCandidate"]
    Feedback --> Evidence["NutritionEvidence"]
    Review --> Knowledge["DrinkKnowledge"]
    Knowledge --> SQL
    Review --> RAG

    PersistLog --> DB[("SQLite")]
    Candidate --> DB
    Evidence --> DB
    Knowledge --> DB
    Memory <--> DB
    Plan <--> DB
```

## 2. Nutrition Pipeline Contract

The shared entry point is `estimate_drink_nutrition(drink, db)` in
`backend/agents/nutrition_pipeline.py`.

Nutrition estimation is implemented as an explicit LangGraph `StateGraph`. The
external contract remains `estimate_drink_nutrition(drink, db)`, so manual
logging and agent-assisted logging both enter the same workflow without calling
separate nutrition implementations.

Graph nodes:

- `normalize_input`
- `lookup_knowledge`
- `route_estimation`
- `use_knowledge_result`
- `composition_decompose`
- `composition_estimate`
- `verify_result`
- `build_explainability`

`lookup_knowledge` currently reuses the existing `enrich_drink_data` function.
This preserves the current SQL/RAG behavior; SQL/RAG internals have not been
fully split out of `backend/agent.py`.

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

The graph first calls the existing enrichment path, then decides whether to
keep a trusted knowledge result or replace weak fallback estimates with
deterministic Composition Estimation.

Current priority:

1. Keep `SQL_EXACT_MATCH`.
2. Keep accepted `RAG_MATCH`.
3. Replace `LLM_ESTIMATION` and `LOCAL_ESTIMATOR` with Composition Estimation
   when possible.
4. Also use Composition Estimation when there is no matched knowledge ID and
   confidence is below the pipeline threshold.
5. Normalize the final result into stable fields: `caffeine`, `sugarContent`,
   `data_source`, `confidence`, `reasoning`, `estimation_method`,
   `matched_knowledge_id`, `retrieval_score`, `composition`, and
   `explainability`.

The Composition Estimation Agent is deterministic. It estimates drink
components such as espresso, milk base, tea base, fruit base, and syrup, then
builds component-level reasoning, warnings, and uncertainty drivers. Ingredient
rules live in `backend/agents/ingredient_rules.py` and provide likely ranges
for caffeine and sugar contributors.

Composition results remain backward compatible: `caffeine` and `sugarContent`
are still best estimates for existing callers. Composition estimation can also
return:

- `caffeine_range`
- `sugar_range`
- `composition.components[].caffeine_range_mg`
- `composition.components[].sugar_range_g`
- `composition.uncertainty_drivers`

Explainability should be interpreted as best estimate plus likely range plus
the sources of uncertainty. SQL/RAG knowledge paths can continue returning
single-point values when reviewed product data is available.

For debugging and demos, explainability now also includes:

- `explainability.graph_trace`: the executed LangGraph node sequence.
- `explainability.verification`: non-mutating verification status, warnings,
  and issues produced by `verify_result`.

The frontend defaults to a user-friendly Estimate Result view. Technical
details such as LangGraph workflow, component lists, retrieval score, raw
reasoning, and verification remain available but folded, so LangGraph is not
the default user-facing message.

## 3. Manual Logging Path

`POST /api/log_drink` is the path that persists a consumed drink.

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as FastAPI
    participant NP as Nutrition Pipeline
    participant SQL as DrinkKnowledge
    participant RAG as ChromaDB
    participant CA as Composition Agent
    participant DB as SQLite DrinkLog

    FE->>API: POST /api/log_drink
    API->>NP: estimate_drink_nutrition(drink, db)
    NP->>NP: normalize_input
    NP->>SQL: lookup_knowledge via enrich_drink_data
    alt Trusted SQL match
        SQL-->>NP: SQL_EXACT_MATCH result
        NP->>NP: use_knowledge_result
    else No SQL match
        NP->>RAG: lookup_knowledge tries accepted retrieval
        alt Accepted RAG match
            RAG-->>NP: RAG_MATCH result
            NP->>NP: use_knowledge_result
        else Weak or missing knowledge
            NP->>CA: composition_decompose
            NP->>CA: composition_estimate
            CA-->>NP: COMPOSITION_ESTIMATION result
        end
    end
    NP->>NP: verify_result
    NP->>NP: build_explainability
    NP-->>API: Stable nutrition result
    API->>DB: Save DrinkLog with composition_json/explainability_json
    API-->>FE: Result and daily insight payload
```

Persistence details:

- `composition_json` stores structured component estimates when Composition
  Estimation is used, including component-level ranges and uncertainty drivers
  when available.
- `explainability_json` stores method, knowledge-match state, confidence,
  reasoning, assumptions, warnings, `graph_trace`, `verification`, and feedback
  metadata when present.
- `GET /api/logs` deserializes those JSON fields so the frontend can replay
  saved explainability from historical logs.

## 4. Agent-Assisted Logging Path

`POST /api/agent/act` does not directly save a `DrinkLog` for drink logging.
It returns a draft nutrition result and `final_action="fill_log_form"` so the
frontend can fill or confirm the log form.

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as FastAPI
    participant OR as Orchestrator
    participant IP as Intake Parser
    participant NA as Nutrition Agent
    participant NP as Nutrition Pipeline
    participant DB as AgentTrace

    FE->>API: POST /api/agent/act
    API->>OR: run_agent_orchestrator(message, date, db)
    OR->>IP: parse_intake(message)
    alt Missing drink fields
        OR-->>API: final_action=ask_follow_up
    else Complete drink fields
        OR->>NA: estimate_from_parsed_drink(parsed, date, db)
        NA->>NP: estimate_drink_nutrition(draft, db)
        NP-->>NA: nutrition_result
        NA-->>OR: draft nutrition result
        OR-->>API: final_action=fill_log_form
    end
    API->>DB: save AgentTrace
    API-->>FE: agent_state
```

This distinction matters for demos and documentation: the agent path prepares a
structured draft, while `/api/log_drink` is the path that persists the actual
consumed drink.

## 5. Explainability Replay

When a drink is persisted through `/api/log_drink`, the API stores the normalized
pipeline output on `DrinkLog`.

The frontend can later:

- Fetch logs through `GET /api/logs`.
- Click a historical log.
- Rebuild the Nutrition Explainability panel from saved `composition` and
  `explainability`.
- Show the Estimate Result first, including best estimate, likely range when
  available, and the plain-language source of uncertainty.
- Keep knowledge/composition source, assumptions, warnings, LangGraph trace, raw
  reasoning, and prior feedback metadata in folded technical details.

This replay is persistence-based; it does not re-run the estimator.

## 6. Human Feedback Loop

Feedback corrects one saved drink log immediately and can optionally stage
reviewable evidence for future estimates. The normal user form is simplified to
the corrected caffeine/sugar values, source note, and review-queue option;
brand/type/date and other metadata remain available only as advanced details.

```mermaid
flowchart TD
    Log["Saved DrinkLog"] --> FeedbackForm["Nutrition Feedback Form"]
    FeedbackForm --> FeedbackAPI["POST /api/logs/{id}/nutrition_feedback"]

    FeedbackAPI --> UpdateLog["Optional: update current DrinkLog"]
    UpdateLog --> Explainability["Store feedback metadata<br/>inside explainability_json.feedback"]

    FeedbackAPI --> SubmitEvidence{"submit_as_evidence?"}
    SubmitEvidence -->|No| Done["Only this log is corrected"]
    SubmitEvidence -->|Yes| Candidate["Create or reuse ProductCandidate"]
    Candidate --> Evidence["Create NutritionEvidence<br/>source_type=user_feedback"]
    Evidence --> ReviewUI["Knowledge Acquisition Review UI"]
    ReviewUI --> Approve["Approve evidence"]
    Approve --> Knowledge["Create or update DrinkKnowledge"]
    Knowledge --> Future["Future same-product estimates<br/>prefer SQL_EXACT_MATCH"]
```

The feedback endpoint does not write directly to `DrinkKnowledge`. This keeps
the trust boundary clear: users can fix their own log immediately, but reusable
knowledge must pass through review.

## 7. Knowledge Acquisition

Knowledge Acquisition manages product candidates and nutrition evidence.

Implemented paths include:

- Manual candidate creation.
- Evidence creation for a candidate.
- Image analysis staging/import flow.
- Evidence approval into `DrinkKnowledge`.
- ChromaDB synchronization after knowledge approval.
- Bulk approval and deletion helpers.

Approved evidence can become future exact SQL knowledge, which the nutrition
pipeline keeps ahead of Composition Estimation.

## 8. Agent Trace, Memory, And Health Plans

`AgentTrace` records observability fields for agent runs:

- `trace_id`
- `intent`
- `agents_called`
- `tools_used`
- `retrieved_docs`
- `model_name`
- `latency_ms`
- `confidence`
- `final_action`
- `error`

Memory stores user preferences and goals in `UserPreference`. The Health Plan
Agent creates and updates 7-day plans in `HealthPlan`. These are active agent
features, but they are separate from the nutrition persistence path.

## 9. Main Persistent Objects

| Object | Purpose |
| --- | --- |
| `DrinkLog` | Saved consumed drinks, totals, method metadata, `composition_json`, and `explainability_json`. |
| `DrinkKnowledge` | Reviewed reusable nutrition knowledge used by SQL exact matching and Chroma sync. |
| `ProductCandidate` | Review candidate that may become knowledge. |
| `NutritionEvidence` | Reviewable nutrition evidence for a candidate. |
| `AgentTrace` | Agent execution observability. |
| `UserPreference` | Memory preferences and goals. |
| `HealthPlan` | 7-day plans and progress. |
| `ChatLog` | Chat history. |

## 10. Demo Talking Points

1. Manual logging persists explainability; agent logging prepares a draft.
2. Both paths enter the LangGraph Nutrition StateGraph through
   `estimate_drink_nutrition(drink, db)`.
3. SQL/RAG knowledge has priority over Composition Estimation.
4. Composition Estimation provides a backward-compatible best estimate plus
   likely range and uncertainty drivers instead of a black-box final number.
5. The default UI message is the Estimate Result; `explainability.graph_trace`,
   retrieval score, raw reasoning, and `explainability.verification` remain
   folded for technical inspection.
6. Saved explainability can be replayed from history.
7. Feedback fixes one log immediately but only becomes reusable knowledge after
   review.
8. The quality gate keeps backend behavior, composition eval, and frontend build
   aligned.
