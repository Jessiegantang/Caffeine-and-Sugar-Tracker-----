# Synthetic Agent Eval Report

Generated: 2026-06-19T01:07:29

说明：该评测集为自建固定模拟输入集，用于度量固定场景下的 Agent 行为、字段解析和追问逻辑表现，不代表生产环境真实准确率。

## Summary

- Mode: current
- Total cases: 100
- Passed: 100
- Failed: 0
- Pass rate: 100.00%
- Intent distribution: {'log_drink': 80, 'ask_advice': 20}
- Action distribution: {'fill_log_form': 60, 'ask_follow_up': 20, 'answer_advice': 20}

## Metrics

- intent_accuracy: 100/100 (100.00%)
- final_action_accuracy: 100/100 (100.00%)
- parsed_field_accuracy: 356/356 (100.00%)
- missing_field_recall: 24/24 (100.00%)

## Baseline vs Current

| Metric | Baseline | Current | Delta |
| --- | --- | --- | --- |
| synthetic_pass_rate | 86/100 (86.00%) | 100/100 (100.00%) | +14.00pp |
| final_action_accuracy | 96/100 (96.00%) | 100/100 (100.00%) | +4.00pp |
| intent_accuracy | 100/100 (100.00%) | 100/100 (100.00%) | +0.00pp |
| missing_field_recall | 24/24 (100.00%) | 24/24 (100.00%) | +0.00pp |
| parsed_field_accuracy | 339/356 (95.22%) | 356/356 (100.00%) | +4.78pp |

## Case Results

