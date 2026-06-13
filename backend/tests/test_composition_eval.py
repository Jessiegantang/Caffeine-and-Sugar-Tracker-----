import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import knowledge.knowledge_lookup as knowledge_lookup
import knowledge.rag_store as rag_store
from workflows.nutrition_pipeline import estimate_drink_nutrition
from db.database import DrinkKnowledge, SessionLocal


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "composition_eval_cases.json"


class DisabledLLM:
    def with_structured_output(self, *args, **kwargs):
        raise RuntimeError("LLM disabled for deterministic composition eval")


class CompositionEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_lookup_vectorstore = knowledge_lookup.vectorstore
        cls.original_rag_retriever = rag_store.retriever
        cls.original_llm = knowledge_lookup.llm
        knowledge_lookup.vectorstore = None
        rag_store.retriever = None
        knowledge_lookup.llm = DisabledLLM()
        with FIXTURE_PATH.open("r", encoding="utf-8") as f:
            cls.cases = json.load(f)

    @classmethod
    def tearDownClass(cls):
        knowledge_lookup.vectorstore = cls.original_lookup_vectorstore
        rag_store.retriever = cls.original_rag_retriever
        knowledge_lookup.llm = cls.original_llm

    def tearDown(self):
        db = SessionLocal()
        try:
            ids = [
                case.get("setup_knowledge", {}).get("id")
                for case in self.cases
                if case.get("setup_knowledge", {}).get("id")
            ]
            if ids:
                for row in db.query(DrinkKnowledge).filter(DrinkKnowledge.id.in_(ids)).all():
                    db.delete(row)
                db.commit()
        finally:
            db.close()

    def test_composition_eval_cases(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                db = SessionLocal()
                try:
                    self._seed_knowledge(db, case.get("setup_knowledge"))
                    result = estimate_drink_nutrition(case["input"], db)
                finally:
                    db.close()

                expected = case["expected"]
                explainability = result.get("explainability") or {}
                composition = result.get("composition") or {}
                components = composition.get("components") or explainability.get("components") or []
                component_names = {component.get("name") for component in components}

                self.assertEqual(result.get("estimation_method"), expected["method"])
                self.assertEqual(explainability.get("used_composition"), expected["used_composition"])
                if "used_knowledge_match" in expected:
                    self.assertEqual(explainability.get("used_knowledge_match"), expected["used_knowledge_match"])
                if expected.get("drink_type") is not None:
                    self.assertEqual(composition.get("drink_type"), expected["drink_type"])
                    self.assertTrue(composition.get("uncertainty_drivers"))
                else:
                    self.assertIsNone(result.get("composition"))

                for component_name in expected.get("required_components", []):
                    self.assertIn(component_name, component_names)

                caffeine_min, caffeine_max = expected["caffeine_range"]
                sugar_min, sugar_max = expected["sugar_range"]
                self.assertGreaterEqual(result.get("caffeine"), caffeine_min)
                self.assertLessEqual(result.get("caffeine"), caffeine_max)
                self.assertGreaterEqual(result.get("sugarContent"), sugar_min)
                self.assertLessEqual(result.get("sugarContent"), sugar_max)
                self.assertGreaterEqual(result.get("confidence"), expected["min_confidence"])
                self.assertIsInstance(result.get("reasoning"), list)
                self.assertIn("explainability", result)
                if expected["used_composition"]:
                    self.assertTrue(components)
                    for component in components:
                        self._assert_valid_range(component.get("caffeine_range_mg"), "mg")
                        self._assert_valid_range(component.get("sugar_range_g"), "g")

    def _seed_knowledge(self, db, payload):
        if not payload:
            return
        existing = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == payload["id"]).first()
        if existing:
            db.delete(existing)
            db.commit()
        db.add(DrinkKnowledge(**payload))
        db.commit()

    def _assert_valid_range(self, value, unit):
        self.assertIsInstance(value, dict)
        self.assertEqual(value.get("unit"), unit)
        self.assertLessEqual(value.get("min"), value.get("best"))
        self.assertLessEqual(value.get("best"), value.get("max"))


if __name__ == "__main__":
    unittest.main()
