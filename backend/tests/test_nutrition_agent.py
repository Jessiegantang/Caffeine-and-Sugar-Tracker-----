import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent import enrich_drink_data
from agents.health_plan_agent import build_plan_days, infer_plan_target
from database import DrinkKnowledge, SessionLocal
from local_estimator import estimate_nutrition


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

    def test_health_plan_is_structured_for_seven_days(self):
        target = infer_plan_target("我想一周内减少奶茶糖分")
        plan = build_plan_days(target)

        self.assertEqual(target, "reduce_sugar")
        self.assertEqual(len(plan), 7)
        self.assertEqual(set(plan[0].keys()), {"day", "goal", "suggestion", "status"})


if __name__ == "__main__":
    unittest.main()
