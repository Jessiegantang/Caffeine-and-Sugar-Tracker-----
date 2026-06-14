import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.run_agent_effect_eval_report import run_report


class AgentEffectEvalTests(unittest.TestCase):
    def test_agent_effect_eval_cases(self):
        report = run_report()
        failures = {
            row["id"]: row["failures"]
            for row in report["rows"]
            if row["failures"]
        }
        self.assertFalse(failures, failures)


if __name__ == "__main__":
    unittest.main()
