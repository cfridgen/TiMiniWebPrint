from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from timiniprint.app import web


class WebLoggingTests(unittest.TestCase):
    def test_configure_file_logging_uses_dedicated_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            web_log = log_dir / "webserver.log"
            access_log = log_dir / "access.log"

            with patch.object(web, "LOG_DIR", log_dir), patch.object(web, "WEB_LOG_PATH", web_log), patch.object(
                web, "ACCESS_LOG_PATH", access_log
            ):
                for logger_name in ("timiniprint.web", "timiniprint.access", "uvicorn.error", "uvicorn.access"):
                    logger = logging.getLogger(logger_name)
                    logger.handlers.clear()
                    logger.propagate = True

                web._configure_file_logging()

                app_logger = logging.getLogger("timiniprint.web")
                request_logger = logging.getLogger("timiniprint.access")
                error_logger = logging.getLogger("uvicorn.error")
                access_logger = logging.getLogger("uvicorn.access")

                self.assertFalse(app_logger.propagate)
                self.assertFalse(request_logger.propagate)
                self.assertFalse(error_logger.propagate)
                self.assertFalse(access_logger.propagate)
                self.assertEqual(len(app_logger.handlers), 1)
                self.assertEqual(len(request_logger.handlers), 1)
                self.assertEqual(len(error_logger.handlers), 1)
                self.assertEqual(len(access_logger.handlers), 1)
                self.assertEqual(Path(app_logger.handlers[0].baseFilename), web_log)
                self.assertEqual(Path(request_logger.handlers[0].baseFilename), access_log)
                self.assertEqual(Path(error_logger.handlers[0].baseFilename), web_log)
                self.assertEqual(Path(access_logger.handlers[0].baseFilename), access_log)


if __name__ == "__main__":
    unittest.main()
