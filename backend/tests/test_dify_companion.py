import os
import sys
import unittest
from unittest.mock import Mock, patch

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services import dify_companion_service


class DifyCompanionTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "today_caffeine_mg": 285,
            "today_sugar_g": 32,
            "last_night_sleep_hours": 5.5,
            "user_preferences": {"goal": "reduce_sugar"},
        }
        self.history = [{"role": "user", "content": "昨晚没睡好"}]
        self.dify_env = {
            "COMPANION_PROVIDER": "dify",
            "DIFY_BASE_URL": "https://api.dify.ai/v1",
            "DIFY_API_KEY": "test-secret-key",
            "DIFY_USER_ID": "test-user",
            "DIFY_TIMEOUT_SECONDS": "30",
            "DRINKMIND_OFFLINE": "false",
        }

    def test_dify_response_uses_expected_context_without_exposing_key(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"answer": "建议今天选择低咖啡因、低糖饮品。"}

        with patch.dict(os.environ, self.dify_env, clear=False):
            with patch.object(dify_companion_service.httpx, "post", return_value=response) as post:
                result = dify_companion_service.generate_companion_response(
                    "我还能喝咖啡吗？",
                    self.history,
                    self.context,
                )

        self.assertEqual(result["provider"], "dify")
        self.assertIsNone(result["fallback_reason"])
        self.assertIn("低咖啡因", result["text"])
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["query"], "我还能喝咖啡吗？")
        self.assertEqual(payload["inputs"]["today_caffeine_mg"], 285.0)
        self.assertEqual(payload["inputs"]["sleep_hours"], 5.5)
        self.assertIn("昨晚没睡好", payload["inputs"]["recent_history"])
        self.assertNotIn("test-secret-key", str(result))

    def test_timeout_falls_back_to_local_companion(self):
        with patch.dict(os.environ, self.dify_env, clear=False):
            with patch.object(
                dify_companion_service.httpx,
                "post",
                side_effect=httpx.ReadTimeout("timeout"),
            ):
                result = dify_companion_service.generate_companion_response(
                    "我还能喝咖啡吗？",
                    self.history,
                    self.context,
                )

        self.assertEqual(result["provider"], "local")
        self.assertEqual(result["fallback_reason"], "timeout")
        self.assertTrue(result["text"])

    def test_offline_mode_never_calls_dify(self):
        env = {**self.dify_env, "DRINKMIND_OFFLINE": "true"}
        with patch.dict(os.environ, env, clear=False):
            with patch.object(dify_companion_service.httpx, "post") as post:
                result = dify_companion_service.generate_companion_response(
                    "推荐一杯饮品",
                    [],
                    self.context,
                )

        post.assert_not_called()
        self.assertEqual(result["provider"], "local")
        self.assertIsNone(result["fallback_reason"])

    def test_missing_sleep_is_omitted_instead_of_becoming_zero_hours(self):
        inputs = dify_companion_service._build_inputs([], {
            "today_caffeine_mg": 0,
            "today_sugar_g": 0,
            "last_night_sleep_hours": "未知",
            "user_preferences": {},
        })

        self.assertNotIn("sleep_hours", inputs)

    def test_drink_form_answer_is_converted_to_local_parsed_intake(self):
        answer = """[DRINK_FORM]
{
  "intent": "log_drink",
  "message": "我已经整理好饮品信息，请确认后添加到当天记录。",
  "drink": {
    "brand": "瑞幸咖啡",
    "name": "生椰拿铁",
    "type": "coffee",
    "volume": 500,
    "sugar": "three",
    "time": "now"
  },
  "missing_fields": []
}
"""

        result = dify_companion_service.parse_dify_answer(answer)

        self.assertEqual(result["response_type"], "drink_form")
        self.assertEqual(result["parsed_intake"]["intent"], "log_drink")
        self.assertEqual(result["parsed_intake"]["name"], "生椰拿铁")
        self.assertEqual(result["parsed_intake"]["volume"], 500)
        self.assertEqual(result["parsed_intake"]["sugar"], "three")
        self.assertNotIn("[DRINK_FORM]", result["text"])

    def test_invalid_drink_form_is_rejected_before_frontend_fill(self):
        answer = """[DRINK_FORM]
{"intent":"log_drink","drink":{"name":"测试饮品","type":"coffee","volume":500,"sugar":"sometimes","time":"now"}}
"""

        with self.assertRaises(dify_companion_service.DifyCompanionError) as raised:
            dify_companion_service.parse_dify_answer(answer)

        self.assertEqual(raised.exception.code, "invalid_drink_form_sugar")


if __name__ == "__main__":
    unittest.main()
