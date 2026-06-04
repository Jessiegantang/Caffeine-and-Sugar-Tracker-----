import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent import parse_intake_message
from agents.orchestrator import run_agent_orchestrator
from database import SessionLocal


class IntakeParserTests(unittest.TestCase):
    def test_parse_complete_drink_sentence(self):
        result = parse_intake_message("我刚喝了一杯瑞幸生椰拿铁，大杯，三分糖。")

        self.assertEqual(result["intent"], "log_drink")
        self.assertEqual(result["brand"], "瑞幸咖啡")
        self.assertEqual(result["name"], "生椰拿铁")
        self.assertEqual(result["volume"], 500)
        self.assertEqual(result["sugar"], "three")
        self.assertEqual(result["missing_fields"], [])

    def test_parse_missing_sugar_asks_follow_up(self):
        result = parse_intake_message("我刚喝了一杯瑞幸生椰拿铁，大杯。")

        self.assertEqual(result["intent"], "log_drink")
        self.assertIn("sugar", result["missing_fields"])
        self.assertTrue(result["follow_up"])

    def test_orchestrator_routes_advice_question(self):
        db = SessionLocal()
        try:
            state = run_agent_orchestrator("我现在还能喝咖啡吗", "2026-06-04", db)
        finally:
            db.close()

        self.assertEqual(state["intent"], "ask_advice")
        self.assertEqual(state["final_action"], "answer_advice")
        self.assertIn("risk_result", state)


if __name__ == "__main__":
    unittest.main()
