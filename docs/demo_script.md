# DrinkMind Demo Script

## Scene 1: Natural Language Drink Logging

User says:

```text
我刚喝了一杯瑞幸生椰拿铁，大杯，三分糖。
```

Expected demo points:

- `POST /api/agent/parse_intake` returns structured JSON.
- Chat shows parsed intake fields.
- The drink form is filled without frontend field guessing.
- Saving the drink runs the nutrition pipeline and shows source, confidence, method, trace, and reasoning.

## Scene 2: Ask Whether Coffee Still Fits Today

User says:

```text
我现在还能喝咖啡吗？
```

Expected demo points:

- `POST /api/agent/act` routes to `ask_advice`.
- The response includes risk evaluation.
- `GET /api/agent/traces` shows agents called, tools used, final action, latency, and error status.

## Scene 3: Weekly Report And Plan-Aware Advice

User says:

```text
我想一周内减少奶茶糖分，帮我做一个7天计划。
```

Expected demo points:

- `POST /api/agent/act` routes to `create_health_plan`.
- The generated plan has `day`, `goal`, `suggestion`, and `status`.
- `GET /api/health/plans/active` displays the active plan.
- `POST /api/health/plans/active/progress?date=YYYY-MM-DD` updates plan progress.
- Weekly report includes active plan progress.

## Useful Demo Commands

```powershell
.\scripts\start_demo.ps1
```

```powershell
cd backend
venv\Scripts\python.exe -m unittest discover -s tests
```
