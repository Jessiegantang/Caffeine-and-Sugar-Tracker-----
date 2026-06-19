# Agent Effect Eval Report

Generated: 2026-06-19T00:33:13

| id | intent | action | risk | method | result | failures |
| --- | --- | --- | --- | --- | --- | --- |
| advice_low_budget | ask_advice | answer_advice | low | - | PASS | - |
| advice_medium_budget | ask_advice | answer_advice | medium | - | PASS | - |
| advice_high_caffeine_budget | ask_advice | answer_advice | high | - | PASS | - |
| advice_high_sugar_budget | ask_advice | answer_advice | high | - | PASS | - |
| log_luckin_coconut_latte | log_drink | fill_log_form | low | SQL_EXACT_MATCH | PASS | - |
| log_cotti_super_coconut_americano | log_drink | fill_log_form | medium | COMPOSITION_ESTIMATION | PASS | - |
| log_starbucks_americano_exact_evidence | log_drink | fill_log_form | medium | SQL_EXACT_MATCH | PASS | - |
| followup_missing_sugar | log_drink | ask_follow_up | - | - | PASS | - |
| log_milk_tea_half | log_drink | fill_log_form | low | COMPOSITION_ESTIMATION | PASS | - |
| log_fruit_tea_no_sugar | log_drink | fill_log_form | medium | COMPOSITION_ESTIMATION | PASS | - |
| log_americano_full_sugar | log_drink | fill_log_form | low | COMPOSITION_ESTIMATION | PASS | - |
| log_oat_latte_half | log_drink | fill_log_form | low | COMPOSITION_ESTIMATION | PASS | - |
| risk_after_existing_medium_plus_drink | log_drink | fill_log_form | medium | COMPOSITION_ESTIMATION | PASS | - |
| risk_after_existing_high_plus_drink | log_drink | fill_log_form | high | COMPOSITION_ESTIMATION | PASS | - |
| memory_reduce_sugar | log_drink | fill_log_form | low | SQL_EXACT_MATCH | PASS | - |
| offline_advice_with_caffeine_preference_text | ask_advice | answer_advice | low | - | PASS | - |
| offline_no_llm_for_advice | ask_advice | answer_advice | low | - | PASS | - |
| offline_log_stability | log_drink | fill_log_form | medium | COMPOSITION_ESTIMATION | PASS | - |
| evidence_trace_shape | log_drink | fill_log_form | medium | COMPOSITION_ESTIMATION | PASS | - |
| followup_missing_volume_and_sugar | log_drink | ask_follow_up | - | - | PASS | - |

## Summary

- Total cases: 20
- Passed: 20
- Failed: 0
- Intent distribution: {'ask_advice': 6, 'log_drink': 14}
- Action distribution: {'answer_advice': 6, 'fill_log_form': 12, 'ask_follow_up': 2}
- LLM comparison: skipped

## Metrics

- intent_accuracy: 20/20 (100.00%)
- final_action_accuracy: 20/20 (100.00%)
- risk_level_accuracy: 13/13 (100.00%)
- required_tool_recall: 45/45 (100.00%)
- forbidden_tool_accuracy: 6/6 (100.00%)
- used_knowledge_match_accuracy: 3/3 (100.00%)
- parsed_field_accuracy: 29/29 (100.00%)
- nutrition_method_accuracy: 7/7 (100.00%)
- used_composition_accuracy: 6/6 (100.00%)
- trace_node_recall: 14/14 (100.00%)
- missing_field_recall: 3/3 (100.00%)
- offline_stability: 2/2 (100.00%)
- trace_event_shape_accuracy: 7/7 (100.00%)
