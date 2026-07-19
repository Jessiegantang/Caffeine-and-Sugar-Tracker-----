import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rules.composition_agent import (
    decompose_drink,
    estimate_composition_nutrition,
    estimate_from_composition,
)
import rules.llm_composition_decomposer as llm_decomposer
from rules.llm_composition_decomposer import composition_llm_enabled, decompose_with_llm


class CompositionAgentTests(unittest.TestCase):
    def assert_valid_range(self, value, unit):
        self.assertIsInstance(value, dict)
        self.assertEqual(value["unit"], unit)
        self.assertLessEqual(value["min"], value["best"])
        self.assertLessEqual(value["best"], value["max"])

    def test_large_coconut_latte_estimates_espresso_and_coconut_milk(self):
        result = estimate_composition_nutrition({
            "brand": "Luckin",
            "name": "sheng ye coconut latte",
            "type": "coffee",
            "volume": 500,
            "sugar": "three",
        })

        composition = result["composition"]
        self.assertEqual(composition["drink_type"], "coconut_latte")
        self.assertEqual(composition["espresso_shots"], 2.0)
        self.assertEqual(composition["milk_base"], "coconut_milk")
        self.assertGreater(result["caffeine"], 100)
        self.assertGreater(result["sugarContent"], 20)
        self.assert_valid_range(result["caffeine_range"], "mg")
        self.assert_valid_range(result["sugar_range"], "g")
        self.assertEqual(result["caffeine"], result["caffeine_range"]["best"])
        self.assertEqual(result["sugarContent"], result["sugar_range"]["best"])
        self.assertTrue(composition["uncertainty_drivers"])

    def test_americano_has_caffeine_but_near_zero_sugar_when_no_sugar(self):
        result = estimate_composition_nutrition({
            "name": "Americano",
            "type": "coffee",
            "volume": 500,
            "sugar": "none",
        })

        self.assertEqual(result["composition"]["drink_type"], "americano")
        self.assertGreater(result["caffeine"], 100)
        self.assertLessEqual(result["sugarContent"], 1.0)
        self.assert_valid_range(result["sugar_range"], "g")
        self.assertLessEqual(result["sugar_range"]["max"], 2.0)

    def test_orange_americano_uses_generic_fruit_base(self):
        result = estimate_composition_nutrition({
            "brand": "Luckin",
            "name": "orange americano",
            "type": "coffee",
            "volume": 500,
            "sugar": "none",
        })

        composition = result["composition"]
        self.assertEqual(composition["drink_type"], "fruit_americano")
        self.assertEqual(composition["fruit_base"], "fruit_or_juice_base")
        self.assertGreater(result["caffeine"], 100)
        self.assertGreater(result["sugarContent"], 10)

    def test_chinese_mulberry_americano_uses_generic_fruit_base(self):
        result = estimate_composition_nutrition({
            "brand": "Cotti",
            "name": "桑葚美式",
            "type": "coffee",
            "volume": 500,
            "sugar": "none",
        })

        composition = result["composition"]
        self.assertEqual(composition["drink_type"], "fruit_americano")
        self.assertEqual(composition["fruit_base"], "fruit_or_juice_base")
        self.assertGreater(result["sugarContent"], 10)

    def test_latte_includes_milk_natural_sugar(self):
        result = estimate_composition_nutrition({
            "name": "Latte",
            "type": "coffee",
            "volume": 500,
            "sugar": "none",
        })

        milk_components = [
            item for item in result["composition"]["components"]
            if item["category"] == "milk_base"
        ]
        self.assertTrue(milk_components)
        self.assertGreater(result["sugarContent"], 5)
        self.assert_valid_range(milk_components[0]["sugar_range_g"], "g")
        self.assertGreater(milk_components[0]["sugar_range_g"]["min"], 0)

    def test_milk_tea_includes_tea_caffeine_and_added_sugar(self):
        result = estimate_composition_nutrition({
            "name": "classic milk tea",
            "type": "milktea",
            "volume": 500,
            "sugar": "half",
        })

        categories = {item["category"] for item in result["composition"]["components"]}
        self.assertIn("tea_base", categories)
        self.assertIn("sweetener", categories)
        self.assertGreater(result["caffeine"], 50)
        self.assertGreater(result["sugarContent"], 15)

    def test_fruit_tea_includes_fruit_base_sugar(self):
        result = estimate_composition_nutrition({
            "name": "mango fruit tea",
            "type": "fruittea",
            "volume": 500,
            "sugar": "three",
        })

        categories = {item["category"] for item in result["composition"]["components"]}
        self.assertIn("fruit_base", categories)
        self.assertGreater(result["sugarContent"], 20)

    def test_no_sugar_preserves_natural_milk_or_fruit_sugar(self):
        latte = estimate_composition_nutrition({
            "name": "oat latte",
            "type": "coffee",
            "volume": 500,
            "sugar": "none",
        })
        fruit_tea = estimate_composition_nutrition({
            "name": "fruit tea",
            "type": "fruittea",
            "volume": 500,
            "sugar": "none",
        })

        self.assertGreater(latte["sugarContent"], 5)
        self.assertGreater(fruit_tea["sugarContent"], 20)

    def test_unknown_sugar_adds_warning(self):
        unknown = estimate_composition_nutrition({
            "name": "Latte",
            "type": "coffee",
            "volume": 500,
            "sugar": "mystery",
        })

        self.assertTrue(unknown["composition"]["warnings"])

    def test_output_contains_reasoning_and_components(self):
        composition = decompose_drink({
            "name": "milk tea",
            "type": "milktea",
            "volume": 500,
            "sugar": "seven",
        })
        estimate = estimate_from_composition(composition)

        self.assertTrue(estimate["reasoning"])
        self.assertTrue(estimate["components"])
        for component in estimate["components"]:
            self.assertIn("name", component)
            self.assertIn("category", component)
            self.assertIn("amount", component)
            self.assertIn("unit", component)
            self.assertIn("caffeine_mg", component)
            self.assertIn("sugar_g", component)
            self.assertIn("caffeine_range_mg", component)
            self.assertIn("sugar_range_g", component)
            self.assertIn("basis", component)
            self.assert_valid_range(component["caffeine_range_mg"], "mg")
            self.assert_valid_range(component["sugar_range_g"], "g")
        self.assert_valid_range(estimate["caffeine_range"], "mg")
        self.assert_valid_range(estimate["sugar_range"], "g")

    def test_top_level_output_is_compatible_with_nutrition_result_fields(self):
        result = estimate_composition_nutrition({
            "name": "unknown drink",
            "type": "unknown",
            "volume": 500,
            "sugar": "unknown",
        })

        for key in [
            "caffeine",
            "sugarContent",
            "data_source",
            "reasoning",
            "estimation_method",
            "matched_knowledge_id",
            "retrieval_score",
            "composition",
        ]:
            self.assertIn(key, result)
        self.assertIn("caffeine_range", result)
        self.assertIn("sugar_range", result)
        self.assertEqual(result["data_source"], "Composition Estimation Agent")
        self.assertEqual(result["estimation_method"], "COMPOSITION_ESTIMATION")
        self.assertIsNone(result["matched_knowledge_id"])
        self.assertIsNone(result["retrieval_score"])
        self.assertEqual(result["composition"]["drink_type"], "unknown")
        self.assertTrue(result["composition"]["warnings"])
        self.assertGreaterEqual(result["sugar_range"]["max"] - result["sugar_range"]["min"], 10.0)

    def test_llm_composition_decomposer_can_be_disabled(self):
        with patch.dict(os.environ, {"ENABLE_LLM_COMPOSITION": "false"}):
            self.assertFalse(composition_llm_enabled())

    def test_llm_primary_components_are_converted_to_rule_based_nutrition(self):
        llm_result = llm_decomposer.LLMCompositionResult(
            drink_type="milk_tea",
            tea_base="jasmine_tea",
            tea_base_ratio=0.45,
            milk_base="milk",
            milk_ratio=0.35,
            fruit_base="apple_base",
            fruit_ratio=0.15,
            syrup_pumps=0,
            natural_sugar_sources=["milk", "apple_base"],
            assumptions=["用户选择的奶茶类型作为主要约束。"],
        )
        drink = {
            "brand": "Test Brand",
            "name": "茉莉苹果冰奶",
            "type": "milktea",
            "volume": 500,
            "sugar": "none",
        }

        with patch.dict(os.environ, {
            "ENABLE_LLM_COMPOSITION": "true",
            "DRINKMIND_OFFLINE": "false",
            "OPENAI_API_KEY": "real_test_key",
        }), patch.object(llm_decomposer, "_call_llm_decomposer", return_value=llm_result):
            composition = decompose_with_llm(drink)

        estimate = estimate_from_composition(composition)
        self.assertEqual(composition["drink_type"], "milk_tea")
        self.assertEqual(composition["input"]["type"], "milktea")
        self.assertEqual(composition["decomposition_source"], "llm_primary")
        self.assertTrue(composition["llm_decomposition_used"])
        self.assertEqual(composition["tea_base_volume_ml"], 225.0)
        self.assertEqual(composition["milk_volume_ml"], 175.0)
        self.assertEqual(composition["fruit_base_volume_ml"], 75.0)
        self.assertGreater(estimate["caffeine"], 0)
        self.assertGreater(estimate["sugarContent"], 0)


if __name__ == "__main__":
    unittest.main()
