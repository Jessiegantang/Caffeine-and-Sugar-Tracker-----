import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from langchain_core.runnables import RunnableLambda

import agents.memory_extractor_agent as memory_extractor_agent
from services.memory_service import (
    extract_memory_updates,
    infer_memory_updates_from_text,
)
from agents.memory_extractor_agent import MemoryExtractionResult, infer_memory_updates_with_llm


class RaisingLLM:
    def with_structured_output(self, *args, **kwargs):
        raise AssertionError("LLM should not be called when disabled")


class FakeMemoryLLM:
    def __init__(self, result: MemoryExtractionResult):
        self.result = result
        self.called = False

    def with_structured_output(self, *args, **kwargs):
        self.called = True
        return RunnableLambda(lambda _: self.result)


class MemoryServiceTests(unittest.TestCase):
    def test_blood_sugar_health_context_sets_reduce_sugar_goal(self):
        updates = infer_memory_updates_from_text(
            "\u6700\u8fd1\u4f53\u68c0\u8840\u7cd6\u504f\u9ad8\uff0c\u533b\u751f\u8ba9\u6211\u6ce8\u610f\u4e00\u4e0b"
        )

        self.assertEqual(updates["goal"], "reduce_sugar")
        self.assertIn("blood_sugar_attention", updates["health_context"])
        self.assertIn("doctor_advice", updates["health_context"])

    def test_vague_doctor_advice_does_not_create_health_memory(self):
        updates = infer_memory_updates_from_text("\u533b\u751f\u8ba9\u6211\u6ce8\u610f\u4e00\u4e0b")

        self.assertEqual(updates, {})

    def test_caffeine_sensitivity_sets_goal_and_sensitivity(self):
        updates = infer_memory_updates_from_text(
            "\u6211\u559d\u5b8c\u5496\u5561\u5bb9\u6613\u5fc3\u614c\uff0c\u665a\u4e0a\u4e5f\u7761\u4e0d\u7740"
        )

        self.assertEqual(updates["goal"], "reduce_caffeine")
        self.assertEqual(updates["caffeine_sensitivity"], "high")
        self.assertIn("sleep_attention", updates["health_context"])

    def test_preferred_sugar_uses_last_explicit_preference(self):
        updates = infer_memory_updates_from_text(
            "\u6211\u4ee5\u524d\u559d\u4e09\u5206\u7cd6\uff0c\u73b0\u5728\u60f3\u6539\u6210\u534a\u7cd6"
        )

        self.assertEqual(updates["preferred_sugar"], "half")

    def test_extract_memory_updates_combines_parsed_drink_and_semantic_text(self):
        updates = extract_memory_updates(
            "\u6700\u8fd1\u4f53\u68c0\u8840\u7cd6\u504f\u9ad8\uff0c\u8fd9\u676f\u5148\u8bb0\u4e00\u4e0b",
            "log_drink",
            {"brand": "\u745e\u5e78\u5496\u5561", "sugar": "none", "time": "now"},
            None,
        )

        self.assertEqual(updates["goal"], "reduce_sugar")
        self.assertEqual(updates["last_brand_seen"], "\u745e\u5e78\u5496\u5561")
        self.assertEqual(updates["last_sugar_seen"], "none")

    def test_extract_memory_updates_uses_memory_extractor_agent(self):
        with patch("services.memory_service.infer_memory_updates_with_llm", return_value={"goal": "reduce_caffeine"}):
            updates = extract_memory_updates("\u6211\u60f3\u8c03\u6574\u4e00\u4e0b\u996e\u54c1\u4e60\u60ef", "ask_advice", None, None)

        self.assertEqual(updates["goal"], "reduce_caffeine")

    def test_llm_memory_extractor_is_disabled_offline(self):
        with patch.dict(os.environ, {
            "ENABLE_LLM": "false",
            "DRINKMIND_OFFLINE": "true",
            "OPENAI_API_KEY": "real-looking-key",
        }):
            with patch.object(memory_extractor_agent, "llm", RaisingLLM()):
                updates = infer_memory_updates_with_llm("fake message", {})

        self.assertEqual(updates, {})

    def test_llm_memory_extractor_can_add_structured_updates(self):
        fake_llm = FakeMemoryLLM(MemoryExtractionResult(
            updates={
                "goal": "reduce_sugar",
                "health_context": "blood_sugar_attention,doctor_advice",
                "ignored_key": "ignored",
            },
            confidence=0.86,
            reason="blood sugar context",
        ))

        with patch.dict(os.environ, {
            "ENABLE_LLM": "true",
            "DRINKMIND_OFFLINE": "false",
            "OPENAI_API_KEY": "real-looking-key",
        }):
            with patch.object(memory_extractor_agent, "llm", fake_llm):
                updates = infer_memory_updates_with_llm(
                    "\u4f53\u68c0\u6307\u6807\u63d0\u9192\u6211\u8981\u5c11\u559d\u751c\u7684",
                    {},
                )

        self.assertTrue(fake_llm.called)
        self.assertEqual(updates["goal"], "reduce_sugar")
        self.assertEqual(updates["health_context"], "blood_sugar_attention,doctor_advice")
        self.assertNotIn("ignored_key", updates)

    def test_low_confidence_llm_memory_is_ignored(self):
        fake_llm = FakeMemoryLLM(MemoryExtractionResult(
            updates={"goal": "reduce_sugar"},
            confidence=0.3,
            reason="too vague",
        ))

        with patch.dict(os.environ, {
            "ENABLE_LLM": "true",
            "DRINKMIND_OFFLINE": "false",
            "OPENAI_API_KEY": "real-looking-key",
        }):
            with patch.object(memory_extractor_agent, "llm", fake_llm):
                updates = infer_memory_updates_with_llm("\u533b\u751f\u8ba9\u6211\u6ce8\u610f", {})

        self.assertEqual(updates, {})


if __name__ == "__main__":
    unittest.main()
