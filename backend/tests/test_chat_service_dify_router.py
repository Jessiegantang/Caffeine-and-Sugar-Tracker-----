import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient

import main
from db.database import AgentTrace, ChatLog, SessionLocal
from services.dify_companion_service import DifyCompanionError


class DifyFirstChatRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def _cleanup_date(self, date: str) -> None:
        db = SessionLocal()
        try:
            trace_ids = [
                row.id
                for row in db.query(AgentTrace).filter(AgentTrace.user_input.in_([
                    "帮我记录一杯瑞幸生椰拿铁。",
                    "大杯，三分糖。",
                    "帮我记录一杯星巴克大杯拿铁，三分糖。",
                ])).all()
            ]
            db.query(ChatLog).filter(ChatLog.date == date).delete(synchronize_session=False)
            if trace_ids:
                db.query(AgentTrace).filter(AgentTrace.id.in_(trace_ids)).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def test_dify_follow_up_then_complete_form_uses_local_chat_history(self):
        date = "2099-02-01"
        first_turn = {
            "response_type": "chat_message",
            "text": "你喝的是小杯、中杯还是大杯？也可以告诉我大概多少毫升。",
            "parsed_intake": None,
            "provider": "dify",
            "fallback_reason": None,
        }
        second_turn = {
            "response_type": "drink_form",
            "text": "我已经整理好饮品信息，请确认后添加到当天记录。",
            "parsed_intake": {
                "intent": "log_drink",
                "brand": "瑞幸咖啡",
                "name": "生椰拿铁",
                "type": "coffee",
                "volume": 500,
                "sugar": "three",
                "time": "now",
                "confidence": 0.9,
                "missing_fields": [],
                "follow_up": None,
            },
            "provider": "dify",
            "fallback_reason": None,
        }
        try:
            with patch("services.chat_service.dify_available", return_value=True), \
                    patch("services.chat_service.generate_dify_turn", side_effect=[first_turn, second_turn]) as generate, \
                    patch("services.chat_service.extract_memory_updates", return_value={}):
                first = self.client.post("/api/chat", json={
                    "date": date,
                    "message": "帮我记录一杯瑞幸生椰拿铁。",
                })
                second = self.client.post("/api/chat", json={
                    "date": date,
                    "message": "大杯，三分糖。",
                })

            self.assertEqual(first.status_code, 200)
            self.assertIsNone(first.json()["parsed_intake"])
            self.assertEqual(second.status_code, 200)
            self.assertEqual(second.json()["parsed_intake"]["name"], "生椰拿铁")
            self.assertEqual(second.json()["parsed_intake"]["volume"], 500)
            second_history = generate.call_args_list[1].args[1]
            self.assertEqual(second_history[0]["role"], "user")
            self.assertIn("瑞幸生椰拿铁", second_history[0]["content"])
            self.assertEqual(second_history[1]["role"], "assistant")
            self.assertIn("多少毫升", second_history[1]["content"])
        finally:
            self._cleanup_date(date)

    def test_dify_failure_restores_complete_local_intake_route(self):
        date = "2099-02-02"
        try:
            with patch("services.chat_service.dify_available", return_value=True), \
                    patch(
                        "services.chat_service.generate_dify_turn",
                        side_effect=DifyCompanionError("timeout"),
                    ), \
                    patch("services.chat_service.extract_memory_updates", return_value={}):
                response = self.client.post("/api/chat", json={
                    "date": date,
                    "message": "帮我记录一杯星巴克大杯拿铁，三分糖。",
                })

            self.assertEqual(response.status_code, 200)
            parsed = response.json()["parsed_intake"]
            self.assertEqual(parsed["intent"], "log_drink")
            self.assertEqual(parsed["volume"], 500)
            self.assertEqual(parsed["sugar"], "three")
        finally:
            self._cleanup_date(date)


if __name__ == "__main__":
    unittest.main()
