import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents import companion_agent
from agents import intake_parser
from agents import llm_config
from agents import report_agent
import knowledge.knowledge_lookup as knowledge_lookup
from workflows.nutrition_pipeline import estimate_drink_nutrition
from db.database import SessionLocal
from langchain_core.runnables import RunnableLambda


class RaisingLLM:
    def with_structured_output(self, *args, **kwargs):
        raise AssertionError("LLM should not be called when disabled")

    def invoke(self, *args, **kwargs):
        raise AssertionError("LLM should not be called when disabled")


class FakeStructuredLLM:
    def __init__(self):
        self.called = False

    def with_structured_output(self, *args, **kwargs):
        self.called = True
        return RunnableLambda(lambda _: intake_parser.IntakeParseResult(
            intent="log_drink",
            brand="FakeBrand",
            name="Fake Latte",
            type="coffee",
            volume=500,
            sugar="half",
            time="now",
            missing_fields=[],
            follow_up=None,
        ))


def incomplete_local_parse():
    return {
        "intent": "log_drink",
        "brand": "FakeBrand",
        "name": "Fake Latte",
        "type": "coffee",
        "volume": 500,
        "sugar": None,
        "time": "now",
        "missing_fields": ["sugar"],
        "follow_up": "Which sugar level?",
    }


class LLMOfflineControlTests(unittest.TestCase):
    def test_llm_enabled_rules(self):
        cases = [
            (
                {
                    "ENABLE_LLM": "true",
                    "DRINKMIND_OFFLINE": "true",
                    "OPENAI_API_KEY": "real-looking-key",
                },
                False,
            ),
            (
                {
                    "ENABLE_LLM": "true",
                    "DRINKMIND_OFFLINE": "false",
                    "OPENAI_API_KEY": "",
                },
                False,
            ),
            (
                {
                    "ENABLE_LLM": "true",
                    "DRINKMIND_OFFLINE": "false",
                    "OPENAI_API_KEY": "dummy_key_if_none",
                },
                False,
            ),
            (
                {
                    "ENABLE_LLM": "false",
                    "DRINKMIND_OFFLINE": "false",
                    "OPENAI_API_KEY": "real-looking-key",
                },
                False,
            ),
            (
                {
                    "ENABLE_LLM": "true",
                    "DRINKMIND_OFFLINE": "false",
                    "OPENAI_API_KEY": "real-looking-key",
                },
                True,
            ),
        ]

        for env, expected in cases:
            with self.subTest(env=env):
                with patch.dict(os.environ, env, clear=False):
                    self.assertEqual(llm_config.llm_enabled(), expected)

    def test_parse_intake_does_not_call_structured_llm_when_disabled(self):
        with patch.dict(os.environ, {
            "ENABLE_LLM": "false",
            "DRINKMIND_OFFLINE": "true",
            "OPENAI_API_KEY": "real-looking-key",
        }):
            with patch.object(intake_parser, "llm", RaisingLLM()):
                with patch.object(intake_parser, "_parse_intake_locally", return_value=incomplete_local_parse()):
                    result, provider = intake_parser.parse_intake_with_fallback("fake drink")

        self.assertEqual(result["missing_fields"], ["sugar"])
        self.assertEqual(result["follow_up"], "Which sugar level?")
        self.assertEqual(provider, "local_rule_intake")

    def test_report_agent_returns_local_report_without_llm_when_disabled(self):
        logs = [{"name": "Offline Latte", "caffeine": 120, "sugarContent": 12}]
        with patch.dict(os.environ, {
            "ENABLE_LLM": "false",
            "DRINKMIND_OFFLINE": "true",
            "OPENAI_API_KEY": "real-looking-key",
        }):
            with patch.object(report_agent, "llm", RaisingLLM()):
                result = report_agent.generate_health_report(logs, "daily")
                self.assertIn("insights", result)
                self.assertGreater(len(result["insights"]), 0)

    def test_companion_agent_returns_fallback_without_llm_when_disabled(self):
        with patch.dict(os.environ, {
            "ENABLE_LLM": "false",
            "DRINKMIND_OFFLINE": "true",
            "OPENAI_API_KEY": "real-looking-key",
        }):
            with patch.object(companion_agent, "llm", RaisingLLM()):
                response = companion_agent.generate_companion_response("hi", [], {})

        self.assertTrue(response)
        self.assertNotIn("LLM companion is disabled", response)

    def test_enrich_no_knowledge_match_returns_missing_fields_for_graph(self):
        db = SessionLocal()
        try:
            with patch.dict(os.environ, {
                "ENABLE_LLM": "false",
                "DRINKMIND_OFFLINE": "true",
                "OPENAI_API_KEY": "real-looking-key",
            }):
                with patch.object(knowledge_lookup, "vectorstore", None):
                    with patch("builtins.print") as mocked_print:
                        result = knowledge_lookup.enrich_drink_data({
                            "brand": "NoKbOfflineBrand",
                            "name": "Offline Test Latte",
                            "type": "coffee",
                            "sugar": "three",
                            "volume": 500,
                            "data_source": "user_input",
                        }, db)
        finally:
            db.close()

        self.assertEqual(result["estimation_method"], "NO_KNOWLEDGE_MATCH")
        self.assertIsNone(result["caffeine"])
        self.assertIsNone(result["sugarContent"])
        printed = "\n".join(str(call.args[0]) for call in mocked_print.call_args_list if call.args)
        self.assertNotIn("AI Estimation Error", printed)
        self.assertNotIn("tool_choice", printed)

    def test_nutrition_pipeline_still_uses_composition_when_llm_disabled(self):
        db = SessionLocal()
        try:
            with patch.dict(os.environ, {
                "ENABLE_LLM": "false",
                "DRINKMIND_OFFLINE": "true",
                "OPENAI_API_KEY": "real-looking-key",
            }):
                with patch.object(knowledge_lookup, "vectorstore", None):
                    result = estimate_drink_nutrition({
                        "brand": "NoKbCompositionOfflineBrand",
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
        self.assertTrue(result["composition"]["components"])

    def test_parse_intake_can_enter_llm_path_when_explicitly_enabled(self):
        fake_llm = FakeStructuredLLM()
        with patch.dict(os.environ, {
            "ENABLE_LLM": "true",
            "DRINKMIND_OFFLINE": "false",
            "OPENAI_API_KEY": "real-looking-key",
        }):
            with patch.object(intake_parser, "llm", fake_llm):
                with patch.object(intake_parser, "_parse_intake_locally") as local_parser:
                    result, provider = intake_parser.parse_intake_with_fallback("fake drink")

        self.assertTrue(fake_llm.called)
        local_parser.assert_not_called()
        self.assertEqual(provider, "llm_intake_agent")
        self.assertEqual(result["sugar"], "half")
        self.assertEqual(result["missing_fields"], [])

    def test_parse_intake_uses_rules_only_after_llm_failure(self):
        local_result = incomplete_local_parse()
        with patch.dict(os.environ, {
            "ENABLE_LLM": "true",
            "DRINKMIND_OFFLINE": "false",
            "OPENAI_API_KEY": "real-looking-key",
        }):
            with patch.object(intake_parser, "llm", RaisingLLM()):
                with patch.object(intake_parser, "_parse_intake_locally", return_value=local_result) as local_parser:
                    result, provider = intake_parser.parse_intake_with_fallback("fake drink")

        local_parser.assert_called_once_with("fake drink")
        self.assertEqual(provider, "local_rule_intake")
        self.assertEqual(result, local_result)


if __name__ == "__main__":
    unittest.main()
