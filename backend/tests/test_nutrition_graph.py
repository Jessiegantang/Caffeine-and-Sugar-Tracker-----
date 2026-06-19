import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from workflows import nutrition_pipeline
from workflows.nutrition_pipeline import estimate_drink_nutrition
from db.database import DrinkKnowledge, SessionLocal


class NutritionGraphTests(unittest.TestCase):
    def test_sql_exact_path_uses_knowledge_nodes(self):
        db = SessionLocal()
        kb_id = "test_graph_exact_kb"
        try:
            existing = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if existing:
                db.delete(existing)
                db.commit()

            db.add(DrinkKnowledge(
                id=kb_id,
                brand="GraphExactBrand",
                name="Graph Exact Latte",
                type="coffee",
                volume=500,
                caffeine=120,
                baseSugar=20,
                source="test_fixture",
                confidence=0.95,
            ))
            db.commit()

            result = estimate_drink_nutrition({
                "brand": "GraphExactBrand",
                "name": "Graph Exact Latte",
                "type": "coffee",
                "sugar": "half",
                "volume": 500,
                "data_source": "user_input",
            }, db)
        finally:
            row = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if row:
                db.delete(row)
                db.commit()
            db.close()

        trace = result["explainability"]["graph_trace"]
        trace_ids = [event.get("id") for event in trace]
        self.assertEqual(result["estimation_method"], "SQL_EXACT_MATCH")
        self.assertIsNone(result["composition"])
        self.assertIn("lookup_knowledge", trace_ids)
        self.assertIn("use_knowledge_result", trace_ids)
        self.assertNotIn("composition_decompose", trace_ids)
        self._assert_trace_event_shape(trace)

    def test_no_knowledge_path_uses_composition_nodes(self):
        db = SessionLocal()
        try:
            result = estimate_drink_nutrition({
                "brand": "NoKbGraphBrand",
                "name": "coconut latte",
                "type": "coffee",
                "sugar": "three",
                "volume": 500,
                "data_source": "user_input",
            }, db)
        finally:
            db.close()

        trace = result["explainability"]["graph_trace"]
        trace_ids = [event.get("id") for event in trace]
        self.assertEqual(result["estimation_method"], "COMPOSITION_ESTIMATION")
        self.assertTrue(result["explainability"]["used_composition"])
        self.assertIn("composition_decompose", trace_ids)
        self.assertIn("composition_estimate", trace_ids)
        self.assertIn("verify_result", trace_ids)
        self._assert_trace_event_shape(trace)

    def test_composition_error_falls_back_without_raising(self):
        db = SessionLocal()
        try:
            with patch.object(nutrition_pipeline, "estimate_from_composition", side_effect=RuntimeError("boom")):
                result = estimate_drink_nutrition({
                    "brand": "NoKbGraphErrorBrand",
                    "name": "coconut latte",
                    "type": "coffee",
                    "sugar": "three",
                    "volume": 500,
                    "data_source": "user_input",
                }, db)
        finally:
            db.close()

        trace = result["explainability"]["graph_trace"]
        trace_ids = [event.get("id") for event in trace]
        self.assertNotEqual(result["estimation_method"], "COMPOSITION_ESTIMATION")
        self.assertFalse(result["explainability"]["used_composition"])
        self.assertIn("composition_error", trace_ids)
        self.assertIsNone(result["composition"])

    def test_verify_result_adds_out_of_range_warnings(self):
        high_result = {
            "caffeine": 650,
            "sugarContent": 125,
            "data_source": "test",
            "confidence": 0.9,
            "reasoning": ["test high range"],
            "estimation_method": "SQL_EXACT_MATCH",
            "matched_knowledge_id": "kb_high",
            "retrieval_score": None,
        }

        with patch.object(nutrition_pipeline, "enrich_drink_data", return_value=high_result):
            result = estimate_drink_nutrition({
                "brand": "HighRange",
                "name": "High Range Drink",
                "type": "coffee",
                "sugar": "full",
                "volume": 500,
                "data_source": "user_input",
            }, db=None)

        warnings = result["explainability"]["verification"]["warnings"]
        self.assertIn("caffeine exceeds 500mg", warnings)
        self.assertIn("sugarContent exceeds 100g", warnings)
        self.assertEqual(result["caffeine"], 650.0)
        self.assertEqual(result["sugarContent"], 125.0)

    def test_contract_keys_unchanged(self):
        db = SessionLocal()
        try:
            result = estimate_drink_nutrition({
                "brand": "NoKbContractBrand",
                "name": "americano",
                "type": "coffee",
                "sugar": "none",
                "volume": 500,
                "data_source": "user_input",
            }, db)
        finally:
            db.close()

        expected_keys = {
            "caffeine",
            "sugarContent",
            "data_source",
            "confidence",
            "reasoning",
            "estimation_method",
            "matched_knowledge_id",
            "retrieval_score",
            "composition",
            "explainability",
        }
        self.assertTrue(expected_keys.issubset(result.keys()))

        explainability = result["explainability"]
        expected_explainability_keys = {
            "method",
            "used_composition",
            "used_knowledge_match",
            "matched_knowledge_id",
            "retrieval_score",
            "confidence",
            "reasoning",
            "components",
            "assumptions",
            "warnings",
            "graph_trace",
            "verification",
        }
        self.assertTrue(expected_explainability_keys.issubset(explainability.keys()))
        self._assert_trace_event_shape(explainability["graph_trace"])

    def test_llm_composition_decomposer_updates_complex_drink_when_enabled(self):
        low_confidence_fallback = {
            "caffeine": 0,
            "sugarContent": 0,
            "data_source": "test",
            "confidence": 0.4,
            "reasoning": ["test fallback"],
            "estimation_method": "LOCAL_ESTIMATOR",
            "matched_knowledge_id": None,
            "retrieval_score": None,
        }
        db = SessionLocal()
        try:
            with patch.dict(os.environ, {
                "ENABLE_LLM": "true",
                "ENABLE_LLM_COMPOSITION": "true",
                "DRINKMIND_OFFLINE": "false",
                "OPENAI_API_KEY": "real_test_key",
            }):
                with patch.object(nutrition_pipeline, "enrich_drink_data", return_value=low_confidence_fallback), \
                     patch.object(
                         nutrition_pipeline,
                         "decompose_with_optional_llm",
                         return_value={
                             "drink_type": "mango_coconut_drink",
                             "coffee_base": None,
                             "espresso_shots": 0.0,
                             "tea_base": "light_tea",
                             "tea_base_volume_ml": 75.0,
                             "milk_base": "coconut_milk",
                             "milk_volume_ml": 125.0,
                             "fruit_base": "mango_puree_or_juice_base",
                             "fruit_base_volume_ml": 225.0,
                             "sweetener_type": "syrup",
                             "sweetener_level": "half",
                             "syrup_pumps": 2.0,
                             "natural_sugar_sources": ["mango_puree_or_juice_base", "coconut_milk"],
                             "assumptions": ["LLM inferred mango coconut dessert drink components."],
                             "warnings": ["Sago or toppings are not modeled numerically."],
                             "uncertainty_drivers": ["Brand recipe and topping amount are unknown."],
                             "confidence": 0.58,
                             "input": {
                                 "brand": "",
                                 "name": "杨枝甘露",
                                 "type": "fruittea",
                                 "volume": 500,
                                 "sugar": "half",
                             },
                             "decomposition_source": "llm_assisted",
                             "llm_decomposition_used": True,
                         },
                     ):
                    result = estimate_drink_nutrition({
                        "brand": "Heytea",
                        "name": "杨枝甘露",
                        "type": "fruittea",
                        "sugar": "half",
                        "volume": 500,
                        "data_source": "user_input",
                    }, db)
        finally:
            db.close()

        trace_ids = [event.get("id") for event in result["explainability"]["graph_trace"]]
        self.assertEqual(result["estimation_method"], "COMPOSITION_ESTIMATION")
        self.assertEqual(result["composition"]["drink_type"], "mango_coconut_drink")
        self.assertTrue(result["composition"]["llm_decomposition_used"])
        self.assertIn("llm_composition_decompose", trace_ids)
        component_names = {item["name"] for item in result["composition"]["components"]}
        self.assertIn("coconut_milk", component_names)
        self.assertIn("mango_puree_or_juice_base", component_names)

    def test_llm_composition_failure_keeps_rule_decomposition(self):
        low_confidence_fallback = {
            "caffeine": 0,
            "sugarContent": 0,
            "data_source": "test",
            "confidence": 0.4,
            "reasoning": ["test fallback"],
            "estimation_method": "LOCAL_ESTIMATOR",
            "matched_knowledge_id": None,
            "retrieval_score": None,
        }
        db = SessionLocal()
        try:
            with patch.dict(os.environ, {
                "ENABLE_LLM": "true",
                "ENABLE_LLM_COMPOSITION": "true",
                "DRINKMIND_OFFLINE": "false",
                "OPENAI_API_KEY": "real_test_key",
            }):
                with patch.object(nutrition_pipeline, "enrich_drink_data", return_value=low_confidence_fallback), \
                     patch.object(
                         nutrition_pipeline,
                         "decompose_with_optional_llm",
                         side_effect=RuntimeError("llm boom"),
                     ):
                    result = estimate_drink_nutrition({
                        "brand": "Heytea",
                        "name": "杨枝甘露",
                        "type": "fruittea",
                        "sugar": "half",
                        "volume": 500,
                        "data_source": "user_input",
                    }, db)
        finally:
            db.close()

        trace = result["explainability"]["graph_trace"]
        trace_ids = [event.get("id") for event in trace]
        llm_trace = next(event for event in trace if event.get("id") == "llm_composition_decompose")
        self.assertEqual(result["estimation_method"], "COMPOSITION_ESTIMATION")
        self.assertEqual(result["composition"]["drink_type"], "fruit_tea")
        self.assertIn("llm_composition_decompose", trace_ids)
        self.assertEqual(llm_trace["status"], "warning")
        self.assertIn("LLM composition decomposition did not finish; using rule-based decomposition.", result["explainability"]["warnings"])

    def _assert_trace_event_shape(self, trace):
        self.assertTrue(trace)
        for event in trace:
            self.assertIsInstance(event, dict)
            for key in ["id", "label", "phase", "agent", "status", "summary"]:
                self.assertIn(key, event)


if __name__ == "__main__":
    unittest.main()
