from __future__ import annotations

import unittest

from timiniprint.rendering.text_size_policy import (
    columns_from_font_size_pt,
    font_size_pt_from_columns,
    resolve_text_size,
)


class TextSizePolicyTests(unittest.TestCase):
    def test_columns_decrease_when_pt_increases(self) -> None:
        self.assertGreater(columns_from_font_size_pt(8), columns_from_font_size_pt(28))

    def test_resolve_prefers_font_size_pt_when_provided(self) -> None:
        size = resolve_text_size(font_size_pt=28, text_columns=20)
        self.assertEqual(size.font_size_pt, 28)
        self.assertEqual(size.text_columns, columns_from_font_size_pt(28))

    def test_resolve_uses_columns_when_pt_missing(self) -> None:
        size = resolve_text_size(font_size_pt=None, text_columns=12)
        self.assertEqual(size.text_columns, 12)
        self.assertEqual(size.font_size_pt, font_size_pt_from_columns(12))


if __name__ == "__main__":
    unittest.main()
