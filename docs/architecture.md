# DrinkMind Architecture

本文档说明 DrinkMind 的 multi-agent 架构、核心数据流，以及 RAG、Memory、Trace 在系统中的位置。它面向简历项目说明和面试展示，重点解释“用户一句自然语言如何变成可追踪、可落库、可个性化的健康建议”。

## 1. 总体架构

```mermaid
flowchart LR
    User["用户<br/>自然语言 / 表单录入"] --> Frontend["Vite Frontend<br/>Dashboard + Chat + DB Panel"]
    Frontend --> API["FastAPI Backend<br/>REST endpoints"]

    API --> Orchestrator["Agent Orchestrator<br/>backend/agents/orchestrator.py"]
    API --> LogAPI["Drink / Sleep / Knowledge APIs"]

    Orchestrator --> Intake["Intake Parser<br/>解析饮品、容量、糖度、时间"]
    Orchestrator --> Nutrition["Nutrition Agent<br/>营养估算与数据来源解释"]
    Orchestrator --> Risk["Risk Agent<br/>咖啡因 / 糖分风险评估"]
    Orchestrator --> Memory["Memory Agent<br/>偏好提取与读取"]
    Orchestrator --> Report["Report Agent<br/>日报 / 周报"]
    Orchestrator --> Plan["Health Plan Agent<br/>7 天计划与进度"]

    Nutrition --> SQLMatch["SQLite Exact Match<br/>DrinkKnowledge"]
    Nutrition --> RAG["ChromaDB RAG<br/>向量检索饮品知识"]
    Nutrition --> Estimator["Local Estimator<br/>规则兜底"]

    API --> DB[("SQLite<br/>DrinkLog / SleepRecord / ChatLog<br/>UserPreference / HealthPlan<br/>AgentTrace / Knowledge")]
    SQLMatch --> DB
    Memory <--> DB
    Report --> DB
    Plan <--> DB
    LogAPI --> DB
    RAG <--> VectorDB[("ChromaDB<br/>drink knowledge embeddings")]

    Orchestrator --> Trace["Trace Recorder<br/>trace_id / agents / tools / latency"]
    Trace --> DB
```

## 2. Multi-Agent 路由

`POST /api/agent/act` 是主要入口。后端会创建 `DrinkMindAgentState`，再由 orchestrator 根据解析结果和用户意图路由到不同 Agent 节点。

```mermaid
flowchart TD
    Start["POST /api/agent/act<br/>user_message + date"] --> State["初始化 Agent State<br/>trace_id, date, chat_context"]
    State --> Parse["Intake Parser Node"]
    Parse --> Intent{"Intent / Missing Fields"}

    Intent -->|log_drink + 信息完整| LogGate["Log Drink Gate"]
    Intent -->|log_drink + 信息缺失| FollowUp["Follow-up Node<br/>追问缺失字段"]
    Intent -->|create_health_plan| PlanNode["Health Plan Node"]
    Intent -->|ask_advice / other| Advice["Advice Node"]

    LogGate --> NutritionNode["Nutrition Agent"]
    NutritionNode --> RiskNode["Risk Agent"]
    RiskNode --> MemoryNode["Memory Agent<br/>extract + apply updates"]
    MemoryNode --> FormatLog["生成摄入结果回复"]

    PlanNode --> SavePlan["写入 HealthPlan"]
    SavePlan --> PlanMemory["记录目标到 Memory"]

    Advice --> ReadMemory["读取 UserPreference"]
    ReadMemory --> RiskContext["读取当日摄入 / 预算"]
    RiskContext --> AdviceResponse["生成建议回复"]

    FollowUp --> Finish["Finish State<br/>latency / confidence / final_action"]
    FormatLog --> Finish
    PlanMemory --> Finish
    AdviceResponse --> Finish
    Finish --> SaveTrace["save_agent_trace"]
    SaveTrace --> Response["返回 assistant response + agent_state"]
```

### Agent State 关键字段

- `trace_id`：一次 Agent 执行的唯一 ID。
- `intent`：解析后的用户意图，例如 `log_drink`、`ask_advice`、`create_health_plan`。
- `parsed_intake`：饮品名称、品牌、容量、糖度、时间等结构化字段。
- `agents_called`：本次执行经过哪些 Agent 节点。
- `tools_used`：本次执行用到的工具或策略，例如 local parser、SQLite exact match、RAG retrieval。
- `retrieved_docs`：RAG 或知识库命中的文档 ID。
- `memory_updates`：从本轮对话中提取出的偏好或目标。
- `final_action`：最终动作，例如记录饮品、追问字段、生成建议或创建计划。

## 3. 饮品录入与 RAG 营养估算数据流

