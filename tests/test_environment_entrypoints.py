from __future__ import annotations

import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


_ROOT = Path(__file__).resolve().parents[1]


class EnvironmentEntrypointTests(unittest.TestCase):
    def test_command_line_entrypoint_delegates_to_cli_main(self) -> None:
        path = _ROOT / "timiniprint_command_line.py"
        with patch("timiniprint.app.cli.main", return_value=7) as main_mock:
            with self.assertRaises(SystemExit) as cm:
                runpy.run_path(str(path), run_name="__main__")
        self.assertEqual(cm.exception.code, 7)
        self.assertEqual(main_mock.call_count, 1)

    def test_module_entrypoint_delegates_to_cli_main(self) -> None:
        with patch("timiniprint.app.cli.main", return_value=11) as main_mock:
            with self.assertRaises(SystemExit) as cm:
                runpy.run_module("timiniprint", run_name="__main__")
        self.assertEqual(cm.exception.code, 11)
        self.assertEqual(main_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
