# TODO: DO NOT READ. This code is waiting to be rewritten :P
# One day I’ll refactor the whole GUI properly;
# for now, the terrible single-file monolith stays.

from __future__ import annotations

import asyncio
import os
import queue
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, ttk

from PIL import Image, ImageFont, ImageOps, ImageTk

from .diagnostics import emit_startup_warnings
from .. import reporting
from ..devices import PrinterCatalog
from ..protocol import PrinterProtocol
from ..rendering.converters.text import TextConverter
from ..rendering.fonts import find_monospace_bold_font
from ..transport.bluetooth import BleakBluetoothConnector, BluetoothDiscovery
from ..transport.bluetooth.types import DeviceTransport

PAPER_MOTION_INTERVAL_MS = 1000
PREVIEW_WRAP_COLUMNS = 15
PREVIEW_FONT_SCALE = 1.2


class BleLoop:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
        pending = [task for task in asyncio.all_tasks(self._loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self._loop.run_until_complete(self._loop.shutdown_asyncgens())
        self._loop.close()

    def submit(self, coro, callback=None):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        if callback:
            future.add_done_callback(callback)
        return future

    def shutdown(self, timeout: float = 2.0) -> None:
        if self._loop.is_closed():
            return
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout)


class TiMiniPrintGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        emit_startup_warnings()
        self.title("TiMini Print")
        self.resizable(True, True)

        self.catalog = PrinterCatalog.load()
        self.discovery = BluetoothDiscovery(self.catalog)
        self.ble_loop = BleLoop()
        self.queue: queue.Queue = queue.Queue()
        self.reporter = reporting.Reporter(
            [
                reporting.QueueStatusSink(self.queue, show_warnings=True),
                reporting.StderrSink(),
            ]
        )
        self.connector = BleakBluetoothConnector(reporter=self.reporter)
        self.connection = None

        self.devices = []
        self.device_map = {}

        self.device_var = tk.StringVar()
        self.profile_var = tk.StringVar(value="")
        self.file_var = tk.StringVar()
        self.text_input_var = tk.StringVar()
        self.text_mode_var = tk.BooleanVar(value=False)
        self.rotate_90_var = tk.BooleanVar(value=False)
        self.darkness_var = tk.IntVar(value=3)
        self.text_font_var = tk.StringVar()
        self.text_columns_var = tk.IntVar(value=15)
        self.text_wrap_var = tk.BooleanVar(value=True)
        self.trim_margins_var = tk.BooleanVar(value=True)
        self.trim_top_bottom_margins_var = tk.BooleanVar(value=True)
        self.pdf_pages_var = tk.StringVar()
        self.pdf_gap_var = tk.IntVar(value=5)
        self.status_var = tk.StringVar(
            value=reporting.MessageCatalog.resolve("status", reporting.STATUS_IDLE) or "Idle"
        )
        self.connected_device = None
        self._connecting = False
        self._paper_motion_action = None
        self._paper_motion_job = None
        self._paper_motion_busy = False
        self._layout_ready = False
        self._closing = False
        self._animation_spinner_index = 0
        self._animation_mode = "scan"
        self._animation_job = None
        self._bt_icon_idle = None
        self._bt_icon_connected = None
        self._bt_scan_frames = []
        self._bt_connect_frames = []
        self._bt_fallback_symbols = ["ᛒ", "ᛒ", "ᛒ", "ᛒ"]
        self._preview_area_width_px = None
        self.file_var.trace_add("write", self._on_file_path_change)
        self.text_columns_var.trace_add("write", self._on_text_columns_change)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self.update_idletasks()
        self.minsize(int(self.winfo_reqwidth()*.9), self.winfo_reqheight())

        self._layout_ready = True
        self._on_text_columns_change()  # Set initial font size for text input
        self._set_connected_state(False)
        self.after(100, self._process_queue)
        self.after(200, self.scan)
        
    def _build_ui(self) -> None:
        padding = {"padx": 10, "pady": 6}

        device_frame = ttk.LabelFrame(self, text="Bluetooth")
        device_frame.pack(fill="x", padx=10, pady=10)
        device_frame.columnconfigure(1, weight=1)

        ttk.Label(device_frame, text="Device:").grid(row=0, column=0, sticky="w", **padding)
        self.device_combo = ttk.Combobox(device_frame, textvariable=self.device_var, width=38, state="readonly")
        self.device_combo.grid(row=0, column=1, sticky="ew", **padding)

        self.bluetooth_icon_container = tk.Frame(
            device_frame,
            width=34,
            height=30,
            bg=self.cget("bg"),
        )
        self.bluetooth_icon_container.grid(row=0, column=2, rowspan=2, sticky="n", pady=(8, 0))
        self.bluetooth_icon_container.grid_propagate(False)

        self.bluetooth_status_icon = tk.Label(
            self.bluetooth_icon_container,
            bg=self.cget("bg"),
        )
        self.bluetooth_status_icon.pack(expand=True)
        self._load_bluetooth_icon_states()

        self.refresh_button = ttk.Button(device_frame, text="Refresh", command=self.scan)
        self.refresh_button.grid(row=0, column=3, **padding)
        ttk.Label(device_frame, text="Profile:").grid(row=1, column=0, sticky="w", **padding)
        self.profile_label = ttk.Label(device_frame, textvariable=self.profile_var, width=48)
        self.profile_label.grid(row=1, column=1, sticky="ew", **padding)

        self.connection_button = ttk.Button(device_frame, text="Connect", command=self.toggle_connection)
        self.connection_button.grid(row=1, column=3, sticky="e", **padding)

        file_frame = ttk.LabelFrame(self, text="Input")
        file_frame.pack(fill="both", expand=False, padx=10, pady=10)
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="File path:").grid(row=0, column=0, sticky="w", **padding)
        self.file_entry = ttk.Entry(file_frame, textvariable=self.file_var, width=48)
        self.file_entry.grid(row=0, column=1, sticky="ew", **padding)
        self.browse_button = ttk.Button(file_frame, text="Browse", command=self.browse)
        self.browse_button.grid(row=0, column=2, **padding)

        ttk.Label(file_frame, text="Or text:").grid(row=1, column=0, sticky="nw", **padding)
        self.text_input_container = ttk.Frame(file_frame, width=420, height=110)
        self.text_input_container.grid(row=1, column=1, sticky="w", **padding)
        self.text_input_container.grid_propagate(False)
        self.text_input_container.pack_propagate(False)
        self.text_input = tk.Text(self.text_input_container, height=4, width=1, wrap="word")
        self.text_input.pack(fill="both", expand=True)
        self.text_input.insert("1.0", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        self.text_input.bind("<Control-a>", lambda e: (self.text_input.tag_add("sel", "1.0", "end"), "break"))
        file_frame.rowconfigure(1, weight=0)

        self.options_frame = ttk.LabelFrame(self, text="Options")
        self.options_frame.pack(fill="x", padx=10, pady=10)
        checks_frame = ttk.Frame(self.options_frame)
        checks_frame.grid(row=0, column=0, columnspan=3, sticky="w", **padding)
        self.text_mode_check = ttk.Checkbutton(
            checks_frame,
            text="Firmware text mode",
            variable=self.text_mode_var,
        )
        self.text_mode_check.pack(side="left", padx=(0, 12))
        self.rotate_90_check = ttk.Checkbutton(
            checks_frame,
            text="Rotate 90 deg",
            variable=self.rotate_90_var,
        )
        self.rotate_90_check.pack(side="left", padx=(0, 12))
        self.trim_margins_check = ttk.Checkbutton(
            checks_frame,
            text="Trim side margins",
            variable=self.trim_margins_var,
        )
        self.trim_margins_check.pack(side="left", padx=(0, 12))
        self.trim_top_bottom_margins_check = ttk.Checkbutton(
            checks_frame,
            text="Trim vertical margins",
            variable=self.trim_top_bottom_margins_var,
        )
        self.trim_top_bottom_margins_check.pack(side="left")
        ttk.Label(self.options_frame, text="Darkness:").grid(row=1, column=0, sticky="w", **padding)
        self.darkness_scale = tk.Scale(
            self.options_frame,
            from_=1,
            to=5,
            orient="horizontal",
            resolution=1,
            showvalue=False,
            variable=self.darkness_var,
        )
        self.darkness_scale.grid(row=1, column=1, sticky="ew", **padding)
        self.darkness_value_label = ttk.Label(self.options_frame, textvariable=self.darkness_var, width=2)
        self.darkness_value_label.grid(row=1, column=2, sticky="w", **padding)
        self.options_frame.columnconfigure(1, weight=1)

        self.text_frame = ttk.LabelFrame(self, text="Txt Options")
        self.text_frame.columnconfigure(1, weight=1)
        ttk.Label(self.text_frame, text="Font:").grid(row=0, column=0, sticky="w", **padding)
        self.text_font_entry = ttk.Entry(self.text_frame, textvariable=self.text_font_var, width=48)
        self.text_font_entry.grid(row=0, column=1, sticky="ew", **padding)
        self.text_font_browse = ttk.Button(self.text_frame, text="Browse", command=self.browse_text_font)
        self.text_font_browse.grid(row=0, column=2, **padding)
        self.text_font_clear = ttk.Button(self.text_frame, text="Default", command=self.clear_text_font)
        self.text_font_clear.grid(row=0, column=3, **padding)
        ttk.Label(self.text_frame, text="Schriftgröße:").grid(row=1, column=0, sticky="w", **padding)
        size_controls = ttk.Frame(self.text_frame)
        size_controls.grid(row=1, column=1, columnspan=3, sticky="ew", **padding)
        size_controls.columnconfigure(1, weight=1)
        left_indicator = ttk.Frame(size_controls)
        left_indicator.grid(row=0, column=0, sticky="e", padx=(0, 4))
        ttk.Label(left_indicator, text="kleiner", font=("TkDefaultFont", 8)).grid(row=0, column=0, sticky="e")
        ttk.Label(left_indicator, text="50 cpl", font=("TkDefaultFont", 6)).grid(row=1, column=0, sticky="e")
        self.text_columns_scale = tk.Scale(
            size_controls,
            from_=50,
            to=15,
            orient="horizontal",
            resolution=1,
            showvalue=False,
            variable=self.text_columns_var,
        )
        self.text_columns_scale.grid(row=0, column=1, sticky="ew", padx=4)
        right_indicator = ttk.Frame(size_controls)
        right_indicator.grid(row=0, column=2, sticky="w", padx=(4, 0))
        ttk.Label(right_indicator, text="Größer", font=("TkDefaultFont", 13, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(right_indicator, text="15 cpl", font=("TkDefaultFont", 6)).grid(row=1, column=0, sticky="w")
        self.text_columns_value_label = ttk.Label(self.text_frame, textvariable=self.text_columns_var, width=4)
        self.text_columns_value_label.grid(row=2, column=0, sticky="w", **padding)
        self.text_wrap_check = ttk.Checkbutton(
            self.text_frame,
            text="Whitespace wrap",
            variable=self.text_wrap_var,
        )
        self.text_wrap_check.grid(row=2, column=1, sticky="w", **padding)

        self.pdf_frame = ttk.LabelFrame(self, text="PDF Options")
        self.pdf_frame.columnconfigure(1, weight=1)
        ttk.Label(self.pdf_frame, text="Pages (e.g. 1-3,5):").grid(row=0, column=0, sticky="w", **padding)
        self.pdf_pages_entry = ttk.Entry(self.pdf_frame, textvariable=self.pdf_pages_var, width=48)
        self.pdf_pages_entry.grid(row=0, column=1, sticky="ew", **padding)
        ttk.Label(self.pdf_frame, text="Page gap (mm):").grid(row=1, column=0, sticky="w", **padding)
        self.pdf_gap_scale = tk.Scale(
            self.pdf_frame,
            from_=0,
            to=50,
            orient="horizontal",
            resolution=1,
            showvalue=False,
            variable=self.pdf_gap_var,
        )
        self.pdf_gap_scale.grid(row=1, column=1, sticky="ew", **padding)
        self.pdf_gap_value_label = ttk.Label(self.pdf_frame, textvariable=self.pdf_gap_var, width=4)
        self.pdf_gap_value_label.grid(row=1, column=2, sticky="w", **padding)

        self.action_frame = ttk.Frame(self)
        self.action_frame.pack(fill="x", padx=10, pady=10)
        self.print_button = ttk.Button(self.action_frame, text="Print", command=self.print_file)
        self.retract_button = ttk.Button(self.action_frame, text="Retract")
        self.feed_button = ttk.Button(self.action_frame, text="Feed")
        self.feed_button.pack(side="left")
        self.retract_button.pack(side="left", padx=(6, 0))
        self.print_button.pack(side="right")
        self.feed_button.bind("<ButtonPress-1>", lambda event: self._start_paper_motion("feed"))
        self.feed_button.bind("<ButtonRelease-1>", self._stop_paper_motion)
        self.feed_button.bind("<Leave>", self._stop_paper_motion)
        self.retract_button.bind("<ButtonPress-1>", lambda event: self._start_paper_motion("retract"))
        self.retract_button.bind("<ButtonRelease-1>", self._stop_paper_motion)
        self.retract_button.bind("<Leave>", self._stop_paper_motion)

        status_frame = ttk.Frame(self)
        status_frame.pack(fill="x", padx=10, pady=10)
        ttk.Label(status_frame, text="Status:").pack(side="left")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side="left", padx=6)

        self._update_option_sections(self.file_var.get())

    def _process_queue(self) -> None:
        while True:
            try:
                action, payload = self.queue.get_nowait()
            except queue.Empty:
                break
            if action == "status":
                self.status_var.set(payload)
            elif action == "devices":
                self.devices = payload
                self.device_map = {self._device_label(d): d for d in payload}
                values = list(self.device_map.keys())
                self.device_combo["values"] = values
                current = self.device_var.get()
                if values:
                    if current in self.device_map:
                        self.device_var.set(current)
                    elif not self.connected_device:
                        self.device_var.set(values[0])
                else:
                    self.device_var.set("")
            elif action == "connected":
                device = payload
                self._set_connected_state(True, device)
            elif action == "disconnected":
                self._set_connected_state(False)
            elif action == "error":
                self.status_var.set(f"Error: {payload}")
            elif action == "connecting":
                self._set_connecting_state(bool(payload))
        self.after(100, self._process_queue)

    def _device_label(self, device) -> str:
        name = device.display_name or ""
        transport = f" {device.transport_badge}"
        experimental = device.experimental_badge
        status = " [unpaired]" if device.paired is False else ""
        if name:
            return f"{name}{experimental} ({device.address}){transport}{status}"
        return f"{device.address}{experimental}{transport}{status}"

    def _queue_status(self, key: str, **ctx) -> None:
        self.reporter.status(key, **ctx)

    def _queue_warning(self, key: str, detail=None, **ctx) -> None:
        self.reporter.warning(key, detail=detail, **ctx)

    def _queue_error(self, key: str, detail=None, exc=None, **ctx) -> None:
        self.reporter.error(key, detail=detail, exc=exc, **ctx)

    def scan(self) -> None:
        self._queue_status(reporting.STATUS_SCAN_START)
        self._start_animation("scan")

        def done(fut):
            try:
                result = fut.result()
                self.queue.put(("devices", result.devices))
                for failure in result.failures:
                    if failure.transport == DeviceTransport.BLE:
                        self._queue_warning(reporting.WARNING_SCAN_BLE_FAILED, detail=str(failure.error))
                    else:
                        self._queue_warning(reporting.WARNING_SCAN_CLASSIC_FAILED, detail=str(failure.error))
                self._queue_status(reporting.STATUS_SCAN_DONE, count=len(result.devices))
                self._stop_animation()
            except Exception as exc:
                self._queue_error(reporting.ERROR_SCAN_FAILED, detail=str(exc), exc=exc)
                self._stop_animation()

        self.ble_loop.submit(self.discovery.scan_report(), callback=done)

    def connect(self) -> None:
        label = self.device_var.get()
        device = self.device_map.get(label)
        if not device:
            self._queue_error(reporting.ERROR_NO_DEVICE)
            return
        self._queue_status(reporting.STATUS_CONNECT_START)
        self.queue.put(("connecting", True))

        def done(fut):
            try:
                self.connection = fut.result()
                self._queue_status(reporting.STATUS_CONNECT_DONE)
                self.queue.put(("connected", device))
            except Exception as exc:
                self._queue_error(reporting.ERROR_CONNECT_FAILED, detail=str(exc), exc=exc)
                self.queue.put(("connecting", False))

        self.ble_loop.submit(self.connector.connect(device), callback=done)

    def toggle_connection(self) -> None:
        if self._connecting:
            return
        if self.connected_device:
            self.disconnect()
        else:
            self.connect()

    def disconnect(self) -> None:
        self._queue_status(reporting.STATUS_DISCONNECT_START)
        connection = self.connection

        def done(fut):
            try:
                fut.result()
                self.connection = None
                self._queue_status(reporting.STATUS_DISCONNECT_DONE)
                self.queue.put(("disconnected", None))
            except Exception as exc:
                self._queue_error(reporting.ERROR_DISCONNECT_FAILED, detail=str(exc), exc=exc)

        if connection is None:
            self.queue.put(("disconnected", None))
            return
        self.ble_loop.submit(connection.disconnect(), callback=done)

    def browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select file",
            filetypes=[
                ("Supported", "*.png *.jpg *.jpeg *.gif *.bmp *.pdf *.txt"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.file_var.set(path)

    def browse_text_font(self) -> None:
        """Open the native OS font file picker and apply selected font to preview."""
        path = filedialog.askopenfilename(
            parent=self,
            title="Select font",
            initialdir=self._default_font_directory(),
            filetypes=[
                ("Font files", "*.ttf *.otf *.ttc"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.text_font_var.set(path)
            self._on_text_columns_change()

    def clear_text_font(self) -> None:
        self.text_font_var.set("")
        self._on_text_columns_change()

    @staticmethod
    def _default_font_directory() -> str:
        if os.name == "nt":
            return os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
        if os.path.isdir("/System/Library/Fonts"):
            return "/System/Library/Fonts"
        if os.path.isdir("/Library/Fonts"):
            return "/Library/Fonts"
        if os.path.isdir("/usr/share/fonts"):
            return "/usr/share/fonts"
        return os.path.expanduser("~")

    def _preview_font_spec(self, font_size: int):
        configured_font = self.text_font_var.get().strip()
        font_source = configured_font or find_monospace_bold_font()
        family_name = "TkFixedFont"
        style_tokens = []

        if font_source and os.path.isfile(font_source):
            try:
                family_name, style_name = ImageFont.truetype(font_source, 10).getname()
                style_name = (style_name or "").lower()
                if "bold" in style_name:
                    style_tokens.append("bold")
                if "italic" in style_name or "oblique" in style_name:
                    style_tokens.append("italic")
            except Exception:
                pass
        elif configured_font:
            family_name = configured_font

        return (family_name, font_size, *style_tokens)

    def _on_file_path_change(self, *_args) -> None:
        path = self.file_var.get()
        self._set_text_mode_for_path(path)
        self._update_option_sections(path)

    def _on_text_columns_change(self, *_args) -> None:
        """Update text input preview font size based on columns slider."""
        try:
            columns = self.text_columns_var.get()
            # Calculate font size: inverse relationship to columns (more columns = smaller font)
            # Formula: base_size * (default_columns / current_columns)
            # At 35 columns (default), use 10pt; scales proportionally
            base_size = 10
            default_columns = 35
            font_size = max(6, int(round(base_size * default_columns * PREVIEW_FONT_SCALE / columns)))
            preview_font = self._preview_font_spec(font_size)
            self.text_input.configure(font=preview_font)

            measured_font = tkfont.Font(font=self.text_input.cget("font"))
            if self._preview_area_width_px is None:
                # Calibrate once from the default 15 cpl view; printer width is fixed afterwards.
                alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                repeats = (PREVIEW_WRAP_COLUMNS // len(alphabet)) + 1
                preview_sample = (alphabet * repeats)[:PREVIEW_WRAP_COLUMNS]
                content_width = measured_font.measure(preview_sample)
                self._preview_area_width_px = max(220, min(760, content_width + 24))
            self.text_input_container.configure(width=self._preview_area_width_px)
        except Exception:
            pass  # Ignore errors during initialization

    def _set_text_mode_for_path(self, path: str) -> None:
        path = path.strip()
        if not path:
            self.text_mode_var.set(False)
            return
        ext = os.path.splitext(path)[1].lower()
        self.text_mode_var.set(ext == ".txt")

    def _update_option_sections(self, path: str) -> None:
        ext = os.path.splitext(path.strip())[1].lower()
        # Text options are always visible (for both file input and direct text)
        self._set_section_visible(self.text_frame, True)
        self._set_section_visible(self.pdf_frame, ext == ".pdf")
        self._refresh_min_height()

    def _set_section_visible(self, frame: ttk.LabelFrame, visible: bool) -> None:
        if visible:
            if not frame.winfo_manager():
                if frame is self.text_frame:
                    frame.pack(before=self.options_frame, fill="x", padx=10, pady=10)
                else:
                    frame.pack(before=self.action_frame, fill="x", padx=10, pady=10)
            return
        if frame.winfo_manager():
            frame.pack_forget()

    def _refresh_min_height(self) -> None:
        if not self._layout_ready:
            return
        self.update_idletasks()
        min_width, _min_height = self.minsize()
        req_height = self.winfo_reqheight()
        if req_height > 0:
            self.minsize(min_width, req_height)

    def print_file(self) -> None:
        import tempfile
        from ..printing import PrintJobBuilder, PrintSettings

        label = self.device_var.get()
        device = self.device_map.get(label)
        if not device:
            self._queue_error(reporting.ERROR_NO_DEVICE)
            return
        
        path = self.file_var.get().strip()
        text_input = self.text_input.get("1.0", "end").strip()
        
        if not path and not text_input:
            self._queue_error(reporting.ERROR_NO_FILE)
            return
        if path and text_input:
            self._queue_error("error_both_input", detail="Provide either a file path or text, not both.")
            return
        
        connected_device = self.connected_device
        if not connected_device or self.connection is None:
            self._queue_error(reporting.ERROR_PROFILE_NOT_DETECTED)
            return
        
        # Handle text input by creating a temporary file
        temp_path = None
        try:
            if text_input:
                with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as handle:
                    handle.write(text_input)
                    temp_path = handle.name
                path = temp_path
        except Exception as exc:
            self._queue_error(reporting.ERROR_PRINT_FAILED, detail=str(exc), exc=exc)
            return
        
        ext = os.path.splitext(path)[1].lower()
        pdf_pages = None
        pdf_page_gap_mm = 0
        if ext == ".pdf":
            pdf_pages = self.pdf_pages_var.get().strip() or None
            pdf_page_gap_mm = int(self.pdf_gap_var.get())
        settings = PrintSettings(
            text_mode=self.text_mode_var.get(),
            rotate_90_clockwise=self.rotate_90_var.get(),
            blackening=self.darkness_var.get(),
            text_font=self.text_font_var.get().strip() or None,
            text_columns=self.text_columns_var.get(),
            text_wrap=self.text_wrap_var.get(),
            trim_side_margins=self.trim_margins_var.get(),
            trim_top_bottom_margins=self.trim_top_bottom_margins_var.get(),
            pdf_pages=pdf_pages,
            pdf_page_gap_mm=pdf_page_gap_mm,
        )
        builder = PrintJobBuilder(connected_device, settings=settings)

        def done(fut):
            try:
                fut.result()
                self._queue_status(reporting.STATUS_PRINT_SENT)
            except Exception as exc:
                self._queue_error(reporting.ERROR_PRINT_FAILED, detail=str(exc), exc=exc)
            finally:
                # Clean up temporary file if it was created
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass

        async def run() -> None:
            self._queue_status(reporting.STATUS_PRINTING)
            job = builder.build_from_file(path)
            await self.connection.send(job)

        self._queue_status(reporting.STATUS_PRINTING)
        self.ble_loop.submit(run(), callback=done)

    def _start_paper_motion(self, action: str) -> None:
        if action not in {"feed", "retract"}:
            return
        self._stop_paper_motion()
        if action == "feed":
            self._queue_status(reporting.STATUS_PAPER_FEED)
        else:
            self._queue_status(reporting.STATUS_PAPER_RETRACT)
        self._paper_motion_action = action
        self._send_paper_motion(action)
        self._schedule_paper_motion()

    def _schedule_paper_motion(self) -> None:
        if not self._paper_motion_action:
            return
        self._paper_motion_job = self.after(PAPER_MOTION_INTERVAL_MS, self._paper_motion_tick)

    def _paper_motion_tick(self) -> None:
        if not self._paper_motion_action:
            return
        self._send_paper_motion(self._paper_motion_action)
        self._schedule_paper_motion()

    def _stop_paper_motion(self, *_args) -> None:
        self._paper_motion_action = None
        if self._paper_motion_job is not None:
            self.after_cancel(self._paper_motion_job)
            self._paper_motion_job = None
        if not self._paper_motion_busy:
            self._restore_status_after_paper_motion()

    def _send_paper_motion(self, action: str) -> None:
        if self._paper_motion_busy:
            return
        label = self.device_var.get()
        device = self.device_map.get(label)
        if not device:
            self._queue_error(reporting.ERROR_NO_DEVICE)
            self._stop_paper_motion()
            return
        connected_device = self.connected_device
        if not connected_device or self.connection is None:
            self._queue_error(reporting.ERROR_PROFILE_NOT_DETECTED)
            self._stop_paper_motion()
            return
        job = PrinterProtocol(connected_device).build_paper_motion(action)
        self._paper_motion_busy = True

        async def run() -> None:
            if action == "feed":
                self._queue_status(reporting.STATUS_PAPER_FEED)
            else:
                self._queue_status(reporting.STATUS_PAPER_RETRACT)
            await self.connection.send(job)

        def done(fut):
            self._paper_motion_busy = False
            try:
                fut.result()
                if not self._paper_motion_action:
                    self._restore_status_after_paper_motion()
            except Exception as exc:
                self._queue_error(reporting.ERROR_PAPER_MOTION_FAILED, detail=str(exc), exc=exc)
                self._stop_paper_motion()

        self.ble_loop.submit(run(), callback=done)

    def _restore_status_after_paper_motion(self) -> None:
        if self.__dict__.get("connected_device") is not None:
            self._queue_status(reporting.STATUS_CONNECT_DONE)
            return
        self._queue_status(reporting.STATUS_IDLE)

    def _set_connected_state(self, connected: bool, device=None) -> None:
        self._connecting = False
        self._stop_animation()
        self._set_bluetooth_icon_idle()
        self.connected_device = None
        if connected and device:
            self.connected_device = device
            self.profile_var.set(device.profile_key.upper())
            self._set_bluetooth_icon_connected()
            self._set_device_combo_state(False)
            self._set_widget_state(self.refresh_button, False)
            self._set_widget_state(self.file_entry, True)
            self._set_widget_state(self.browse_button, True)
            self._set_widget_state(self.text_mode_check, True)
            self._set_widget_state(self.rotate_90_check, True)
            self._set_widget_state(self.darkness_scale, True)
            self._set_widget_state(self.darkness_value_label, True)
            self._set_widget_state(self.text_font_entry, True)
            self._set_widget_state(self.text_font_browse, True)
            self._set_widget_state(self.text_font_clear, True)
            self._set_widget_state(self.text_columns_scale, True)
            self._set_widget_state(self.text_columns_value_label, True)
            self._set_widget_state(self.text_wrap_check, True)
            self._set_widget_state(self.trim_margins_check, True)
            self._set_widget_state(self.trim_top_bottom_margins_check, True)
            self._set_widget_state(self.pdf_pages_entry, True)
            self._set_widget_state(self.pdf_gap_scale, True)
            self._set_widget_state(self.pdf_gap_value_label, True)
            self._set_widget_state(self.feed_button, True)
            self._set_widget_state(self.retract_button, True)
            self._set_widget_state(self.print_button, True)
            self._set_connection_button("Disconnect", True)
            self._configure_text_columns(device.profile)
            return

        self.profile_var.set("")
        self._set_device_combo_state(True)
        self._set_widget_state(self.refresh_button, True)
        self._set_widget_state(self.file_entry, False)
        self._set_widget_state(self.browse_button, False)
        self._set_widget_state(self.text_mode_check, False)
        self._set_widget_state(self.rotate_90_check, False)
        self._set_widget_state(self.darkness_scale, False)
        self._set_widget_state(self.darkness_value_label, False)
        self._set_widget_state(self.text_font_entry, False)
        self._set_widget_state(self.text_font_browse, False)
        self._set_widget_state(self.text_font_clear, False)
        self._set_widget_state(self.text_columns_scale, False)
        self._set_widget_state(self.text_columns_value_label, False)
        self._set_widget_state(self.text_wrap_check, False)
        self._set_widget_state(self.trim_margins_check, False)
        self._set_widget_state(self.trim_top_bottom_margins_check, False)
        self._set_widget_state(self.pdf_pages_entry, False)
        self._set_widget_state(self.pdf_gap_scale, False)
        self._set_widget_state(self.pdf_gap_value_label, False)
        self._set_widget_state(self.feed_button, False)
        self._set_widget_state(self.retract_button, False)
        self._set_widget_state(self.print_button, False)
        self._set_connection_button("Connect", True)
        self._stop_paper_motion()

    def _configure_text_columns(self, profile) -> None:
        width = self._normalized_width(profile.width)
        default_columns = TextConverter.default_columns_for_width(width)
        min_columns = min(15, max(5, int(round(default_columns * 0.5))))
        max_columns = max(min_columns + 1, int(round(default_columns * 1.5)))
        # Keep slider semantics stable: left = more cpl (smaller text), right = fewer cpl (larger text)
        self.text_columns_scale.configure(from_=max_columns, to=min_columns)
        current_columns = self.text_columns_var.get()
        preferred_columns = max(min_columns, min(current_columns, max_columns))
        self.text_columns_var.set(preferred_columns)

    @staticmethod
    def _normalized_width(width: int) -> int:
        if width % 8 == 0:
            return width
        return width - (width % 8)

    def _set_connecting_state(self, connecting: bool) -> None:
        self._connecting = connecting
        if connecting:
            self._set_device_combo_state(False)
            self._set_widget_state(self.refresh_button, False)
            self._set_connection_button("Connecting...", False)
            self._start_animation("connect")
            return
        self._stop_animation()
        if self.connected_device:
            self._set_bluetooth_icon_connected()
            return
        self._set_bluetooth_icon_idle()
        self._set_device_combo_state(True)
        self._set_widget_state(self.refresh_button, True)
        self._set_connection_button("Connect", True)

    def _set_connection_button(self, label: str, enabled: bool) -> None:
        self.connection_button.configure(text=label)
        self._set_widget_state(self.connection_button, enabled)

    @staticmethod
    def _set_widget_state(widget, enabled: bool) -> None:
        if isinstance(widget, ttk.Widget):
            if enabled:
                widget.state(["!disabled"])
            else:
                widget.state(["disabled"])
            return
        state = "normal" if enabled else "disabled"
        widget.configure(state=state)

    def _set_device_combo_state(self, enabled: bool) -> None:
        state = "readonly" if enabled else "disabled"
        self.device_combo.configure(state=state)

    def _start_animation(self, mode: str = "scan") -> None:
        """Animate the bluetooth status icon while scanning/connecting."""
        self._stop_animation()
        self._animation_mode = mode
        self._animation_spinner_index = 0
        self._animate()

    def _animate(self) -> None:
        """Animate bluetooth status by switching fixed-size image frames."""
        frames = self._bt_connect_frames if self._animation_mode == "connect" else self._bt_scan_frames
        if frames:
            idx = self._animation_spinner_index % len(frames)
            self.bluetooth_status_icon.configure(image=frames[idx], text="")
            self._animation_spinner_index = (self._animation_spinner_index + 1) % len(frames)
        else:
            # Fallback animation when image frames are unavailable.
            colors = ["#8a8a8a", "#6b7280", "#4b5563", "#6b7280"]
            if self._animation_mode == "connect":
                colors = ["#60a5fa", "#3b82f6", "#2563eb", "#1d4ed8"]
            idx = self._animation_spinner_index % len(colors)
            self.bluetooth_status_icon.configure(image="", text=self._bt_fallback_symbols[idx], fg=colors[idx])
            self._animation_spinner_index = (self._animation_spinner_index + 1) % len(colors)
        self._animation_job = self.after(220, self._animate)

    def _stop_animation(self) -> None:
        """Stop icon animation; caller applies final icon state."""
        if self._animation_job is not None:
            self.after_cancel(self._animation_job)
            self._animation_job = None

    def _set_bluetooth_icon_idle(self) -> None:
        self._stop_animation()
        if self._bt_icon_idle is not None:
            self.bluetooth_status_icon.configure(image=self._bt_icon_idle, text="")
            return
        self.bluetooth_status_icon.configure(image="", text="ᛒ", fg="#8a8a8a")

    def _set_bluetooth_icon_connected(self) -> None:
        self._stop_animation()
        if self._bt_icon_connected is not None:
            self.bluetooth_status_icon.configure(image=self._bt_icon_connected, text="")
            return
        self.bluetooth_status_icon.configure(image="", text="ᛒ", fg="#2563eb")

    def _load_bluetooth_icon_states(self) -> None:
        """Load bluetooth icon image and create fixed-size states for idle/scan/connect/connected."""
        icon_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "data", "icons", "bluetooth.png")
        )
        if not os.path.isfile(icon_path):
            return
        try:
            resampling = getattr(Image, "Resampling", Image)
            base = Image.open(icon_path).convert("RGBA").resize((22, 22), resampling.LANCZOS)
        except Exception:
            return

        self._bt_icon_idle = ImageTk.PhotoImage(self._tinted_bluetooth_icon(base, "#7a7a7a"))
        self._bt_icon_connected = ImageTk.PhotoImage(self._tinted_bluetooth_icon(base, "#2563eb"))

        scan_colors = ["#8a8a8a", "#6b7280", "#4b5563", "#6b7280"]
        connect_colors = ["#60a5fa", "#3b82f6", "#2563eb", "#1d4ed8"]
        self._bt_scan_frames = [ImageTk.PhotoImage(self._tinted_bluetooth_icon(base, color)) for color in scan_colors]
        self._bt_connect_frames = [ImageTk.PhotoImage(self._tinted_bluetooth_icon(base, color)) for color in connect_colors]

        self.bluetooth_status_icon.configure(image=self._bt_icon_idle, text="")

    @staticmethod
    def _tinted_bluetooth_icon(base: Image.Image, color: str) -> Image.Image:
        gray = ImageOps.grayscale(base)
        tinted = ImageOps.colorize(gray, black="#000000", white=color).convert("RGBA")
        tinted.putalpha(base.split()[-1])
        return tinted

    def _on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._stop_paper_motion()
        try:
            if self.connection is not None:
                future = self.ble_loop.submit(self.connection.disconnect())
                future.result(timeout=2.0)
        except Exception:
            pass
        finally:
            self.ble_loop.shutdown()
            self.destroy()


def main() -> int:
    app = TiMiniPrintGUI()
    app.mainloop()
    return 0