| id | intent | action | result | failures |
| --- | --- | --- | --- | --- |
| log_luckin_coconut_latte_large_three | log_drink | fill_log_form | PASS | - |
| log_luckin_coconut_latte_large_half | log_drink | fill_log_form | PASS | - |
| log_cotti_coconut_americano_650_none | log_drink | fill_log_form | PASS | - |
| log_starbucks_americano_500_none | log_drink | fill_log_form | PASS | - |
| log_manner_yuzu_americano_large_three | log_drink | fill_log_form | PASS | - |
| log_moli_orchid_latte_large_half | log_drink | fill_log_form | PASS | - |
| log_classic_milk_tea_500_half | log_drink | fill_log_form | PASS | - |
| log_fruit_tea_500_none | log_drink | fill_log_form | PASS | - |
| log_americano_500_full | log_drink | fill_log_form | PASS | - |
| log_oat_latte_500_half | log_drink | fill_log_form | PASS | - |
| log_coke_can_none | log_drink | fill_log_form | PASS | - |
| log_nayuki_lemon_tea_large_seven | log_drink | fill_log_form | PASS | - |
| log_heytea_yangzhi_large_half | log_drink | fill_log_form | PASS | - |
| log_chabaidao_milk_tea_medium_three | log_drink | fill_log_form | PASS | - |
| log_guming_fruit_tea_large_full | log_drink | fill_log_form | PASS | - |
| log_mixue_lemon_tea_large_none | log_drink | fill_log_form | PASS | - |
| log_pepsi_can_full | log_drink | fill_log_form | PASS | - |
| log_tims_coffee_standard_none | log_drink | fill_log_form | PASS | - |
| log_costa_latte_small_half | log_drink | fill_log_form | PASS | - |
| log_yidiandian_milk_tea_large_seven | log_drink | fill_log_form | PASS | - |
| log_luckin_americano_medium_none | log_drink | fill_log_form | PASS | - |
| log_cotti_latte_small_three | log_drink | fill_log_form | PASS | - |
| log_starbucks_latte_standard_half | log_drink | fill_log_form | PASS | - |
| log_manner_coffee_large_none | log_drink | fill_log_form | PASS | - |
| log_moli_milk_tea_500_seven | log_drink | fill_log_form | PASS | - |
| log_heytea_fruit_tea_650_half | log_drink | fill_log_form | PASS | - |
| log_nayuki_yangzhi_500_full | log_drink | fill_log_form | PASS | - |
| log_chabaidao_lemon_tea_330_none | log_drink | fill_log_form | PASS | - |
| log_guming_milk_tea_250_half | log_drink | fill_log_form | PASS | - |
| log_mixue_fruit_tea_500_three | log_drink | fill_log_form | PASS | - |
| log_coke_500_full | log_drink | fill_log_form | PASS | - |
| log_pepsi_500_none | log_drink | fill_log_form | PASS | - |
| log_tims_latte_500_half | log_drink | fill_log_form | PASS | - |
| log_costa_americano_350_none | log_drink | fill_log_form | PASS | - |
| log_yidiandian_fruit_tea_500_full | log_drink | fill_log_form | PASS | - |
| log_luckin_raw_coconut_latte_650_half | log_drink | fill_log_form | PASS | - |
| log_cotti_americano_500_none | log_drink | fill_log_form | PASS | - |
| log_starbucks_oat_latte_500_three | log_drink | fill_log_form | PASS | - |
| log_manner_latte_250_half | log_drink | fill_log_form | PASS | - |
| log_moli_lemon_tea_500_none | log_drink | fill_log_form | PASS | - |
| log_heytea_milk_tea_330_seven | log_drink | fill_log_form | PASS | - |
| log_nayuki_fruit_tea_650_three | log_drink | fill_log_form | PASS | - |
| log_chabaidao_yangzhi_500_half | log_drink | fill_log_form | PASS | - |
| log_guming_lemon_tea_500_none | log_drink | fill_log_form | PASS | - |
| log_mixue_milk_tea_330_full | log_drink | fill_log_form | PASS | - |
| log_plain_coffee_250_none | log_drink | fill_log_form | PASS | - |
| log_plain_latte_500_half | log_drink | fill_log_form | PASS | - |
| log_plain_lemon_tea_330_three | log_drink | fill_log_form | PASS | - |
| log_plain_milk_tea_650_seven | log_drink | fill_log_form | PASS | - |
| log_plain_fruit_tea_350_none | log_drink | fill_log_form | PASS | - |
| log_plain_coke_330_full | log_drink | fill_log_form | PASS | - |
| log_english_luckin_500_none | log_drink | fill_log_form | PASS | - |
| log_english_cotti_latte_350_half | log_drink | fill_log_form | PASS | - |
| log_mixed_star_latte_500_three | log_drink | fill_log_form | PASS | - |
| log_mixed_manner_americano_250_none | log_drink | fill_log_form | PASS | - |
| log_time_morning_coffee | log_drink | fill_log_form | PASS | - |
| log_time_afternoon_latte | log_drink | fill_log_form | PASS | - |
| log_time_evening_milk_tea | log_drink | fill_log_form | PASS | - |
| log_punctuated_fruit_tea | log_drink | fill_log_form | PASS | - |
| log_punctuated_latte | log_drink | fill_log_form | PASS | - |
| followup_missing_sugar_luckin | log_drink | ask_follow_up | PASS | - |
| followup_missing_volume_and_sugar_milk_tea | log_drink | ask_follow_up | PASS | - |
| followup_missing_volume_fruit_tea | log_drink | ask_follow_up | PASS | - |
| followup_missing_sugar_starbucks | log_drink | ask_follow_up | PASS | - |
| followup_missing_sugar_pepsi | log_drink | ask_follow_up | PASS | - |
| followup_missing_volume_cotti | log_drink | ask_follow_up | PASS | - |
| followup_missing_volume_luckin | log_drink | ask_follow_up | PASS | - |
| followup_missing_sugar_guming | log_drink | ask_follow_up | PASS | - |
| followup_missing_sugar_manner | log_drink | ask_follow_up | PASS | - |
| followup_missing_volume_manner | log_drink | ask_follow_up | PASS | - |
| followup_missing_volume_sugar_coffee | log_drink | ask_follow_up | PASS | - |
| followup_missing_volume_sugar_lemon_tea | log_drink | ask_follow_up | PASS | - |
| followup_missing_sugar_tims | log_drink | ask_follow_up | PASS | - |
| followup_missing_sugar_coke | log_drink | ask_follow_up | PASS | - |
| followup_missing_volume_mixue | log_drink | ask_follow_up | PASS | - |
| followup_missing_sugar_yidiandian | log_drink | ask_follow_up | PASS | - |
| followup_missing_volume_nayuki | log_drink | ask_follow_up | PASS | - |
| followup_missing_sugar_costa | log_drink | ask_follow_up | PASS | - |
| followup_missing_volume_sugar_yangzhi | log_drink | ask_follow_up | PASS | - |
| followup_missing_volume_plain_americano | log_drink | ask_follow_up | PASS | - |
| advice_can_drink_coffee | ask_advice | answer_advice | PASS | - |
| advice_milk_tea_afternoon | ask_advice | answer_advice | PASS | - |
| advice_today_budget | ask_advice | answer_advice | PASS | - |
| advice_recommend_drink | ask_advice | answer_advice | PASS | - |
| advice_symptom_nausea | ask_advice | answer_advice | PASS | - |
| advice_after_three_no_caffeine | ask_advice | answer_advice | PASS | - |
| advice_too_much_sugar | ask_advice | answer_advice | PASS | - |
| advice_low_sugar_choice | ask_advice | answer_advice | PASS | - |
| advice_sleep_sensitive | ask_advice | answer_advice | PASS | - |
| advice_heart_racing | ask_advice | answer_advice | PASS | - |
| advice_healthy_today | ask_advice | answer_advice | PASS | - |
| advice_can_have_soda | ask_advice | answer_advice | PASS | - |
| advice_choose_milk_tea | ask_advice | answer_advice | PASS | - |
| advice_caffeine_budget | ask_advice | answer_advice | PASS | - |
| advice_sugar_budget | ask_advice | answer_advice | PASS | - |
| advice_evening_recommendation | ask_advice | answer_advice | PASS | - |
| advice_after_latte | ask_advice | answer_advice | PASS | - |
| advice_risk_check | ask_advice | answer_advice | PASS | - |
| advice_drink_plan | ask_advice | answer_advice | PASS | - |
| advice_avoid_caffeine | ask_advice | answer_advice | PASS | - |