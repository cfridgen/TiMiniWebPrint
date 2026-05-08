from __future__ import annotations

import argparse
import asyncio
import base64
import io
import logging
import tempfile
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import reporting
from ..devices import PrinterCatalog
from ..rendering.converters.text import TextConverter
from ..transport.bluetooth import BleakBluetoothConnector, BluetoothDiscovery
from . import cli as cli_app

app = FastAPI(title="TiMini Web Print", version="0.1.0")
WEB_STATIC_DIR = Path(__file__).with_name("web_static")
FONT_DIR = WEB_STATIC_DIR / "fonts"
FONT_CATALOG: dict[str, dict[str, str]] = {
    "inter_variable": {
        "label": "Inter",
        "family": "sans",
        "width": "variable",
        "filename": "Inter-Variable.ttf",
        "css_family": "WebFontInter",
    },
    "noto_sans_variable": {
        "label": "Noto Sans",
        "family": "sans",
        "width": "variable",
        "filename": "NotoSans-Variable.ttf",
        "css_family": "WebFontNotoSans",
    },
    "noto_serif_variable": {
        "label": "Noto Serif",
        "family": "serif",
        "width": "variable",
        "filename": "NotoSerif-Variable.ttf",
        "css_family": "WebFontNotoSerif",
    },
    "source_serif4_variable": {
        "label": "Source Serif 4",
        "family": "serif",
        "width": "variable",
        "filename": "SourceSerif4-Variable.ttf",
        "css_family": "WebFontSourceSerif4",
    },
    "roboto_mono_variable": {
        "label": "Roboto Mono",
        "family": "sans",
        "width": "fixed",
        "filename": "RobotoMono-Variable.ttf",
        "css_family": "WebFontRobotoMono",
    },
    "ibm_plex_mono": {
        "label": "IBM Plex Mono",
        "family": "sans",
        "width": "fixed",
        "filename": "IBMPlexMono-Regular.ttf",
        "css_family": "WebFontIBMPlexMono",
    },
    "courier_prime": {
        "label": "Courier Prime",
        "family": "serif",
        "width": "fixed",
        "filename": "CourierPrime-Regular.ttf",
        "css_family": "WebFontCourierPrime",
    },
    "cutive_mono": {
        "label": "Cutive Mono",
        "family": "serif",
        "width": "fixed",
        "filename": "CutiveMono-Regular.ttf",
        "css_family": "WebFontCutiveMono",
    },
    "material_symbols_outlined": {
        "label": "Material Symbols Outlined",
        "family": "sans",
        "width": "variable",
        "filename": "MaterialSymbolsOutlined-Variable.ttf",
        "css_family": "WebFontMaterialSymbolsOutlined",
    },
    "noto_sans_symbols2": {
        "label": "Noto Sans Symbols 2",
        "family": "sans",
        "width": "variable",
        "filename": "NotoSansSymbols2-Regular.ttf",
        "css_family": "WebFontNotoSansSymbols2",
    },
}
DEFAULT_FONT_KEY = "roboto_mono_variable"

app.mount("/static", StaticFiles(directory=WEB_STATIC_DIR), name="static")
logger = logging.getLogger("timiniprint.web")
_active_printer: dict[str, str] | None = None
_debug_events: deque[dict[str, object]] = deque(maxlen=300)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _debug_event(kind: str, message: str, **context: object) -> None:
    entry: dict[str, object] = {
        "ts": _now_iso(),
        "kind": kind,
        "message": message,
    }
    if context:
        entry["context"] = context
    _debug_events.append(entry)


@app.middleware("http")
async def log_http_requests(request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - started) * 1000
        _debug_event(
            "error",
            "Unhandled HTTP exception",
            method=request.method,
            path=request.url.path,
            duration_ms=round(duration_ms, 1),
        )
        logger.exception("HTTP %s %s -> 500 in %.1fms", request.method, request.url.path, duration_ms)
        raise
    duration_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "HTTP %s %s -> %s in %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    if request.url.path != "/api/preview" or response.status_code >= 400:
        _debug_event(
            "http",
            "HTTP request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 1),
        )
    return response


