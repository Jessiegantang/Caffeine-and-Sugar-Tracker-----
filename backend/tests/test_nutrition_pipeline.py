import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from workflows.nutrition_pipeline import estimate_drink_nutrition
from db.database import DrinkKnowledge, SessionLocal
from knowledge import knowledge_lookup


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
            trace_ids = [event["id"] for event in result["explainability"]["graph_trace"]]
            self.assertIn("llm_composition_decompose", trace_ids)
            self.assertIn("composition_estimate", trace_ids)
            self.assertTrue(result["explainability"]["used_composition"])
            self.assertTrue(result["composition"]["components"])
        finally:
            row = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if row:
                db.delete(row)
                db.commit()
            db.close()

    def test_partial_rag_match_uses_rag_field_and_agent_for_missing_field(self):
        class FakeDocument:
            metadata = {
                "id": "rag_partial_1",
                "brand": "UniqueRagBrand",
                "name": "Unique Mango Tea",
                "volume": 500,
                "caffeine": 35,
                "sugar": 0,
                "source": "reviewed:web:caffeine_only",
            }

        class FakeVectorStore:
            def similarity_search_with_score(self, query, k=1):
                return [(FakeDocument(), 0.1)]

        db = SessionLocal()
        try:
            with patch.object(knowledge_lookup, "vectorstore", FakeVectorStore()):
                result = estimate_drink_nutrition({
                    "brand": "UniqueRagBrand",
                    "name": "Unique Mango Tea",
                    "type": "fruittea",
                    "sugar": "none",
                    "volume": 500,
                    "data_source": "user_input",
                }, db)
        finally:
            db.close()

        self.assertEqual(result["caffeine"], 35.0)
        self.assertGreater(result["sugarContent"], 0)
        self.assertEqual(result["estimation_method"], "HYBRID_RAG_MATCH_COMPOSITION")
        self.assertEqual(result["matched_knowledge_id"], "rag_partial_1")
        self.assertTrue(result["explainability"]["used_composition"])

    def test_legacy_zero_sugar_is_missing_and_uses_agent(self):
        db = SessionLocal()
        kb_id = "test_legacy_zero_sugar"
        try:
            existing = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if existing:
                db.delete(existing)
                db.commit()
            db.add(DrinkKnowledge(
                id=kb_id,
                brand="LegacyZeroBrand",
                name="Legacy Zero Latte",
                type="coffee",
                volume=500,
                caffeine=120,
                baseSugar=0,
                source="用户自建知识库",
            ))
            db.commit()

            result = estimate_drink_nutrition({
                "brand": "LegacyZeroBrand",
                "name": "Legacy Zero Latte",
                "type": "coffee",
                "sugar": "none",
                "volume": 500,
                "data_source": "user_input",
            }, db)
        finally:
            row = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
            if row:
                db.delete(row)
                db.commit()
            db.close()

        self.assertEqual(result["caffeine"], 120.0)
        self.assertGreater(result["sugarContent"], 0)
        self.assertEqual(result["estimation_method"], "HYBRID_SQL_EXACT_MATCH_COMPOSITION")
        self.assertTrue(result["explainability"]["used_composition"])


if __name__ == "__main__":
    unittest.main()
