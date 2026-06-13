import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.health_plan_agent import build_plan_days, infer_plan_target
from agents.nutrition_agent import estimate_from_parsed_drink
from agents.orchestrator import run_agent_orchestrator
from db.database import DrinkKnowledge, SessionLocal
from knowledge.knowledge_lookup import enrich_drink_data
from rules.local_estimator import estimate_nutrition


class NutritionAgentTests(unittest.TestCase):
    def test_local_estimator_fallback_returns_numbers(self):
        result = estimate_nutrition("Unknown", "Test Coffee", "coffee", 500, "three")

        self.assertGreaterEqual(result["caffeine"], 0)
        self.assertGreaterEqual(result["sugar"], 0)
        self.assertEqual(result["source"], "Local Estimator (Dynamic DB)")
        self.assertTrue(result["reasoning"])

    def test_sql_exact_match_adds_explainability_fields(self):
        db = SessionLocal()
        kb_id = "test_exact_match_kb"
        try:
            existing = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if existing:
                db.delete(existing)
                db.commit()

            db.add(DrinkKnowledge(
                id=kb_id,
                brand="TestBrand",
                name="Exact Latte",
                type="coffee",
                volume=500,
                caffeine=120,
                baseSugar=20,
                source="test_fixture",
                confidence=0.99,
            ))
            db.commit()

            result = enrich_drink_data({
                "brand": "TestBrand",
                "name": "Exact Latte",
                "type": "coffee",
                "sugar": "half",
                "volume": 500,
                "data_source": "用户录入",
            }, db)

            self.assertEqual(result["estimation_method"], "SQL_EXACT_MATCH")
            self.assertEqual(result["matched_knowledge_id"], kb_id)
            self.assertEqual(result["confidence"], 0.99)
        finally:
            row = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if row:
                db.delete(row)
                db.commit()
            db.close()

    def test_partial_sql_match_uses_hybrid_estimation(self):
        db = SessionLocal()
        kb_id = "test_partial_match_kb"
        try:
            existing = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if existing:
                db.delete(existing)
                db.commit()

            db.add(DrinkKnowledge(
                id=kb_id,
                brand="TestBrand",
                name="Partial Latte",
                type="coffee",
                volume=500,
                caffeine=150,
                baseSugar=0,
                source="reviewed:image_upload:caffeine_only",
                confidence=0.72,
            ))
            db.commit()

            result = enrich_drink_data({
                "brand": "TestBrand",
                "name": "Partial Latte",
                "type": "coffee",
                "sugar": "none",
                "volume": 650,
                "data_source": "用户录入",
            }, db)

            self.assertTrue(result["estimation_method"].startswith("HYBRID_SQL_EXACT_MATCH"))
            self.assertEqual(result["matched_knowledge_id"], kb_id)
            self.assertEqual(result["caffeine"], 195.0)
            self.assertGreaterEqual(result["sugarContent"], 0)
        finally:
            row = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if row:
                db.delete(row)
                db.commit()
            db.close()

    def test_sql_match_allows_minor_name_suffix(self):
        db = SessionLocal()
        kb_id = "test_suffix_match_kb"
        try:
            existing = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if existing:
                db.delete(existing)
                db.commit()

            db.add(DrinkKnowledge(
                id=kb_id,
                brand="TestBrand",
                name="Velvet Latte",
                type="coffee",
                volume=500,
                caffeine=140,
                baseSugar=0,
                source="reviewed:image_upload:caffeine_only",
                confidence=0.72,
            ))
            db.commit()

            result = enrich_drink_data({
                "brand": "TestBrand",
                "name": "Velvet Latte Coffee",
                "type": "coffee",
                "sugar": "none",
                "volume": 500,
            }, db)

            self.assertEqual(result["matched_knowledge_id"], kb_id)
            self.assertEqual(result["caffeine"], 140.0)
            self.assertTrue(result["estimation_method"].startswith("HYBRID_SQL_EXACT_MATCH"))
        finally:
            row = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if row:
                db.delete(row)
                db.commit()
            db.close()

    def test_sql_match_allows_brand_alias(self):
        db = SessionLocal()
        kb_id = "test_brand_alias_match_kb"
        try:
            existing = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if existing:
                db.delete(existing)
                db.commit()

            db.add(DrinkKnowledge(
                id=kb_id,
                brand="luckin coffee",
                name="Test Alias Cappuccino",
                type="coffee",
                volume=450,
                caffeine=150,
                baseSugar=0,
                source="reviewed:image_upload:caffeine_only",
                confidence=0.72,
            ))
            db.commit()

            result = enrich_drink_data({
                "brand": "瑞幸咖啡",
                "name": "Test Alias Cappuccino",
                "type": "coffee",
                "sugar": "none",
                "volume": 500,
            }, db)

            self.assertEqual(result["matched_knowledge_id"], kb_id)
            self.assertTrue(result["estimation_method"].startswith("HYBRID_SQL_EXACT_MATCH"))
            self.assertEqual(result["caffeine"], 166.7)
        finally:
            row = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if row:
                db.delete(row)
                db.commit()
            db.close()

    def test_nutrition_agent_uses_composition_when_no_knowledge_match(self):
        db = SessionLocal()
        try:
            result = estimate_from_parsed_drink({
                "brand": "NoKbBrand",
                "name": "coconut latte",
                "type": "coffee",
                "sugar": "three",
                "volume": 500,
                "confidence": 0.9,
            }, "2026-06-04", db)
        finally:
            db.close()

        self.assertEqual(result["estimation_method"], "COMPOSITION_ESTIMATION")
        self.assertEqual(result["data_source"], "Composition Estimation Agent")
        self.assertIn("composition", result)
        self.assertTrue(result["composition"]["components"])
        self.assertTrue(result["reasoning"])

    def test_nutrition_agent_keeps_sql_exact_match(self):
        db = SessionLocal()
        kb_id = "test_nutrition_agent_exact_kb"
        try:
            existing = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if existing:
                db.delete(existing)
                db.commit()

            db.add(DrinkKnowledge(
                id=kb_id,
                brand="ExactCompositionBrand",
                name="Exact Composition Latte",
                type="coffee",
                volume=500,
                caffeine=123,
                baseSugar=22,
                source="test_fixture",
                confidence=0.98,
            ))
            db.commit()

            result = estimate_from_parsed_drink({
                "brand": "ExactCompositionBrand",
                "name": "Exact Composition Latte",
                "type": "coffee",
                "sugar": "half",
                "volume": 500,
                "confidence": 0.9,
            }, "2026-06-04", db)

            self.assertEqual(result["estimation_method"], "SQL_EXACT_MATCH")
            self.assertEqual(result["matched_knowledge_id"], kb_id)
            self.assertIsNone(result["composition"])
            self.assertTrue(result["explainability"]["used_knowledge_match"])
        finally:
            row = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if row:
                db.delete(row)
                db.commit()
            db.close()

    def test_orchestrator_tools_used_contains_composition_estimation(self):
        db = SessionLocal()
        try:
            state = run_agent_orchestrator(
                "我刚喝了一杯coconut-latte，大杯，三分糖。",
                "2026-06-04",
                db,
            )
        finally:
            db.close()

        self.assertEqual(state["final_action"], "fill_log_form")
        self.assertEqual(state["nutrition_result"]["estimation_method"], "COMPOSITION_ESTIMATION")
        self.assertIn("COMPOSITION_ESTIMATION", state["tools_used"])

    def test_health_plan_is_structured_for_seven_days(self):
        target = infer_plan_target("我想一周内减少奶茶糖分")
        plan = build_plan_days(target)

        self.assertEqual(target, "reduce_sugar")
        self.assertEqual(len(plan), 7)
        self.assertEqual(set(plan[0].keys()), {"day", "goal", "suggestion", "status"})


if __name__ == "__main__":
    unittest.main()
