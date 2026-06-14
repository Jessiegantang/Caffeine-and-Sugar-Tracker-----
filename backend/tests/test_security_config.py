import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import DEFAULT_CORS_ORIGINS, get_cors_origins


class SecurityConfigTests(unittest.TestCase):
    def test_cors_defaults_to_local_frontend_origins(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_cors_origins(), DEFAULT_CORS_ORIGINS)
            self.assertNotIn("*", get_cors_origins())

    def test_cors_origins_can_be_configured(self):
        with patch.dict(os.environ, {
            "CORS_ALLOW_ORIGINS": "https://app.example.com, https://admin.example.com",
        }, clear=False):
            self.assertEqual(get_cors_origins(), [
                "https://app.example.com",
                "https://admin.example.com",
            ])


if __name__ == "__main__":
    unittest.main()
