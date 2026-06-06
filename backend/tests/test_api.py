import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["OPENAI_API_KEY"] = "dummy_test_key"
os.environ["ENABLE_TEXT_EXTRACTION_LLM"] = "false"

from fastapi.testclient import TestClient

import main
from database import HealthPlan, SessionLocal


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def tearDown(self):
        db = SessionLocal()
        try:
            for plan in db.query(HealthPlan).filter(HealthPlan.id.like("plan_%")).all():
                if plan.target in {"reduce_sugar", "reduce_caffeine", "work_week_strategy", "balanced_drink_routine"}:
                    db.delete(plan)
            db.commit()
        finally:
            db.close()
        self.client.delete("/api/user/preferences")

    def test_parse_intake_api_returns_structured_json(self):
        response = self.client.post("/api/agent/parse_intake", json={
            "date": "2026-06-04",
            "message": "我刚喝了一杯瑞幸生椰拿铁，大杯，三分糖。",
        })

        self.assertEqual(response.status_code, 200)
        parsed = response.json()["parsed_intake"]
        self.assertEqual(parsed["intent"], "log_drink")
        self.assertEqual(parsed["sugar"], "three")

    def test_agent_act_records_trace(self):
        response = self.client.post("/api/agent/act", json={
            "date": "2026-06-04",
            "message": "我现在还能喝咖啡吗",
        })

        self.assertEqual(response.status_code, 200)
        trace_id = response.json()["agent_state"]["trace_id"]
        traces = self.client.get("/api/agent/traces?limit=5").json()["traces"]
        self.assertTrue(any(trace["id"] == trace_id for trace in traces))

    def test_memory_preferences_can_be_written_and_cleared(self):
        response = self.client.post("/api/agent/act", json={
            "date": "2026-06-04",
            "message": "我想少喝糖，刚喝了一杯瑞幸生椰拿铁，大杯，三分糖。",
        })
        self.assertEqual(response.status_code, 200)

        preferences = self.client.get("/api/user/preferences").json()["preferences"]
        self.assertEqual(preferences["goal"], "reduce_sugar")
        self.assertEqual(preferences["preferred_sugar"], "three")

        clear_response = self.client.delete("/api/user/preferences")
        self.assertEqual(clear_response.status_code, 200)
        self.assertEqual(self.client.get("/api/user/preferences").json()["preferences"], {})

    def test_health_plan_api_creates_and_updates_plan(self):
        response = self.client.post("/api/health/plans", json={
            "date": "2026-06-04",
            "goal": "我想一周内减少奶茶糖分",
        })

        self.assertEqual(response.status_code, 200)
        plan = response.json()["plan"]
        self.assertEqual(plan["target"], "reduce_sugar")
        self.assertEqual(len(plan["plan_content"]), 7)

        progress = self.client.post("/api/health/plans/active/progress?date=2026-06-06").json()["plan"]
        self.assertEqual(progress["current_day"], 3)


if __name__ == "__main__":
    unittest.main()
