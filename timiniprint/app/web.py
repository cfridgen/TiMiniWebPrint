from __future__ import annotations

import argparse
import asyncio
import base64
import io
import logging
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import reporting
from ..devices import PrinterCatalog
from ..rendering.converters.text import TextConverter
from ..transport.bluetooth import BluetoothDiscovery
from . import cli as cli_app

app = FastAPI(title="TiMini Web Print", version="0.1.0")
app.mount("/static", StaticFiles(directory=Path(__file__).with_name("web_static")), name="static")
logger = logging.getLogger("timiniprint.web")


@app.middleware("http")
async def log_http_requests(request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - started) * 1000
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
    return response


class PreviewRequest(BaseModel):
    text: str = Field(default="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    profile_key: str | None = None
    text_columns: int = Field(default=15, ge=1, le=120)
    text_hard_wrap: bool = False
    text_font: str | None = None


class PrintRequest(BaseModel):
    text: str = Field(min_length=1)
    bluetooth: str | None = None
    serial: str | None = None
    device_config: str | None = None
    text_columns: int = Field(default=15, ge=1, le=120)
    text_hard_wrap: bool = False
    text_font: str | None = None
    darkness: int = Field(default=3, ge=1, le=5)


class ScanRequest(BaseModel):
    target: str | None = None


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
    return _normalize_width(profiles[0].width)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>TiMini Web Print</title>
  <style>
    body { font-family: sans-serif; margin: 20px; max-width: 980px; }
    h1 { margin-bottom: 8px; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 12px; }
    .card { border: 1px solid #ccc; border-radius: 8px; padding: 12px; }
    label { display: block; font-size: 13px; margin-bottom: 4px; }
    textarea, input, select, button { width: 100%; box-sizing: border-box; padding: 8px; margin-bottom: 8px; }
    textarea { min-height: 130px; resize: vertical; }
    .actions { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
    #preview { max-width: 100%; border: 1px solid #ddd; background: #fff; }
    #status { white-space: pre-wrap; font-family: monospace; background: #f7f7f7; padding: 10px; border-radius: 8px; }
  </style>
</head>
<body>
  <h1>TiMini Web Print</h1>
  <p>Browser UI for scan, preview, and label printing.</p>

  <div class=\"row\">
    <div class=\"card\">
      <label for=\"text\">Label text</label>
      <textarea id=\"text\">ABCDEFGHIJKLMNOPQRSTUVWXYZ</textarea>

      <label for=\"bluetooth\">Bluetooth target (name or address)</label>
      <input id=\"bluetooth\" placeholder=\"optional, leave empty for first supported printer\" />

      <label for=\"serial\">Serial port (optional)</label>
      <input id=\"serial\" placeholder=\"optional, e.g. /dev/rfcomm0\" />

      <label for=\"deviceConfig\">Device config path (optional, needed for serial/manual profile)</label>
      <input id=\"deviceConfig\" placeholder=\"optional path to exported device config json\" />

      <label for=\"columns\">Text columns (cpl)</label>
      <input id=\"columns\" type=\"number\" min=\"1\" max=\"120\" value=\"15\" />

      <label for=\"darkness\">Darkness</label>
      <input id=\"darkness\" type=\"number\" min=\"1\" max=\"5\" value=\"3\" />

      <label><input id=\"hardWrap\" type=\"checkbox\" /> Hard wrap text</label>

      <div class=\"actions\">
        <button id=\"scanBtn\">Scan</button>
        <button id=\"previewBtn\">Preview</button>
        <button id=\"printBtn\">Print</button>
      </div>
    </div>

    <div class=\"card\">
      <label for=\"profile\">Preview profile</label>
      <select id=\"profile\"></select>
      <img id=\"preview\" alt=\"preview\" />
      <h3>Status</h3>
      <div id=\"status\">Ready.</div>
    </div>
  </div>

<script src="/static/app.js"></script>
</body>
</html>"""


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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


@app.post("/api/scan")
async def scan(_request: ScanRequest) -> dict[str, object]:
    catalog = PrinterCatalog.load()
    discovery = BluetoothDiscovery(catalog)
    result = await discovery.scan_report(include_classic=True, include_ble=True)
    return {
        "devices": [
            {
                "display_name": device.display_name,
                "address": device.address,
                "transport_badge": device.transport_badge,
                "profile_key": device.profile_key,
                "paired": device.paired,
            }
            for device in result.devices
        ],
        "failures": [
            {
                "transport": failure.transport.value,
                "error": str(failure.error),
            }
            for failure in result.failures
        ],
    }


@app.post("/api/preview")
def preview(request: PreviewRequest) -> dict[str, object]:
    width = _resolve_profile_width(request.profile_key)
    converter = TextConverter(
        font_path=request.text_font,
        columns=request.text_columns,
        wrap_lines=not request.text_hard_wrap,
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
    return argparse.Namespace(
        path=None,
        bluetooth=request.bluetooth,
        serial=request.serial,
        device_config=request.device_config,
        export_device_config=None,
        scan=False,
        list_profiles=False,
        text=request.text,
        text_font=request.text_font,
        text_columns=request.text_columns,
        text_hard_wrap=request.text_hard_wrap,
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


@app.post("/api/print")
async def print_label(request: PrintRequest) -> dict[str, str]:
    args = _build_args(request)
    try:
        if args.serial:
            code = await asyncio.to_thread(cli_app.print_serial, args)
        else:
            reporter = reporting.Reporter([reporting.StderrSink(levels={"debug", "warning", "error"})])
            code = await asyncio.to_thread(cli_app.print_bluetooth, args, reporter)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if code != 0:
        raise HTTPException(status_code=500, detail=f"Print failed with exit code {code}")
    return {"message": "Print job sent."}
