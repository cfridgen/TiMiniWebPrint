from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import timiniprint_web


class WebEntrypointTests(unittest.TestCase):
    def test_uvicorn_kwargs_disable_stdout_logging_for_container_mode(self) -> None:
        env = {
            "APP_ADDR": "0.0.0.0",
            "APP_PORT": "8000",
            "TIMINIPRINT_RELOAD": "0",
            "TIMINIPRINT_LOG_LEVEL": "info",
            "TIMINIPRINT_LOG_TO_STDOUT": "0",
            "TIMINIPRINT_ACCESS_LOG": "0",
        }
        with patch.dict(os.environ, env, clear=False):
            kwargs = timiniprint_web._uvicorn_kwargs()

        self.assertEqual(kwargs["host"], "0.0.0.0")
        self.assertEqual(kwargs["port"], 8000)
        self.assertEqual(kwargs["log_level"], "info")
        self.assertFalse(kwargs["reload"])
        self.assertFalse(kwargs["access_log"])
        self.assertIsNone(kwargs["log_config"])


if __name__ == "__main__":
    unittest.main()