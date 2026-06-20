import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from workflows.nutrition_pipeline import estimate_drink_nutrition
from db.database import DrinkKnowledge, SessionLocal


class NutritionPipelineTests(unittest.TestCase):
    def test_sql_exact_match_has_knowledge_explainability(self):
        db = SessionLocal()
        kb_id = "test_pipeline_exact_kb"
        try:
            existing = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if existing:
                db.delete(existing)
                db.commit()

            db.add(DrinkKnowledge(
                id=kb_id,
                brand="PipelineExactBrand",
                name="Pipeline Exact Latte",
                type="coffee",
                volume=500,
                caffeine=111,
                baseSugar=18,
                source="test_fixture",
                confidence=0.97,
            ))
            db.commit()

            result = estimate_drink_nutrition({
                "brand": "PipelineExactBrand",
                "name": "Pipeline Exact Latte",
                "type": "coffee",
                "sugar": "half",
                "volume": 500,
                "data_source": "user_input",
            }, db)

            self.assertEqual(result["estimation_method"], "SQL_EXACT_MATCH")
            self.assertIsNone(result["composition"])
            self.assertTrue(result["explainability"]["used_knowledge_match"])
            self.assertFalse(result["explainability"]["used_composition"])
            self.assertEqual(result["explainability"]["matched_knowledge_id"], kb_id)
            self.assertIsInstance(result["reasoning"], list)
        finally:
            row = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if row:
                db.delete(row)
                db.commit()
            db.close()

    def test_no_knowledge_match_uses_composition_contract(self):
        db = SessionLocal()
        try:
            result = estimate_drink_nutrition({
                "brand": "NoKbPipelineBrand",
                "name": "coconut latte",
                "type": "coffee",
                "sugar": "three",
                "volume": 500,
                "data_source": "user_input",
            }, db)
        finally:
            db.close()

        self.assertEqual(result["estimation_method"], "COMPOSITION_ESTIMATION")
        self.assertTrue(result["explainability"]["used_composition"])
        self.assertFalse(result["explainability"]["used_knowledge_match"])
        self.assertTrue(result["explainability"]["components"])
        self.assertIsInstance(result["reasoning"], list)

    def test_caffeine_only_knowledge_uses_composition_for_missing_sugar(self):
        db = SessionLocal()
        kb_id = "test_pipeline_caffeine_only_matcha"
        try:
            existing = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if existing:
                db.delete(existing)
                db.commit()

            db.add(DrinkKnowledge(
                id=kb_id,
                brand="PipelineCaffeineOnlyBrand",
                name="Pipeline Matcha Latte",
                type="coffee",
                volume=450,
                caffeine=45,
                baseSugar=0,
                source="reviewed:image_upload:caffeine_only",
                confidence=0.64,
            ))
            db.commit()

            result = estimate_drink_nutrition({
                "brand": "PipelineCaffeineOnlyBrand",
                "name": "Pipeline Matcha Latte",
                "type": "coffee",
                "sugar": "none",
                "volume": 500,
                "data_source": "user_input",
            }, db)

            self.assertEqual(result["matched_knowledge_id"], kb_id)
            self.assertEqual(result["caffeine"], 50.0)
            self.assertGreater(result["sugarContent"], 0)
            self.assertEqual(result["estimation_method"], "HYBRID_SQL_EXACT_MATCH_COMPOSITION")
        finally:
            row = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if row:
                db.delete(row)
                db.commit()
            db.close()


if __name__ == "__main__":
    unittest.main()
