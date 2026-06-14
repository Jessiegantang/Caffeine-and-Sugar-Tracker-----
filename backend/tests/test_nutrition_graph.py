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

    def _assert_trace_event_shape(self, trace):
        self.assertTrue(trace)
        for event in trace:
            self.assertIsInstance(event, dict)
            for key in ["id", "label", "phase", "agent", "status", "summary"]:
                self.assertIn(key, event)


if __name__ == "__main__":
    unittest.main()
