from __future__ import annotations

import inspect
import os
from typing import Dict, List, Optional, Set

from .base import Page, PageConverter
from .image import ImageConverter
from .pdf import PdfConverter
from .text import TextConverter
from ..text_size_policy import resolve_text_size

SUPPORTED_EXTENSIONS: Set[str] = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".pdf", ".txt"}


class PageLoader:
    def __init__(
        self,
        converters: Optional[Dict[str, PageConverter]] = None,
        text_font: Optional[str] = None,
        text_columns: Optional[int] = None,
        text_wrap: bool = True,
        text_preserve_long_lines: bool = False,
        trim_side_margins: bool = True,
        trim_top_bottom_margins: bool = True,
        pdf_pages: Optional[str] = None,
        pdf_page_gap_px: int = 0,
        font_size_pt: Optional[int] = None,
        printer_dpi: int = 200,
    ) -> None:
        if converters is None:
            converters = {}
            image_converter = ImageConverter(
                trim_side_margins=trim_side_margins,
                trim_top_bottom_margins=trim_top_bottom_margins,
            )
            for ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
                converters[ext] = image_converter
            converters[".pdf"] = PdfConverter(
                page_selection=pdf_pages,
                page_gap_px=pdf_page_gap_px,
                trim_side_margins=trim_side_margins,
                trim_top_bottom_margins=trim_top_bottom_margins,
            )
            size = resolve_text_size(font_size_pt=font_size_pt, text_columns=text_columns)
            params = inspect.signature(TextConverter.__init__).parameters
            supports_font_size = "font_size_pt" in params
            candidate_kwargs: Dict[str, object] = {
                "font_path": text_font,
                "columns": None if supports_font_size else size.text_columns,
                "wrap_lines": text_wrap,
                "preserve_long_lines": text_preserve_long_lines,
                "font_size_pt": size.font_size_pt,
                "printer_dpi": printer_dpi,
            }
            supported_kwargs = {name: value for name, value in candidate_kwargs.items() if name in params}
            converters[".txt"] = TextConverter(**supported_kwargs)
        self._converters = converters

    @property
    def supported_extensions(self) -> Set[str]:
        return set(self._converters.keys())

    def load(self, path: str, width: int) -> List[Page]:
        ext = os.path.splitext(path)[1].lower()
        converter = self._converters.get(ext)
        if not converter:
            raise ValueError(f"Unsupported file extension: {ext}")
        return converter.load(path, width)


def load_pages(path: str, width: int) -> List[Page]:
    return PageLoader().load(path, width)


__all__ = ["Page", "PageLoader", "SUPPORTED_EXTENSIONS", "load_pages"]