这条链路展示“自然语言饮品记录”如何进入知识检索和营养估算流程。

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant OR as Agent Orchestrator
    participant IP as Intake Parser
    participant NA as Nutrition Agent
    participant SQL as SQLite DrinkKnowledge
    participant CH as ChromaDB
    participant LE as Local Estimator
    participant DB as SQLite DrinkLog / AgentTrace

    U->>FE: 我刚喝了一杯瑞幸生椰拿铁，大杯，三分糖
    FE->>API: POST /api/agent/act
    API->>OR: run_agent_orchestrator(user_message, date)
    OR->>IP: parse_intake_message
    IP-->>OR: parsed_intake

    OR->>NA: estimate_from_parsed_drink
    NA->>SQL: exact match by brand + name
    alt SQL exact match found
        SQL-->>NA: caffeine / sugar / volume / source
    else no exact match
        NA->>CH: RAG similarity search
        alt RAG hit found
            CH-->>NA: matched knowledge + score
        else no reliable hit
            NA->>LE: estimate by drink type, volume, sugar level
            LE-->>NA: fallback nutrition estimate
        end
    end

    NA-->>OR: nutrition + confidence + reasoning + matched_knowledge_id
    OR->>DB: save DrinkLog
    OR->>DB: save AgentTrace
    OR-->>API: assistant response + agent_state
    API-->>FE: structured result
```

## 4. Memory 数据流

Memory 的目标是让系统在后续建议里“记得用户偏好”，但仍然保持可检查、可清空，方便 demo 和测试。

```mermaid
flowchart TD
    Message["用户消息 / 饮品记录"] --> Extract["memory_agent.extract_memory_updates"]
    Extract --> Updates["memory_updates<br/>常喝饮品 / 糖度偏好 / 咖啡因敏感度 / 健康目标"]
    Updates --> Apply["apply_memory_updates"]
    Apply --> UserPref[("SQLite UserPreference")]

    UserPref --> Read["read_user_memory"]
    Read --> Context["Chat / Advice Context"]
    Context --> Advice["个性化建议<br/>例如减少奶茶糖分、控制咖啡因"]

    UserPref --> APIRead["GET /api/user/preferences"]
    APIRead --> Demo["面试展示 / Debug"]
    Demo --> Clear["DELETE /api/user/preferences"]
    Clear --> UserPref
```

## 5. Trace 可观测性数据流

Trace 用来解释 Agent 为什么这么回答、走过哪些节点、用了哪些工具，也能帮助测试 agent routing 是否正确。

```mermaid
flowchart LR
    Run["Agent Run"] --> TraceState["trace_state / agent_state"]
    TraceState --> Fields["trace_id<br/>intent<br/>agents_called<br/>tools_used<br/>retrieved_docs<br/>model_name<br/>latency_ms<br/>confidence<br/>final_action<br/>error"]
    Fields --> Save["save_agent_trace"]
    Save --> AgentTrace[("SQLite AgentTrace")]
    AgentTrace --> TraceAPI["GET /api/agent/traces"]
    TraceAPI --> UI["Frontend Trace / Demo View"]
    TraceAPI --> Tests["Backend tests<br/>trace recording assertions"]
```

## 6. Knowledge Acquisition 数据流

知识采集流程用于把新增饮品和营养证据纳入可检索知识库。

```mermaid
flowchart TD
    Admin["前端数据库管理 / 知识采集审核"] --> CandidateAPI["POST /api/knowledge/acquisition/candidates"]
    CandidateAPI --> Candidate[("ProductCandidate")]

    Admin --> EvidenceAPI["POST /api/knowledge/acquisition/candidates/{id}/evidence"]
    EvidenceAPI --> Evidence[("NutritionEvidence")]

    Evidence --> Approve["POST /api/knowledge/acquisition/evidence/{id}/approve"]
    Approve --> Knowledge[("DrinkKnowledge<br/>SQLite")]
    Approve --> Sync["sync_chroma_document"]
    Sync --> Chroma[("ChromaDB<br/>Vector Store")]

    Chroma --> RAGUse["Nutrition Agent RAG retrieval"]
    Knowledge --> ExactUse["Nutrition Agent SQLite exact match"]
```

## 7. 主要持久化对象

| 表 / 对象 | 用途 |
| --- | --- |
| `DrinkLog` | 用户每天的饮品摄入记录，包括 caffeine、sugarContent、alcoholContent、data_source、confidence、reasoning。 |
| `DrinkKnowledge` | 饮品知识库，供 SQLite exact match 和 ChromaDB 同步使用。 |
| `UserPreference` | Memory 存储，例如偏好、敏感度、目标。 |
| `HealthPlan` | 7 天健康计划及每日进度。 |
| `ChatLog` | 用户与助手的对话历史。 |
| `AgentTrace` | Agent 执行链路，支持观测、调试和测试。 |
| `ProductCandidate` | 待审核饮品候选。 |
| `NutritionEvidence` | 候选饮品的营养证据。 |

## 8. 面试讲解建议

可以按下面顺序讲：

1. 先讲用户场景：自然语言记录饮品，并询问当天能不能继续喝咖啡。
2. 再讲 Agent Orchestrator：统一维护 state，按 intent 路由到不同 Agent 节点。
3. 然后讲 RAG：营养数据先精确匹配，再向量检索，最后本地规则兜底，避免“一次 LLM 调用决定一切”。
4. 接着讲 Memory：把用户偏好和目标持久化，让建议可以跨会话延续。
5. 最后讲 Trace 和 tests：每次 Agent run 都能解释链路，测试覆盖解析、路由、Trace、Memory 和 health plan。
