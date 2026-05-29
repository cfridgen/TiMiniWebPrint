from __future__ import annotations

from dataclasses import dataclass

DEFAULT_FONT_SIZE_PT = 12
MIN_FONT_SIZE_PT = 4
MAX_FONT_SIZE_PT = 200
MIN_TEXT_COLUMNS = 1
MAX_TEXT_COLUMNS = 120

# Legacy columns model anchor: 12pt approximately matched 15 columns on 58mm labels.
_LEGACY_ANCHOR_PT = 12
_LEGACY_ANCHOR_COLUMNS = 15


@dataclass(frozen=True)
class TextSizeSpec:
    font_size_pt: int
    text_columns: int


def clamp_font_size_pt(value: int | None) -> int:
    if value is None:
        return DEFAULT_FONT_SIZE_PT
    return max(MIN_FONT_SIZE_PT, min(MAX_FONT_SIZE_PT, int(value)))


def clamp_text_columns(value: int | None) -> int:
    if value is None:
        return _LEGACY_ANCHOR_COLUMNS
    return max(MIN_TEXT_COLUMNS, min(MAX_TEXT_COLUMNS, int(value)))


def columns_from_font_size_pt(font_size_pt: int) -> int:
    safe_pt = clamp_font_size_pt(font_size_pt)
    columns = round((_LEGACY_ANCHOR_COLUMNS * _LEGACY_ANCHOR_PT) / safe_pt)
    return clamp_text_columns(columns)


def font_size_pt_from_columns(text_columns: int) -> int:
    safe_columns = clamp_text_columns(text_columns)
    pt = round((_LEGACY_ANCHOR_COLUMNS * _LEGACY_ANCHOR_PT) / safe_columns)
    return clamp_font_size_pt(pt)


def resolve_text_size(font_size_pt: int | None, text_columns: int | None) -> TextSizeSpec:
    if font_size_pt is not None:
        normalized_pt = clamp_font_size_pt(font_size_pt)
        return TextSizeSpec(
            font_size_pt=normalized_pt,
            text_columns=columns_from_font_size_pt(normalized_pt),
        )

    normalized_columns = clamp_text_columns(text_columns)
    return TextSizeSpec(
        font_size_pt=font_size_pt_from_columns(normalized_columns),
        text_columns=normalized_columns,
    )
