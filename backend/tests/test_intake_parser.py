import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.intake_parser import parse_intake_message
from agents.orchestrator import run_agent_orchestrator
from db.database import SessionLocal


class IntakeParserTests(unittest.TestCase):
    def test_parse_complete_drink_sentence(self):
        result = parse_intake_message("\u6211\u521a\u559d\u4e86\u4e00\u676f\u745e\u5e78\u751f\u6930\u62ff\u94c1\uff0c\u5927\u676f\uff0c\u4e09\u5206\u7cd6\u3002")

        self.assertEqual(result["intent"], "log_drink")
        self.assertEqual(result["brand"], "\u745e\u5e78\u5496\u5561")
        self.assertEqual(result["name"], "\u751f\u6930\u62ff\u94c1")
        self.assertEqual(result["volume"], 500)
        self.assertEqual(result["sugar"], "three")
        self.assertEqual(result["missing_fields"], [])

    def test_parse_missing_sugar_asks_follow_up(self):
        result = parse_intake_message("\u6211\u521a\u559d\u4e86\u4e00\u676f\u745e\u5e78\u751f\u6930\u62ff\u94c1\uff0c\u5927\u676f\u3002")

        self.assertEqual(result["intent"], "log_drink")
        self.assertIn("sugar", result["missing_fields"])
        self.assertTrue(result["follow_up"])

    def test_new_brand_alias_can_be_recognized(self):
        result = parse_intake_message("\u6211\u521a\u559d\u4e86\u4e00\u676f\u8309\u8389\u5976\u767d\u7684\u767d\u5170\u62ff\u94c1\uff0c\u5927\u676f\uff0c\u534a\u7cd6")

        self.assertEqual(result["brand"], "\u8309\u8389\u5976\u767d")
        self.assertEqual(result["name"], "\u767d\u5170\u62ff\u94c1")
        self.assertEqual(result["volume"], 500)
        self.assertEqual(result["sugar"], "half")

    def test_name_extraction_ignores_fillers(self):
        result = parse_intake_message("\u6211\u521a\u559d\u4e86\u745e\u5e78\u7684\u90a3\u4e2a\u6930\u5b50\u62ff\u94c1\u5927\u676f\u4e09\u5206\u7cd6")

        self.assertEqual(result["brand"], "\u745e\u5e78\u5496\u5561")
        self.assertEqual(result["name"], "\u6930\u5b50\u62ff\u94c1")
        self.assertEqual(result["sugar"], "three")

    def test_sugar_negation_uses_actual_choice(self):
        result = parse_intake_message("\u6211\u559d\u4e86\u4e00\u676f\u745e\u5e78\u751f\u6930\u62ff\u94c1\u5927\u676f\uff0c\u4e0d\u662f\u5168\u7cd6\u662f\u534a\u7cd6")

        self.assertEqual(result["sugar"], "half")

    def test_symptom_message_routes_to_advice_not_logging(self):
        result = parse_intake_message("\u6211\u4eca\u5929\u8fd9\u676f\u751f\u6930\u7f8e\u5f0f\u559d\u5f97\u6709\u70b9\u4e45\uff0c\u4e00\u76f4\u60f3\u5e72\u5455")

        self.assertEqual(result["intent"], "ask_advice")
        self.assertEqual(result["missing_fields"], [])

    def test_manner_americano_brand_and_name(self):
        result = parse_intake_message("\u521a\u559d\u4e86 Manner \u67da\u5b50\u7f8e\u5f0f \u5927\u676f \u4e09\u5206\u7cd6")

        self.assertEqual(result["brand"], "Manner Coffee")
        self.assertEqual(result["name"], "\u67da\u5b50\u7f8e\u5f0f")
        self.assertEqual(result["type"], "coffee")

    def test_orchestrator_routes_advice_question(self):
        db = SessionLocal()
        try:
            state = run_agent_orchestrator("\u6211\u73b0\u5728\u8fd8\u80fd\u559d\u5496\u5561\u5417\uff1f", "2026-06-04", db)
        finally:
            db.close()

        self.assertEqual(state["intent"], "ask_advice")
        self.assertEqual(state["final_action"], "answer_advice")
        self.assertIn("risk_result", state)
        self.assertNotIn("Based on", state["final_response"])

    def test_orchestrator_log_response_is_chinese(self):
        db = SessionLocal()
        try:
            state = run_agent_orchestrator(
                "\u6211\u521a\u559d\u4e86\u4e00\u676f\u745e\u5e78\u751f\u6930\u62ff\u94c1\uff0c\u5927\u676f\uff0c\u4e09\u5206\u7cd6\u3002",
                "2026-06-04",
                db,
            )
        finally:
            db.close()

        self.assertEqual(state["intent"], "log_drink")
        self.assertEqual(state["final_action"], "fill_log_form")
        self.assertIn("\u5df2\u8bc6\u522b", state["final_response"])
        self.assertIn("\u4f30\u7b97\u5496\u5561\u56e0", state["final_response"])


if __name__ == "__main__":
    unittest.main()