class PreviewRequest(BaseModel):
    text: str = Field(default="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    profile_key: str | None = None
    text_columns: int = Field(default=15, ge=1, le=120)
    text_font: str | None = None
    text_font_key: str | None = None


class PrintRequest(BaseModel):
    text: str = Field(default="")
    bluetooth: str | None = None
    serial: str | None = None
    device_config: str | None = None
    text_columns: int = Field(default=15, ge=1, le=120)
    text_font: str | None = None
    text_font_key: str | None = None
    darkness: int = Field(default=3, ge=1, le=5)
    image_data: str | None = None


class ConnectRequest(BaseModel):
    target: str = Field(min_length=1)


def _normalize_width(width: int) -> int:
    if width % 8 == 0:
        return width
    return width - (width % 8)


def _resolve_profile_width(profile_key: str | None) -> int:
    catalog = PrinterCatalog.load()
    if profile_key:
        profile = catalog.get_profile(profile_key)
        if profile is None:
            raise HTTPException(status_code=400, detail=f"Unknown profile '{profile_key}'")
        return _normalize_width(profile.width)
    profiles = catalog.profiles
    if not profiles:
        raise HTTPException(status_code=500, detail="No printer profiles available")
    widest = max(profiles, key=lambda profile: profile.width)
    return _normalize_width(widest.width)


def _resolve_font_path(text_font_key: str | None, text_font_path: str | None) -> str | None:
    if text_font_key:
        meta = FONT_CATALOG.get(text_font_key)
        if not meta:
            raise HTTPException(status_code=400, detail=f"Unknown text font key '{text_font_key}'")
        path = FONT_DIR / meta["filename"]
        if not path.exists():
            raise HTTPException(status_code=500, detail=f"Bundled font missing: {meta['filename']}")
        return str(path)
    return text_font_path


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html>
<html>
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
    <title>TiMini Web Print</title>
    <link rel=\"icon\" type=\"image/svg+xml\" href=\"/static/favicon.svg\" />
    <style>
        @font-face { font-family: \"WebFontInter\"; src: url(\"/static/fonts/Inter-Variable.ttf\") format(\"truetype\"); }
        @font-face { font-family: \"WebFontNotoSans\"; src: url(\"/static/fonts/NotoSans-Variable.ttf\") format(\"truetype\"); }
        @font-face { font-family: \"WebFontNotoSerif\"; src: url(\"/static/fonts/NotoSerif-Variable.ttf\") format(\"truetype\"); }
        @font-face { font-family: \"WebFontSourceSerif4\"; src: url(\"/static/fonts/SourceSerif4-Variable.ttf\") format(\"truetype\"); }
        @font-face { font-family: \"WebFontRobotoMono\"; src: url(\"/static/fonts/RobotoMono-Variable.ttf\") format(\"truetype\"); }
        @font-face { font-family: \"WebFontIBMPlexMono\"; src: url(\"/static/fonts/IBMPlexMono-Regular.ttf\") format(\"truetype\"); }
        @font-face { font-family: \"WebFontCourierPrime\"; src: url(\"/static/fonts/CourierPrime-Regular.ttf\") format(\"truetype\"); }
        @font-face { font-family: \"WebFontCutiveMono\"; src: url(\"/static/fonts/CutiveMono-Regular.ttf\") format(\"truetype\"); }
        @font-face { font-family: \"WebFontMaterialSymbolsOutlined\"; src: url(\"/static/fonts/MaterialSymbolsOutlined-Variable.ttf\") format(\"truetype\"); }
        @font-face { font-family: \"WebFontNotoSansSymbols2\"; src: url(\"/static/fonts/NotoSansSymbols2-Regular.ttf\") format(\"truetype\"); }

        :root {
            --bg-top: #f3f7ff;
            --bg-bottom: #dfeeff;
            --surface: rgba(255,255,255,0.9);
            --surface-strong: #ffffff;
            --surface-muted: #eef4fb;
            --line: #d7e2ee;
            --line-strong: #b9cadf;
            --text: #18324b;
            --muted: #5f7286;
            --primary: #1473e6;
            --primary-strong: #0f5cc0;
            --accent: #00a86b;
            --accent-strong: #008f5b;
            --shadow: 0 20px 48px rgba(31, 68, 112, 0.14);
        }

        * { box-sizing: border-box; }
        body {
            font-family: "WebFontInter", "Segoe UI", sans-serif;
            margin: 0;
            min-height: 100vh;
            color: var(--text);
            background:
                radial-gradient(circle at top left, rgba(255,255,255,0.85), transparent 28%),
                linear-gradient(180deg, var(--bg-top), var(--bg-bottom));
        }
        h1 { margin: 0 0 6px; font-size: 30px; letter-spacing: -0.03em; }
        p { margin: 0; color: var(--muted); }
        .row { max-width: 1100px; margin: 0 auto; padding: 28px 20px 36px; }
        .card {
            border: 1px solid rgba(255,255,255,0.7);
            border-radius: 28px;
            padding: 24px;
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(247,251,255,0.92));
            box-shadow: var(--shadow);
            backdrop-filter: blur(12px);
        }
        .hero {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            margin-bottom: 20px;
        }
        .section { margin-top: 18px; }
        .section:first-child { margin-top: 0; }
        .section-card {
            padding: 16px 18px 18px;
            border-radius: 20px;
            background: var(--surface);
            border: 1px solid var(--line);
        }
        label { display: block; font-size: 12px; margin-bottom: 6px; font-weight: 700; letter-spacing: 0.02em; color: var(--muted); text-transform: uppercase; }
        textarea, input, select, button { width: 100%; margin-bottom: 8px; }
        textarea, input, select {
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 12px 14px;
            background: var(--surface-strong);
            color: var(--text);
            font: inherit;
            transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
        }
        textarea:focus, input:focus, select:focus {
            outline: none;
            border-color: rgba(20, 115, 230, 0.5);
            box-shadow: 0 0 0 4px rgba(20, 115, 230, 0.12);
        }
        textarea { min-height: 130px; resize: vertical; }
        button {
            border: 0;
            border-radius: 16px;
            padding: 12px 16px;
            background: linear-gradient(180deg, #eef4fb, #dfeaf6);
            color: var(--text);
            font: inherit;
            font-weight: 700;
            cursor: pointer;
            transition: transform 0.16s ease, box-shadow 0.16s ease, filter 0.16s ease;
            box-shadow: 0 8px 18px rgba(19, 39, 62, 0.08);
        }
        button:hover { transform: translateY(-1px); filter: brightness(1.01); }
        button:active { transform: translateY(0); }
        button:disabled {
            cursor: not-allowed;
            opacity: 0.55;
            filter: saturate(0.7);
            transform: none;
            box-shadow: none;
        }

        .device-row { display: grid; grid-template-columns: 1fr auto auto auto; gap: 8px; align-items: center; }
        .device-row select { margin-bottom: 0; }
        .device-row button { width: auto; margin-bottom: 0; }
        .connect-indicator { width: 20px; height: 20px; border: 2.5px solid #d3dbe4; border-top-color: #0a84ff; border-radius: 50%; opacity: 0; transition: opacity 0.2s ease; }
        .connect-indicator.is-active { opacity: 1; animation: spin 0.8s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        /* Busy overlay */
        #busyOverlay { position: fixed; inset: 0; z-index: 9999; background: rgba(180,195,210,0.25); display: flex; align-items: center; justify-content: center; opacity: 0; pointer-events: none; transition: opacity 0.2s ease; }
        #busyOverlay.is-active { opacity: 1; pointer-events: all; }
        #busyOverlay.is-force-hidden { opacity: 0; pointer-events: none; }
        .busy-card { display: flex; flex-direction: column; align-items: center; gap: 14px; background: rgba(255,255,255,0.92); border: 1px solid var(--line); border-radius: 18px; padding: 28px 36px; box-shadow: 0 8px 32px rgba(20,48,80,0.13); }
        .busy-spinner { width: 36px; height: 36px; border: 3.5px solid #d3dbe4; border-top-color: #0a84ff; border-radius: 50%; animation: spin 0.9s linear infinite; }
        #busyMessage { color: #13273e; font-size: 14px; font-weight: 600; }
        .busy-actions { display: flex; gap: 10px; }
        .busy-action { width: auto; margin: 0; min-height: 34px; padding: 6px 14px; border-radius: 10px; font-size: 12px; font-weight: 600; }
        #busyHideBtn { background: #eef3f8; color: #37516b; border: 1px solid #d3deea; }
        #busyCancelBtn { background: #fff1f0; color: #b42318; border: 1px solid #f7c8c4; }
        .busy-action.is-hidden { display: none; }

        .slider-row { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: center; }
        .slider-hint { font-size: 12px; color: #5f6b77; }
        .checkbox-row { display: inline-flex; align-items: center; gap: 10px; font-size: 14px; font-weight: 600; color: var(--text); text-transform: none; letter-spacing: 0; }
        .checkbox-row input { width: 18px; height: 18px; margin: 0; accent-color: var(--primary); }
        .actions { display: grid; grid-template-columns: minmax(0, 1fr) minmax(220px, 0.95fr); gap: 12px; align-items: stretch; }
        .actions button { margin-bottom: 0; min-height: 56px; }
        #previewBtn { background: linear-gradient(180deg, #eef5ff, #dce9ff); color: var(--primary-strong); }
        #printBtn {
            background: linear-gradient(135deg, var(--accent), #15c77c);
            color: #ffffff;
            box-shadow: 0 16px 28px rgba(0, 168, 107, 0.3);
            font-size: 17px;
            letter-spacing: 0.01em;
        }
        #refreshBtn, #fontSizeBtn, #fontBtn, #fontSizeCancelBtn, #fontCancelBtn { background: linear-gradient(180deg, #f4f7fb, #e5edf6); }
        #connectBtn, #fontSizeOkBtn, #fontOkBtn { background: linear-gradient(180deg, #e6f1ff, #cfe2ff); color: var(--primary-strong); }

        .preview-wrapper { position: relative; }
        .preview-area { display: flex; gap: 14px; align-items: flex-start; }
        #previewFrame { width: 420px; min-width: 420px; min-height: 160px; border: 1px solid var(--line-strong); border-radius: 24px; overflow: hidden; display: flex; flex-direction: row; align-items: stretch; flex-shrink: 0; box-shadow: inset 0 1px 0 rgba(255,255,255,0.7), 0 14px 26px rgba(30, 54, 87, 0.12); }
        .carrier-strip { width: 20px; flex-shrink: 0; background-color: #d4d4d4; background-image: repeating-linear-gradient(0deg, rgba(255,255,255,0) 0, rgba(255,255,255,0) 6px, rgba(0,0,0,0.08) 6px, rgba(0,0,0,0.08) 7px); }
        .label-area { flex: 1; background: linear-gradient(180deg, #ffffff, #f8fbff); display: flex; align-items: center; justify-content: center; }
        #preview { max-width: 100%; visibility: hidden; }
        #preview.is-visible { visibility: visible; }
        .preview-side-actions { position: relative; display: flex; flex-direction: column; gap: 10px; min-width: 136px; }
        .preview-side-actions button { width: auto; margin-bottom: 0; white-space: nowrap; padding: 12px 14px; }
        .preview-actions { margin-top: 14px; }
        .side-overlay { position: absolute; left: 0; top: calc(100% + 10px); z-index: 200; background: rgba(255,255,255,0.96); border: 1px solid var(--line); border-radius: 20px; padding: 16px; box-shadow: 0 22px 40px rgba(20, 48, 80, 0.2); backdrop-filter: blur(14px); }
        .side-overlay.is-hidden { display: none; }
        .overlay-title { font-size: 14px; font-weight: 700; color: #13273e; margin-bottom: 12px; }
        .overlay-footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
        .overlay-footer button { width: auto; margin-bottom: 0; }
        #fontSizeOverlay { min-width: 260px; }
        #fontOverlay { left: calc(100% + 12px); top: calc(100% + 10px); min-width: 420px; width: 420px; max-height: 430px; overflow-y: auto; overflow-x: hidden; }

        .status-hub { position: relative; display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
        #statusHistoryBtn {
            width: 34px;
            min-height: 34px;
            margin: 0;
            padding: 0;
            border-radius: 50%;
            font-size: 16px;
            line-height: 1;
            background: linear-gradient(180deg, #e6f1ff, #cfe2ff);
            color: var(--primary-strong);
        }
        #debugLogBtn {
            width: auto;
            min-height: 34px;
            margin: 0;
            padding: 0 12px;
            border-radius: 10px;
            font-size: 12px;
            background: linear-gradient(180deg, #edf7f2, #d9efe3);
            color: #0b6e47;
        }
        .status-history-panel {
            position: absolute;
            right: 0;
            top: calc(100% + 10px);
            z-index: 220;
            width: 280px;
            border: 1px solid var(--line);
            border-radius: 16px;
            background: rgba(255,255,255,0.98);
            box-shadow: 0 18px 36px rgba(19, 39, 62, 0.18);
            padding: 10px 12px;
        }
        .status-history-panel.is-hidden { display: none; }
        .status-history-title { font-size: 12px; font-weight: 700; color: #3d4a58; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.03em; }
        .status-history-list { margin: 0; padding: 0; list-style: none; display: grid; gap: 6px; }
        .status-history-list li { font-size: 12px; color: #334a60; background: #f4f8fd; border: 1px solid #dbe7f3; border-radius: 10px; padding: 6px 8px; }
        .debug-log-panel {
            position: absolute;
            right: 0;
            top: calc(100% + 10px);
            z-index: 230;
            width: min(92vw, 620px);
            border: 1px solid var(--line);
            border-radius: 16px;
            background: rgba(255,255,255,0.98);
            box-shadow: 0 18px 36px rgba(19, 39, 62, 0.18);
            padding: 10px 12px;
        }
        .debug-log-panel.is-hidden { display: none; }
        .debug-log-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
        .debug-log-head .status-history-title { margin-bottom: 0; }
        .debug-log-actions { display: flex; gap: 6px; }
        .debug-log-actions button { width: auto; min-height: 30px; margin: 0; border-radius: 10px; padding: 4px 10px; font-size: 12px; }
        #debugRefreshBtn { background: linear-gradient(180deg, #eef4fb, #dfeaf6); }
        #debugClearBtn { background: linear-gradient(180deg, #fff2f1, #ffe2df); color: #a12a1f; }
        #debugLogMeta { margin-bottom: 8px; font-size: 12px; color: #5a6e82; }
        .debug-log-list { margin: 0; padding: 0; list-style: none; display: grid; gap: 6px; max-height: 42vh; overflow: auto; }
        .debug-log-list li {
            font-family: "WebFontRobotoMono", "WebFontIBMPlexMono", monospace;
            font-size: 11px;
            line-height: 1.35;
            color: #17324c;
            background: #f6faff;
            border: 1px solid #dbe7f3;
            border-radius: 10px;
            padding: 7px 8px;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .status-toast {
            position: fixed;
            top: 14px;
            left: 50%;
            transform: translateX(-50%) translateY(-10px);
            opacity: 0;
            pointer-events: none;
            z-index: 300;
            background: rgba(15, 34, 56, 0.94);
            color: #f5f8fc;
            border-radius: 12px;
            padding: 8px 12px;
            font-size: 13px;
            box-shadow: 0 14px 28px rgba(0, 0, 0, 0.22);
            transition: opacity 0.18s ease, transform 0.18s ease;
            max-width: min(90vw, 620px);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .status-toast.is-visible {
            opacity: 1;
            transform: translateX(-50%) translateY(0);
        }

        #connectionState { font-size: 12px; color: #4d5966; margin-top: 2px; }
        #connectionState.is-scanning { color: #0a84ff; }
        #connectionState.is-connected { color: #117a37; font-weight: 600; }
        #connectionState.is-error { color: #b42318; font-weight: 600; }

        .font-summary { align-self: stretch; display: flex; flex-direction: column; align-items: center; text-align: center; padding: 4px 2px 0; }
        #fontLabel { font-size: 14px; font-weight: 700; color: #13273e; margin-bottom: 0; line-height: 1.2; }
        #fontMeta { display: block; font-size: 11px; color: #6a7d90; margin-top: 3px; line-height: 1.2; text-align: center; }
        .font-group { margin-top: 8px; }
        .font-group:first-of-type { margin-top: 0; }
        .font-group-title { font-size: 11px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; color: #4f5d6b; margin-bottom: 5px; }
        .font-grid { display: grid; grid-template-columns: 1fr; gap: 6px; margin: 0; }
        .font-option { border: 1px solid #d5dde7; border-radius: 14px; padding: 8px 9px; cursor: pointer; background: #ffffff; }
        .font-option.is-selected { border-color: #0a84ff; background: #eef6ff; }
        .font-name { font-size: 13px; font-weight: 700; margin-bottom: 1px; }
        .font-tags { font-size: 11px; color: #5f6b77; margin-bottom: 4px; }
        .font-sample { font-size: 14px; color: #1f2731; line-height: 1.15; }

        @media (max-width: 840px) {
            .hero { flex-direction: column; }
            .device-row, .actions { grid-template-columns: 1fr; }
            .preview-area { flex-direction: column; }
            #previewFrame { width: 100%; min-width: 0; }
            .preview-side-actions { width: 100%; min-width: 0; flex-direction: row; }
            .preview-side-actions button { flex: 1; }
            #fontOverlay { left: 0; top: calc(100% + 10px); min-width: min(420px, calc(100vw - 40px)); width: min(420px, calc(100vw - 40px)); max-height: none; }
        }

    </style>
</head>
<body>    <div id="busyOverlay">
        <div class="busy-card">
            <div class="busy-spinner"></div>
            <div id="busyMessage">Bitte warten…</div>
            <div class="busy-actions">
                <button id="busyHideBtn" type="button" class="busy-action">Hide</button>
                <button id="busyCancelBtn" type="button" class="busy-action is-hidden">Cancel</button>
            </div>
        </div>
    </div>    <div id=\"statusToast\" class=\"status-toast\" aria-live=\"polite\">
        <span id=\"statusToastText\">Ready.</span>
    </div>
  <div class=\"row\">
    <div class=\"card\">
            <div class=\"hero\">
                <div>
                    <h1>TiMini Web Print</h1>
                    <p>Fast browser workflow for scan, preview, and label printing.</p>
                </div>
                                <div class=\"status-hub\">
                                        <button id=\"statusHistoryBtn\" type=\"button\" title=\"Show recent status messages\">i</button>
                                    <button id=\"debugLogBtn\" type=\"button\" title=\"Toggle runtime debug log\">Debug</button>
                                        <div id=\"statusHistoryPanel\" class=\"status-history-panel is-hidden\">
                                                <div class=\"status-history-title\">Recent Status</div>
                                                <ul id=\"statusHistoryList\" class=\"status-history-list\">
                                                        <li>Ready.</li>
                                                </ul>
                                        </div>
                                    <div id=\"debugLogPanel\" class=\"debug-log-panel is-hidden\">
                                        <div class=\"debug-log-head\">
                                            <div class=\"status-history-title\">Runtime Debug Log</div>
                                            <div class=\"debug-log-actions\">
                                                <button id=\"debugRefreshBtn\" type=\"button\">Refresh</button>
                                                <button id=\"debugClearBtn\" type=\"button\">Clear</button>
                                            </div>
                                        </div>
                                        <div id=\"debugLogMeta\">No debug entries yet.</div>
                                        <ul id=\"debugLogList\" class=\"debug-log-list\">
                                            <li>Debug panel hidden by default.</li>
                                        </ul>
                                    </div>
                                </div>
            </div>
            <div class=\"section section-card\">
                <label for=\"deviceSelect\">Printer</label>
                <div class=\"device-row\">
                    <select id=\"deviceSelect\"></select>
                    <button id=\"refreshBtn\" type=\"button\">Refresh</button>
                    <button id=\"connectBtn\" type=\"button\">Connect</button>
                    <span id=\"connectSpinner\" class=\"connect-indicator\" title=\"Connecting\"></span>
                </div>
                <div id=\"connectionState\">Not connected.</div>
            </div>

            <div class=\"section section-card\">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
                    <label for="text" style="margin-bottom:0;">Label text</label>
                    <label style="display:flex;align-items:center;gap:5px;font-size:12px;color:#6a7d90;cursor:pointer;margin-bottom:0;">
                        <input type="checkbox" id="syncFontToggle" checked style="width:auto;margin-bottom:0;"> auto-fill
                    </label>
                </div>
                <textarea id="text" rows="10">ABCDEFGHIJKLMNOPQRSTUVWXYZ</textarea>
            </div>

            <div class=\"section section-card\">
                <div class=\"preview-wrapper\">
                    <div class=\"preview-area\">
                        <div id=\"previewFrame\"><div class=\"carrier-strip\"></div><div class=\"label-area\"><img id=\"preview\" alt=\"preview\" /></div><div class=\"carrier-strip\"></div></div>
                        <div class=\"preview-side-actions\">
                            <button id=\"fontBtn\" type=\"button\">Font</button>
                            <button id=\"fontSizeBtn\" type=\"button\">Font size</button>
                            <div class=\"font-summary\">
                                <div id=\"fontLabel\"></div>
                                <div id=\"fontMeta\"></div>
                            </div>
                            <div id=\"fontOverlay\" class=\"side-overlay is-hidden\">
                                <div class=\"overlay-title\">Font</div>
                                <div id=\"fontList\" class=\"font-grid\"></div>
                                <div class=\"overlay-footer\">
                                    <button id=\"fontCancelBtn\" type=\"button\">Cancel</button>
                                    <button id=\"fontOkBtn\" type=\"button\">OK</button>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div id=\"fontSizeOverlay\" class=\"side-overlay is-hidden\">
                        <div class=\"overlay-title\">Font size</div>
                        <div class=\"slider-row\">
                            <span class=\"slider-hint\">small</span>
                            <input id=\"columns\" type=\"range\" min=\"15\" max=\"52\" value=\"52\" />
                            <span id=\"columnsValue\" class=\"slider-hint\">15 cpl</span>
                        </div>
                        <div class=\"overlay-footer\">
                            <button id=\"fontSizeCancelBtn\" type=\"button\">Cancel</button>
                            <button id=\"fontSizeOkBtn\" type=\"button\">OK</button>
                        </div>
                    </div>
                </div>
                <div class=\"preview-actions actions\">
                    <button id=\"previewBtn\" type=\"button\">Refresh Preview</button>
                    <button id=\"printBtn\" type=\"button\">Print Label</button>
                </div>
            </div>

            <div class=\"section section-card\">
                <label for=\"darkness\">Darkness</label>
                <input id=\"darkness\" type=\"number\" min=\"1\" max=\"5\" value=\"3\" />
            </div>

    </div>
  </div>

<script src="/static/app.js"></script>
</body>
</html>"""


@app.get("/favicon.ico")
def favicon() -> RedirectResponse:
        return RedirectResponse(url="/static/favicon.svg", status_code=307)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/debug/logs")
def debug_logs(limit: int = Query(default=120, ge=1, le=300)) -> dict[str, object]:
    entries = list(_debug_events)[-limit:]
    return {
        "entries": entries,
        "count": len(entries),
    }


@app.post("/api/debug/clear")
def clear_debug_logs() -> dict[str, str]:
    _debug_events.clear()
    _debug_event("system", "Debug log cleared")
    return {"message": "Debug log cleared."}


@app.get("/api/profiles")
def profiles() -> dict[str, list[dict[str, object]]]:
    catalog = PrinterCatalog.load()
    return {
        "profiles": [
            {
                "profile_key": profile.profile_key,
                "width": _normalize_width(profile.width),
            }
            for profile in catalog.profiles
        ]
    }


@app.get("/api/fonts")
def fonts() -> dict[str, object]:
    keys = [key for key, meta in FONT_CATALOG.items() if (FONT_DIR / meta["filename"]).exists()]
    if not keys:
        return {"fonts": [], "default_font_key": None}
    default_key = DEFAULT_FONT_KEY if DEFAULT_FONT_KEY in keys else keys[0]
    return {
        "default_font_key": default_key,
        "fonts": [
            {
                "key": key,
                "label": FONT_CATALOG[key]["label"],
                "family": FONT_CATALOG[key]["family"],
                "width": FONT_CATALOG[key]["width"],
                "css_family": FONT_CATALOG[key]["css_family"],
            }
            for key in keys
        ],
    }


@app.post("/api/scan")
async def scan() -> dict[str, object]:
    active_target = _active_printer["target"] if _active_printer else None
    catalog = PrinterCatalog.load()
    discovery = BluetoothDiscovery(catalog)
    _debug_event("scan", "Scan started", has_active_printer=bool(active_target))
    result = await discovery.scan_report(include_classic=True, include_ble=True)
    if result.failures:
        for failure in result.failures:
            _debug_event("warning", "Scan transport failed", transport=failure.transport.value, error=str(failure.error))
    _debug_event(
        "scan",
        "Scan finished",
        devices=len(result.devices),
        failures=len(result.failures),
    )
    return {
        "devices": [
            {
                "display_name": device.display_name,
                "address": device.address,
                "transport_badge": device.transport_badge,
                "profile_key": device.profile_key,
                "paired": device.paired,
                "connected": device.address == active_target,
            }
            for device in result.devices
        ],
        "active_printer": _active_printer,
        "failures": [
            {
                "transport": failure.transport.value,
                "error": str(failure.error),
            }
            for failure in result.failures
        ],
    }


@app.post("/api/connect")
async def connect(request: ConnectRequest) -> dict[str, str]:
    global _active_printer
    catalog = PrinterCatalog.load()
    discovery = BluetoothDiscovery(catalog)
    _debug_event("connect", "Connect started", target=request.target)
    try:
        device = await discovery.resolve_device(request.target)

        reporter = reporting.Reporter([reporting.StderrSink(levels={"debug", "warning", "error"})])
        connector = BleakBluetoothConnector(reporter=reporter)
        connection = await connector.connect(device)
        await connection.disconnect()
    except Exception as exc:
        _debug_event("error", "Connect failed", target=request.target, error=str(exc))
        raise

    _active_printer = {
        "target": device.address,
        "display_name": device.display_name,
        "profile_key": device.profile_key,
        "transport_badge": device.transport_badge,
    }
    _debug_event("connect", "Connect succeeded", target=device.address, display_name=device.display_name)
    return {
        "target": device.address,
        "display_name": device.display_name,
        "profile_key": device.profile_key,
        "transport_badge": device.transport_badge,
    }


@app.post("/api/preview")
def preview(request: PreviewRequest) -> dict[str, object]:
    width = _resolve_profile_width(request.profile_key)
    font_path = _resolve_font_path(request.text_font_key, request.text_font)
    converter = TextConverter(
        font_path=font_path,
        columns=request.text_columns,
        wrap_lines=True,
    )
    with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as handle:
        handle.write(request.text)
        temp_path = Path(handle.name)
    try:
        page = converter.load(str(temp_path), width)[0]
        buf = io.BytesIO()
        page.image.save(buf, format="PNG")
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return {
            "image_data": f"data:image/png;base64,{encoded}",
            "width": page.image.width,
            "height": page.image.height,
        }
    finally:
        temp_path.unlink(missing_ok=True)


def _build_args(request: PrintRequest) -> argparse.Namespace:
    text_font = _resolve_font_path(request.text_font_key, request.text_font)
    return argparse.Namespace(
        path=None,
        bluetooth=request.bluetooth,
        serial=request.serial,
        device_config=request.device_config,
        export_device_config=None,
        scan=False,
        list_profiles=False,
        text=request.text,
        text_font=text_font,
        text_columns=request.text_columns,
        pdf_pages=None,
        pdf_page_gap=5,
        trim_side_margins=True,
        trim_top_bottom_margins=True,
        darkness=request.darkness,
        verbose=True,
        force_text_mode=False,
        force_image_mode=False,
        feed=False,
        retract=False,
    )


def _decode_data_url(data_url: str) -> bytes:
    payload = data_url
    if "," in data_url:
        payload = data_url.split(",", 1)[1]
    try:
        return base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid image_data payload") from exc


@app.post("/api/print")
async def print_label(request: PrintRequest) -> dict[str, str]:
    if not request.image_data and not request.text.strip():
        raise HTTPException(status_code=400, detail="Missing text or image_data")

    _debug_event(
        "print",
        "Print started",
        bluetooth_target=request.bluetooth,
        serial_target=request.serial,
        text_columns=request.text_columns,
        has_image=bool(request.image_data),
    )
    args = _build_args(request)
    temp_image: Path | None = None
    if request.image_data:
        raw = _decode_data_url(request.image_data)
        with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as handle:
            handle.write(raw)
            temp_image = Path(handle.name)
        args.path = str(temp_image)
        args.text = None
        args.force_image_mode = True

    try:
        if args.serial:
            code = await asyncio.to_thread(cli_app.print_serial, args)
        else:
            reporter = reporting.Reporter([reporting.StderrSink(levels={"debug", "warning", "error"})])
            code = await asyncio.to_thread(cli_app.print_bluetooth, args, reporter)
    except Exception as exc:
        _debug_event("error", "Print unexpected exception", error=str(exc))
        logger.exception("Unexpected error while handling /api/print request", exc_info=exc)
        raise HTTPException(status_code=500, detail="PRINT_UNEXPECTED_ERROR") from exc
    finally:
        if temp_image is not None:
            temp_image.unlink(missing_ok=True)

    if code != 0:
        _debug_event("error", "Print failed", exit_code=code)
        raise HTTPException(status_code=500, detail=f"Print failed with exit code {code}")
    _debug_event("print", "Print job sent")
    return {"message": "Print job sent."}

