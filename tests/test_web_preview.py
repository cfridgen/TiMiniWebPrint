from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from fastapi import HTTPException

from timiniprint.app import web


class WebPreviewTests(unittest.TestCase):
    def test_preview_wraps_unexpected_text_converter_exception(self) -> None:
        request = web.PreviewRequest(text="Hello")

        with patch.object(web, "_resolve_profile_width", return_value=384), patch.object(
            web, "_resolve_profile_dpi", return_value=200
        ), patch.object(web, "_resolve_font_path", return_value=None), patch.object(
            web, "TextConverter"
        ) as converter_cls, patch.object(web, "_debug_event") as debug_event:
            converter_cls.return_value.load.side_effect = RuntimeError("boom")

            with self.assertRaises(HTTPException) as caught:
                web.preview(request)

        self.assertEqual(caught.exception.status_code, 500)
        self.assertEqual(caught.exception.detail, "PREVIEW_UNEXPECTED_ERROR")
        debug_event.assert_any_call("error", "Preview unexpected exception", error="boom", has_image=False)

    def test_preview_supports_legacy_text_converter_signature(self) -> None:
        captured_columns: dict[str, object] = {"value": None}

        class LegacyTextConverter:
            def __init__(self, font_path=None, columns=None, wrap_lines=True):
                self.font_path = font_path
                self.columns = columns
                self.wrap_lines = wrap_lines
                captured_columns["value"] = columns

            def load(self, path: str, width: int):
                with open(path, "r", encoding="utf-8") as handle:
                    _ = handle.read()
                return [SimpleNamespace(image=Image.new("L", (width, 8), 255), dither=False)]

        request = web.PreviewRequest(text="Legacy converter", text_columns=6, font_size_pt=28)
        with patch.object(web, "_resolve_profile_width", return_value=384), patch.object(
            web, "_resolve_profile_dpi", return_value=200
        ), patch.object(web, "_resolve_font_path", return_value=None), patch.object(
            web, "TextConverter", LegacyTextConverter
        ):
            data = web.preview(request)

        self.assertIn("image_data", data)
        self.assertEqual(data["width"], 384)
        self.assertEqual(data["height"], 8)
        self.assertEqual(captured_columns["value"], 6)


if __name__ == "__main__":
    unittest.main()
