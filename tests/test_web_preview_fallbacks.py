from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from timiniprint.app import web


class WebPreviewFallbackTests(unittest.TestCase):
    def test_resolve_font_path_uses_default_bundled_font(self) -> None:
        expected_path = web.FONT_DIR / "RobotoMono-Variable.ttf"
        with patch.object(Path, "exists", return_value=True):
            resolved = web._resolve_font_path(None, None)
        self.assertEqual(resolved, str(expected_path))

    def test_profile_width_prefers_active_printer_profile(self) -> None:
        class _Profile:
            def __init__(self, width: int) -> None:
                self.width = width

        class _Catalog:
            def __init__(self) -> None:
                self.profiles = [_Profile(384), _Profile(2592)]

            def get_profile(self, key: str):
                if key == "active":
                    return _Profile(384)
                return None

        with patch.object(web.PrinterCatalog, "load", return_value=_Catalog()), patch.object(
            web, "_active_printer", {"profile_key": "active"}
        ):
            width = web._resolve_profile_width(None)

        self.assertEqual(width, 384)

    def test_profile_width_defaults_to_384_class_when_unselected(self) -> None:
        class _Profile:
            def __init__(self, width: int, dpi: int = 200) -> None:
                self.width = width
                self.dev_dpi = dpi

        class _Catalog:
            def __init__(self) -> None:
                self.profiles = [_Profile(2592, 300), _Profile(384, 203), _Profile(576, 200)]

            def get_profile(self, _key: str):
                return None

        with patch.object(web.PrinterCatalog, "load", return_value=_Catalog()), patch.object(web, "_active_printer", None):
            width = web._resolve_profile_width(None)
            dpi = web._resolve_profile_dpi(None)

        self.assertEqual(width, 384)
        self.assertEqual(dpi, 203)


if __name__ == "__main__":
    unittest.main()
