"""Independent Tkinter dashboard; optional GUI imports stay lazy."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
import threading
import time
from typing import Any

from core.control_process import MonitorProcess, test_notification
from core.control_settings import (
    BALANCED_PRESET, NOTIFICATION_KEYS, SECRET_MASK, SENSITIVE_PRESET, THRESHOLDS,
    read_env, update_env, validate_notifications, validate_thresholds,
)
from core.monitor_status import explain_status
from core.roi import roi_from_settings, roi_to_env
from ui.camera_roi import CameraROI


class ControlPanel:
    def __init__(self, root: Any, project: Path, env_path: Path, defaults: Any, preview: bool = False) -> None:
        import tkinter as tk
        from tkinter import messagebox, ttk

        self.tk, self.ttk, self.dialog = tk, ttk, messagebox
        self.root, self.env_path, self.defaults, self.preview = root, env_path, defaults, preview
        self.controller = MonitorProcess(project, env_path)
        self.results: Queue[tuple[str, bool]] = Queue()
        self.notification_busy = False
        self.closing = False
        self.restart_pending = False
        self.roi_start_pending = False
        self.monitor_after_roi = False
        self.preview_visible = False
        self.last_received = 0.0
        self.last_state = ""
        self.last_notify = None
        self.snapshot: dict[str, Any] = {"phase": "stopped"}
        self.fields: dict[str, Any] = {}
        self.entries: dict[str, Any] = {}
        self.test_buttons = []
        self.scrollables = []
        self.colors = dict(bg="#0B1220", card="#152238", text="#F1F5F9", muted="#B8C5D6",
                           green="#86EFAC", red="#FDA4AF", amber="#FDE68A")
        root.title("Posture Alarm | 姿態警報控制面板")
        width = min(1040, max(760, root.winfo_screenwidth() - 60))
        height = min(980, max(540, root.winfo_screenheight() - 100))
        root.geometry(f"{width}x{height}")
        root.minsize(760, 540)
        root.configure(bg=self.colors["bg"])
        self._style()
        outer = ttk.Frame(root, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="POSTURE ALARM", style="Brand.TLabel").pack(anchor="w")
        ttk.Label(outer, text="姿態監控控制面板", style="Heading.TLabel").pack(anchor="w", pady=(2, 4))
        note = "介面預覽：未連接硬體、不發送通知、不儲存設定" if preview else "即時監控 · 通知管理 · 跌倒閾值調整"
        ttk.Label(outer, text=note, style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        self.banner = ttk.Label(outer, text="監控已停止", style="State.TLabel", padding=8)
        self.banner.pack(fill="x", pady=(0, 8))
        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(0, 8))
        self.start_button = ttk.Button(actions, text="開始監控", command=self._start, style="Accent.TButton")
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button = ttk.Button(actions, text="停止監控", command=self._stop)
        self.stop_button.pack(side="left", padx=(0, 8))
        self.alarm_button = ttk.Button(actions, text="測試 LED／蜂鳴器", command=self._test_alarm)
        self.alarm_button.pack(side="left")
        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True)
        status_tab = self._scrollable_tab("即時狀態")
        self._build_status(status_tab)
        notification_tab = self._scrollable_tab("LINE / Discord")
        self._build_notifications(notification_tab)
        threshold_tab = ttk.Frame(self.notebook)
        self.notebook.add(threshold_tab, text="跌倒閾值")
        self._build_thresholds(threshold_tab)
        camera_form = self._scrollable_tab("鏡頭／ROI", stretch=True)
        self.camera_tab = camera_form.master.master
        self.camera_view = CameraROI(camera_form, self._open_camera, self._confirm_roi,
                                     self._hide_camera, self._preview_request)
        self.notebook.bind("<<NotebookTabChanged>>", self._tab_changed)
        footer = ttk.Frame(outer)
        # 先保留底部按鈕空間，避免 Notebook 內容較高時把儲存按鈕擠出視窗。
        footer.pack(side="bottom", before=self.notebook, fill="x", pady=(8, 0))
        self.feedback = tk.StringVar(value="設定尚未變更。開始監控會使用已儲存的設定。")
        ttk.Label(footer, textvariable=self.feedback, wraplength=650, style="Muted.TLabel").pack(anchor="w")
        save_bar = ttk.Frame(footer)
        save_bar.pack(fill="x", pady=(8, 0))
        self.save_button = ttk.Button(save_bar, text="儲存設定", command=self._save)
        self.save_button.pack(side="left", padx=(0, 8))
        self.restart_button = ttk.Button(save_bar, text="儲存並重新啟動監控", command=self._restart)
        self.restart_button.pack(side="left", padx=(0, 8))
        self.reload_button = ttk.Button(save_bar, text="重新載入設定", command=self._reload)
        self.reload_button.pack(side="left")
        for canvas, form in self.scrollables:
            self._bind_scroll_widgets(canvas, form)
        self._load_settings()
        for variable in self.fields.values():
            variable.trace_add("write", self._on_edit)
        if preview:
            for button in (self.save_button, self.restart_button, self.reload_button, *self.test_buttons):
                button.state(["disabled"])
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._record("介面預覽" if preview else "控制面板已就緒，尚未啟動監控")
        self._refresh()

    def _style(self) -> None:
        from tkinter import font
        ttk = self.ttk
        style = ttk.Style(self.root)
        style.theme_use("clam")
        families = set(font.families(self.root))
        family = next((name for name in ("Microsoft JhengHei UI", "Noto Sans CJK TC", "Noto Sans CJK SC") if name in families), "TkDefaultFont")
        style.configure(".", font=(family, 11), background=self.colors["bg"], foreground=self.colors["text"])
        style.configure("TFrame", background=self.colors["bg"])
        style.configure("TLabel", background=self.colors["bg"])
        style.configure("Muted.TLabel", foreground=self.colors["muted"])
        style.configure("Brand.TLabel", foreground=self.colors["green"], font=(family, 10, "bold"))
        style.configure("Heading.TLabel", font=(family, 18, "bold"))
        style.configure("State.TLabel", font=(family, 13, "bold"), background=self.colors["card"])
        style.configure("Value.TLabel", font=(family, 20, "bold"))
        style.configure("TButton", padding=(12, 8), background="#253751", foreground=self.colors["text"])
        style.map("TButton", background=[("active", "#354D6B")], foreground=[("disabled", "#8190A3")])
        style.configure("Accent.TButton", background=self.colors["green"], foreground="#10231B")
        style.map("Accent.TButton", background=[("active", "#BBF7D0"), ("disabled", "#253751")])
        style.configure("TNotebook", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 10), background="#1E2E46")
        style.map("TNotebook.Tab", background=[("selected", "#334863")])
        style.configure("TEntry", fieldbackground="#1E2E46", foreground=self.colors["text"], padding=6)
        style.configure("Treeview", background=self.colors["card"], fieldbackground=self.colors["card"],
                        foreground=self.colors["text"], rowheight=28, borderwidth=0)
        style.configure("Treeview.Heading", background="#253751", foreground=self.colors["text"])
        style.map("Treeview", background=[("selected", "#385572")])

    def _scrollable_tab(self, title: str, stretch: bool = False) -> Any:
        container = self.ttk.Frame(self.notebook)
        self.notebook.add(container, text=title)
        canvas = self.tk.Canvas(container, bg=self.colors["bg"], highlightthickness=0)
        scroll = self.ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        form = self.ttk.Frame(canvas, padding=12)
        window = canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        def fit(event: Any) -> None:
            options = {"width": event.width}
            if stretch:
                options["height"] = max(event.height, form.winfo_reqheight())
            canvas.itemconfigure(window, **options)
        canvas.bind("<Configure>", fit)
        self.scrollables.append((canvas, form))
        return form

    def _bind_scroll_widgets(self, canvas: Any, form: Any) -> None:
        def wheel(event: Any) -> str:
            canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return "break"

        def bind(widget: Any) -> None:
            widget.bind("<MouseWheel>", wheel)
            widget.bind("<Button-4>", lambda _: canvas.yview_scroll(-1, "units"))
            widget.bind("<Button-5>", lambda _: canvas.yview_scroll(1, "units"))
            if widget.winfo_class() == "TEntry":
                widget.bind("<FocusIn>", lambda event: self._scroll_to_entry(event.widget, canvas))
            for child in widget.winfo_children():
                bind(child)
        bind(form)

    def _build_status(self, parent: Any) -> None:
        ttk, tk = self.ttk, self.tk
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        cards = ttk.Frame(parent)
        cards.grid(row=0, column=0, columnspan=2, sticky="ew")
        cards.columnconfigure((0, 1), weight=1)
        self.temperature = tk.StringVar(value="— °C")
        self.humidity = tk.StringVar(value="— %")
        for column, title, variable in ((0, "溫度", self.temperature), (1, "濕度", self.humidity)):
            frame = ttk.Frame(cards, padding=(0, 0, 12, 8))
            frame.grid(row=0, column=column, sticky="ew")
            ttk.Label(frame, text=title, style="Muted.TLabel").pack(anchor="w")
            ttk.Label(frame, textvariable=variable, style="Value.TLabel").pack(anchor="w")
        self.health = tk.StringVar(value="相機：未啟動　｜　GPIO：未啟動　｜　感測器：未啟動")
        ttk.Label(parent, textvariable=self.health, wraplength=880).grid(row=1, column=0, columnspan=2, sticky="w", pady=6)
        self.outputs = tk.StringVar(value="LED1：關　 LED2：關　 蜂鳴器：關")
        ttk.Label(parent, textvariable=self.outputs, style="Muted.TLabel", wraplength=880).grid(row=2, column=0, columnspan=2, sticky="w")
        self.reason = tk.StringVar(value="等待開始監控")
        ttk.Label(parent, textvariable=self.reason, wraplength=880, foreground=self.colors["amber"]).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        self.metrics = ttk.Treeview(parent, columns=("name", "value", "limit"), show="headings", height=8)
        for key, title, width in (("name", "診斷項目", 210), ("value", "目前值", 170), ("limit", "執行中的門檻／說明", 360)):
            self.metrics.heading(key, text=title)
            self.metrics.column(key, width=width, minwidth=100, stretch=True)
        self.metrics.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        parent.rowconfigure(4, weight=1)
        for name in ("person", "angle", "diff", "speed", "drop", "score", "event", "bed"):
            self.metrics.insert("", "end", iid=name, values=("—", "—", "—"))
        ttk.Label(parent, text="最近事件", style="Muted.TLabel").grid(row=5, column=0, sticky="w")
        self.events = ttk.Treeview(parent, columns=("time", "message"), show="headings", height=3)
        self.events.heading("time", text="時間")
        self.events.heading("message", text="事件")
        self.events.column("time", width=90, stretch=False)
        self.events.column("message", width=620)
        self.events.grid(row=6, column=0, columnspan=2, sticky="ew")

    def _build_notifications(self, parent: Any) -> None:
        ttk, tk = self.ttk, self.tk
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="憑證以遮罩顯示，僅儲存在本機 demo.env。", style="Muted.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        labels = ("LINE Channel Access Token", "LINE Target ID（使用者／群組）", "Discord Webhook URL")
        for row, (key, label) in enumerate(zip(NOTIFICATION_KEYS, labels), 1):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=8)
            self.fields[key] = tk.StringVar()
            entry = ttk.Entry(parent, textvariable=self.fields[key], show=SECRET_MASK, width=34)
            entry.grid(row=row, column=1, sticky="ew", pady=8)
            self.entries[key] = entry
        buttons = ttk.Frame(parent)
        buttons.grid(row=4, column=0, columnspan=2, sticky="w", pady=(14, 10))
        for channel, label in (("line", "發送 LINE 測試"), ("discord", "發送 Discord 測試")):
            button = ttk.Button(buttons, text=label, command=lambda channel=channel: self._test_notification(channel))
            button.pack(side="left", padx=(0, 10))
            self.test_buttons.append(button)
        ttk.Label(parent, text="測試會使用欄位中的內容，並實際發送一則訊息。\nLINE 須同時填入 Token 與 Target ID；空白或不完整時停用。\n儲存設定後，執行中的監控須重新啟動才會套用。",
                  wraplength=700, style="Muted.TLabel").grid(row=5, column=0, columnspan=2, sticky="w", pady=8)
        self.notification_status = tk.StringVar(value="監控尚未啟動；通知設定尚未套用")
        ttk.Label(parent, textvariable=self.notification_status, wraplength=700).grid(row=6, column=0, columnspan=2, sticky="w", pady=12)

    def _build_thresholds(self, parent: Any) -> None:
        ttk, tk = self.ttk, self.tk
        bar = ttk.Frame(parent, padding=12)
        bar.pack(fill="x")
        ttk.Button(bar, text="平衡／恢復預設", command=lambda: self._preset(BALANCED_PRESET, "平衡")).pack(side="left", padx=(0, 8))
        ttk.Button(bar, text="敏感（測試用）", command=lambda: self._preset(SENSITIVE_PRESET, "敏感")).pack(side="left")
        ttk.Label(bar, text="先編輯草稿，再儲存並重新啟動。", style="Muted.TLabel").pack(side="left", padx=12)
        canvas = tk.Canvas(parent, bg=self.colors["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        form = ttk.Frame(canvas, padding=(14, 4, 14, 14))
        window = canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        form.columnconfigure(2, weight=1)
        for row, spec in enumerate(THRESHOLDS):
            ttk.Label(form, text=spec.label).grid(row=row, column=0, sticky="w", pady=8, padx=(0, 12))
            self.fields[spec.key] = tk.StringVar()
            entry = ttk.Entry(form, textvariable=self.fields[spec.key], width=9)
            entry.grid(row=row, column=1, sticky="w", padx=(0, 12))
            self.entries[spec.key] = entry
            ttk.Label(form, text=spec.hint, wraplength=365, style="Muted.TLabel").grid(row=row, column=2, sticky="w", pady=8)
            entry.bind("<FocusIn>", lambda event, canvas=canvas: self._scroll_to_entry(event.widget, canvas))
        ttk.Label(form, text="敏感預設僅供現場調整起點，尚未針對你的場地驗證。\n原有事件條件、床區抑制及確認流程仍會影響是否報警。",
                  wraplength=760, foreground=self.colors["amber"]).grid(row=len(THRESHOLDS), column=0, columnspan=3, sticky="w", pady=14)
        for widget in (canvas, form, *form.winfo_children()):
            widget.bind("<MouseWheel>", lambda event: canvas.yview_scroll(-1 if event.delta > 0 else 1, "units"))
            widget.bind("<Button-4>", lambda _: canvas.yview_scroll(-1, "units"))
            widget.bind("<Button-5>", lambda _: canvas.yview_scroll(1, "units"))

    def _scroll_to_entry(self, entry: Any, canvas: Any) -> None:
        total = max(1, entry.master.winfo_height())
        top = canvas.canvasy(0)
        y = entry.winfo_y()
        if y < top or y + entry.winfo_height() > top + canvas.winfo_height():
            canvas.yview_moveto(max(0, y - 30) / total)

    def _load_settings(self) -> None:
        self.disk_values = {} if self.preview else read_env(self.env_path)
        values = {key: self.disk_values.get(key, str(getattr(self.defaults, key, ""))) for key in self.fields}
        if self.preview:
            values.update(dict.fromkeys(NOTIFICATION_KEYS, ""))
        # 顯示實際生效的事件窗，沿用 config.py 既有的確認時間保護。
        values["FALL_EVENT_WINDOW_SECONDS"] = str(max(float(values["FALL_EVENT_WINDOW_SECONDS"]), float(values["FALL_CONFIRM_SECONDS"])))
        for key, value in values.items():
            self.fields[key].set(value)
        self.saved_form = self._form()
        self.camera_view.load_points(roi_from_settings(self.disk_values, self.defaults))

    def _form(self) -> dict[str, str]:
        return {key: field.get() for key, field in self.fields.items()}

    def _on_edit(self, *_args: Any) -> None:
        if not self.preview:
            self.feedback.set("草稿已變更，尚未儲存或套用。" if self._form() != self.saved_form else "設定與已儲存值相同。")

    def _reload(self) -> None:
        if self._form() != self.saved_form and not self.dialog.askyesno("重新載入", "要捨棄尚未儲存的修改嗎？", parent=self.root):
            return
        try:
            self._load_settings()
            self.feedback.set("已重新載入設定；執行中的監控設定未變更。")
        except (ValueError, OSError):
            self.dialog.showerror("載入失敗", "無法讀取設定檔，請檢查格式與檔案權限。", parent=self.root)

    def _preset(self, values: dict[str, str], name: str) -> None:
        for key, value in values.items():
            self.fields[key].set(value)
        self.feedback.set(f"已載入{name}草稿；尚未儲存或套用。")

    def _save(self) -> bool:
        if self.preview:
            return False
        try:
            form = self._form()
            validated = {**validate_thresholds(form), **validate_notifications(form)}
            changes = {key: value for key, value in validated.items() if form[key] != self.saved_form[key]}
            if changes:
                update_env(self.env_path, changes, expected=self.disk_values)
                self.disk_values = read_env(self.env_path)
                for key, value in changes.items():
                    self.fields[key].set(value)
                self.saved_form = self._form()
            self.feedback.set("已儲存；目前監控仍使用啟動時的設定，重新啟動才會套用。")
            return True
        except ValueError as exc:
            self.dialog.showerror("設定未儲存", str(exc), parent=self.root)
        except OSError:
            self.dialog.showerror("設定未儲存", "無法寫入 demo.env，請檢查檔案／資料夾權限。", parent=self.root)
        return False

    def _start(self) -> None:
        if self.closing:
            return
        if self.preview:
            self._apply_snapshot({"phase": "running", "camera_ok": False, "state": "PREVIEW"})
            return
        if self._form() != self.saved_form and not self.dialog.askyesno("尚未儲存", "欄位修改尚未儲存。仍要使用已儲存設定開始監控嗎？", parent=self.root):
            return
        if self.controller.busy and (self.controller.mode != "camera" or self.controller.stopping):
            return
        if self.defaults.GUI_ROI_ON_START:
            self.roi_start_pending = True
            self.notebook.select(self.camera_tab)
            self._open_camera()
            self.camera_view.status.set("啟動前請確認床區：可沿用已存 ROI，或重新標記四角，再按「確認 ROI 並開始監控」。")
            return
        if self.controller.busy:
            self.monitor_after_roi = True
            self.controller.stop()
            return
        self._launch_monitor()

    def _launch_monitor(self) -> None:
        try:
            self.controller.start()
            self.last_state, self.last_notify = "", None
            self._apply_snapshot({"phase": "starting"})
            self._record("正在啟動監控")
            self._preview_request()
        except (RuntimeError, ValueError, OSError):
            self.dialog.showerror("無法啟動", "請確認設定檔格式、執行環境，以及監控是否已停止。", parent=self.root)

    def _stop(self) -> None:
        self.restart_pending = False
        self.roi_start_pending = self.monitor_after_roi = False
        self.camera_view.clear("正在停止鏡頭／監控，等待資源釋放。")
        if self.preview:
            self._apply_snapshot({"phase": "stopped"})
            return
        self.controller.stop()
        self.feedback.set("正在停止，等待目前影像／通知操作結束並釋放硬體。")

    def _restart(self) -> None:
        if self.controller.busy and self.controller.mode == "alarm_test":
            self.dialog.showinfo("硬體測試中", "請先等待硬體測試完成。", parent=self.root)
            return
        if not self._save():
            return
        self.roi_start_pending = self.monitor_after_roi = False
        if self.controller.busy:
            self.restart_pending = True
            self.controller.stop()
            self.feedback.set("設定已儲存；停止完成後會重新啟動監控。")
        else:
            self._start()

    def _tab_changed(self, _event: Any = None) -> None:
        if self.closing:
            return
        if self.notebook.select() == str(self.camera_tab):
            self._open_camera()
        else:
            self.preview_visible = False
            self._preview_request()
            self.camera_view.clear()
            # 單純 ROI 預覽可釋放鏡頭；真正監控則只停止傳送預覽影像。
            if self.controller.busy and self.controller.mode == "camera" and not self.monitor_after_roi:
                self.roi_start_pending = False
                self.controller.stop()

    def _open_camera(self) -> None:
        if self.closing:
            return
        self.preview_visible = True
        self.notebook.select(self.camera_tab)
        if self.preview:
            self.camera_view.status.set("介面預覽模式不會開啟實體相機。")
            return
        if self.controller.stopping or (self.controller.busy and self.controller.mode == "alarm_test"):
            self.camera_view.status.set("請等待目前監控／測試停止完成，再開啟鏡頭。")
            return
        try:
            if not self.controller.busy:
                self.camera_view.load_points(roi_from_settings(read_env(self.env_path), self.defaults))
                self.controller.start("camera")
                self._apply_snapshot({"phase": "camera_preview", "camera_ok": False})
                self.camera_view.status.set("正在開啟鏡頭；目前僅預覽，尚未開始監控。")
            self._preview_request()
        except (ValueError, OSError, RuntimeError):
            self.camera_view.clear("鏡頭無法啟動，請檢查設定或是否被其他程式使用。")

    def _preview_request(self) -> None:
        if self.preview or self.closing:
            return
        canvas = self.camera_view.canvas
        self.controller.send_command({"command": "preview", "enabled": self.preview_visible,
                                      "width": canvas.winfo_width(), "height": canvas.winfo_height()})

    def _hide_camera(self) -> None:
        self.notebook.select(0)
        self.preview_visible = False
        self._preview_request()
        self.camera_view.clear("鏡頭畫面已隱藏；若監控已啟動，仍會繼續辨識。")

    def _confirm_roi(self, start: bool) -> None:
        if self.preview or self.closing:
            self.camera_view.status.set("介面預覽不會儲存 ROI 或啟動監控。")
            return
        if not self.controller.busy or self.controller.stopping or self.controller.mode not in {"camera", "monitor"}:
            self.camera_view.status.set("請先開啟鏡頭，等待即時影像後再確認 ROI。")
            return
        try:
            points = self.camera_view.selection()
            update_env(self.env_path, roi_to_env(points), expected=self.disk_values)
            self.disk_values = read_env(self.env_path)
        except ValueError as exc:
            self.dialog.showerror("ROI 未儲存", str(exc), parent=self.root)
            return
        except OSError:
            self.dialog.showerror("ROI 未儲存", "無法寫入 demo.env，請檢查檔案權限。", parent=self.root)
            return
        self.camera_view.editing = False
        self.camera_view.draft = []
        self.camera_view.load_points(points)
        self._record("床區 ROI 已儲存")
        if start and self.controller.mode == "camera":
            self.roi_start_pending = False
            self.monitor_after_roi = True
            self.controller.stop()
            self.camera_view.clear("ROI 已儲存，等待預覽釋放鏡頭後開始監控…")
        else:
            sent = self.controller.send_command({"command": "roi", "points": points})
            self.camera_view.status.set("ROI 已儲存，等待下一幀套用…" if sent else "ROI 已儲存，但尚未套用；請重新啟動監控。")

    def _test_alarm(self) -> None:
        if self.controller.busy:
            return
        if self.preview:
            self.feedback.set("介面預覽不會操作硬體。")
            return
        if self.dialog.askyesno("測試實體警報", "將依已儲存的 GPIO 設定開啟 LED 與蜂鳴器約 1 秒，可能很大聲。繼續嗎？", parent=self.root):
            try:
                self.controller.start("alarm_test")
                self._record("開始警報測試")
            except (ValueError, RuntimeError, OSError):
                self.dialog.showerror("無法測試", "請檢查設定檔或執行環境。", parent=self.root)

    def _test_notification(self, channel: str) -> None:
        if self.preview or self.notification_busy:
            return
        try:
            values = validate_notifications(self._form())
        except ValueError as exc:
            self.dialog.showerror("通知設定", str(exc), parent=self.root)
            return
        configured = bool(values[NOTIFICATION_KEYS[0]] and values[NOTIFICATION_KEYS[1]]) if channel == "line" else bool(values[NOTIFICATION_KEYS[2]])
        if not configured:
            self.dialog.showinfo("尚未設定", "請先填入此通知管道需要的欄位。", parent=self.root)
            return
        label = "LINE" if channel == "line" else "Discord"
        if not self.dialog.askyesno("發送測試通知", f"要使用欄位中的設定，實際發送一則 {label} 測試通知嗎？", parent=self.root):
            return
        self.notification_busy = True
        self.feedback.set(f"正在發送 {label} 測試通知…")

        def send() -> None:
            try:
                result = test_notification(channel, values)
            except Exception:
                result = False
            self.results.put((label, result))

        threading.Thread(target=send, daemon=True).start()

    def _record(self, message: str) -> None:
        self.events.insert("", 0, values=(datetime.now().strftime("%H:%M:%S"), message))
        for item in self.events.get_children()[50:]:
            self.events.delete(item)

    def _apply_snapshot(self, data: dict[str, Any]) -> None:
        self.snapshot = data
        self.last_received = time.monotonic()
        phase = data.get("phase", "stopped")
        state = data.get("state", "")
        active = phase in {"running", "alarm_test"}
        title = {"starting": "正在啟動監控…", "stopped": "監控已停止", "camera_preview": "鏡頭／ROI 預覽 · 尚未開始監控",
                 "alarm_test": "正在測試警報", "error": "啟動或監控失敗"}.get(phase, f"監控中 · {state}")
        if self.preview:
            title = "介面預覽 · 未連接硬體"
        self.banner.configure(text=title, foreground=self.colors["red"] if state == "FALLEN" or phase == "error" else self.colors["text"])
        self.reason.set(explain_status(data))
        if state and state != self.last_state:
            self._record(f"姿態狀態：{state}")
            self.last_state = state
        if data.get("notification_result") is not None and data["notification_result"] != self.last_notify:
            self.last_notify = data["notification_result"]
            self._record("至少一個通知管道已送出" if self.last_notify.get("message_sent") else "通知未送出（未設定或傳送失敗）")
        for key, variable, suffix in (("temperature_c", self.temperature, "°C"), ("humidity_pct", self.humidity, "%")):
            value = data.get(key)
            variable.set(f"{value:.1f} {suffix}" if isinstance(value, (int, float)) else f"— {suffix}")
        if active:
            gpio = "模擬／實體未輸出" if data.get("gpio_simulated", True) else "已初始化／無電氣回授"
            age = data.get("sensor_age_seconds")
            sensor = "尚無有效讀值" if age is None else f"最近有效值 {age:.1f} 秒前"
            if data.get("sensor_error"):
                sensor += "／讀取錯誤"
            self.health.set(f"相機：{'影像接收中' if data.get('camera_ok') else '等待影像'}　｜　GPIO：{gpio}\n感測器後端：{data.get('sensor_backend', '—')} · {sensor}")
        elif phase == "camera_preview":
            self.health.set(f"相機：{'預覽接收中' if data.get('camera_ok') else '等待影像'}　｜　GPIO／感測器：尚未啟動")
        else:
            self.health.set("相機：未啟動　｜　GPIO：未啟動　｜　感測器：未啟動")
        on_off = lambda key: "開" if active and data.get(key) else "關"
        hardware = data.get("hardware", {})
        self.outputs.set(
            f"輸出命令　LED1(GPIO{hardware.get('led_pin', '—')})：{on_off('led_active')}　"
            f"LED2(GPIO{hardware.get('led_2_pin', '—')})：{on_off('led_2_active')}　"
            f"蜂鳴器(GPIO{hardware.get('buzzer_pin', '—')})：{on_off('buzzer_active')} "
            f"／ {hardware.get('buzzer_frequency', '—')} Hz"
        )
        self.notification_status.set(f"執行中設定　LINE：{'已設定' if data.get('line_configured') else '未設定／停用'}　 Discord：{'已設定' if data.get('discord_configured') else '未設定／停用'}")
        limits = data.get("thresholds", {})
        rows = {
            "person": ("人體可見度檢查", "通過" if data.get("person_present") else "未通過／尚無資料", "未通過時不做跌倒分類"),
            "angle": ("身體角度（度）", data.get("trunk_angle_deg"), f">= {limits.get('FALL_TRUNK_ANGLE_THRESHOLD_DEG', '—')}"),
            "diff": ("髖肩高度差", data.get("hip_shoulder_diff"), f"<= {limits.get('FALL_HIP_SHOULDER_DIFF_THRESHOLD', '—')}"),
            "speed": ("髖部移動速度", data.get("hip_speed"), f">= {limits.get('FALL_SPEED_THRESHOLD', '—')} 且滿足事件角度條件"),
            "drop": ("單幀髖部下降", data.get("hip_drop"), f">= {limits.get('FALL_EVENT_MIN_HIP_DROP', '—')} 可形成事件"),
            "score": ("平滑跌倒分數", data.get("fall_score"), f">= {limits.get('FALL_SCORE_THRESHOLD', '—')}"),
            "event": ("本幀／保留中的事件", f"{bool(data.get('has_fall_event'))} / {bool(data.get('recent_event'))}", f"保留 {limits.get('FALL_EVENT_WINDOW_SECONDS', '—')} 秒"),
            "bed": ("床區／安全躺臥抑制", f"{bool(data.get('in_bed_roi'))} / {bool(data.get('safe_lying_detected'))}", "沿用原有床區判斷"),
        }
        for key, (name, value, limit) in rows.items():
            self.metrics.item(key, values=(name, "—" if value is None else value, limit))

    def _refresh(self) -> None:
        for message in self.controller.drain():
            if message.get("type") == "status":
                self._apply_snapshot(message["data"])
            elif message.get("type") == "error":
                self.monitor_after_roi = False
                self.camera_view.clear("鏡頭／監控發生錯誤，請檢查相機連線與設定。")
                self._apply_snapshot({"phase": "error"})
                self.feedback.set(f"監控失敗（{message.get('error_type', 'Error')}）。請檢查相機、模型路徑或執行 CLI 查看錯誤。")
                self._record("監控出現錯誤，請檢查相機與模型")
            elif message.get("type") == "exit":
                self.camera_view.clear("鏡頭／監控已停止；可再次開啟預覽。")
                if message.get("code") == 0:
                    self._apply_snapshot({"phase": "stopped"})
                    self._record("監控／測試已停止，硬體資源已釋放")
                else:
                    self._apply_snapshot({"phase": "error"})
                if self.monitor_after_roi and message.get("code") == 0 and not self.closing:
                    self.monitor_after_roi = False
                    self._launch_monitor()
                elif self.restart_pending and not self.closing:
                    self.restart_pending = False
                    self.last_state, self.last_notify = "", None
                    self._start()
            elif message.get("type") == "roi_applied":
                if [tuple(point) for point in message.get("points", [])] == self.camera_view.points:
                    self.camera_view.status.set("ROI 已儲存並套用。可隱藏畫面；監控中仍會持續辨識。" if self.controller.mode == "monitor"
                                                else "ROI 已儲存。請按「確認 ROI 並開始監控」開始辨識。")
            elif message.get("type") in {"preview_error", "command_error"}:
                self.camera_view.status.set("預覽或 ROI 套用失敗；原有監控不受預覽影響，請重試或重啟。")
        frame = self.controller.take_frame()
        if frame is not None and self.preview_visible and self.controller.busy and not self.controller.stopping:
            self.camera_view.receive(frame)
        if self.camera_view.photo is not None and not self.camera_view.fresh:
            self.camera_view.status.set("影像超過 3 秒未更新，已停用標記／確認；請等待恢復或重試鏡頭。")
        try:
            while True:
                label, success = self.results.get_nowait()
                self.notification_busy = False
                message = f"{label} 測試{'已送出' if success else '失敗，請檢查憑證、權限及網路'}"
                self.feedback.set(message)
                self._record(message)
        except Empty:
            pass
        busy = self.controller.busy
        self.start_button.state(["disabled"] if self.closing or (busy and (self.controller.mode != "camera" or self.controller.stopping)) else ["!disabled"])
        self.alarm_button.state(["disabled"] if busy or self.closing else ["!disabled"])
        self.stop_button.state(["!disabled"] if busy and not self.controller.stopping else ["disabled"])
        for button in self.test_buttons:
            button.state(["disabled"] if self.preview or self.notification_busy or self.closing else ["!disabled"])
        for button in (self.save_button, self.restart_button, self.reload_button):
            button.state(["disabled"] if self.preview or self.closing else ["!disabled"])
        if self.controller.stopping and time.monotonic() - self.controller.stop_started > 12:
            self.feedback.set("停止仍在等待目前操作完成，視窗保持可操作；請勿重複啟動另一個監控。")
        elif busy and self.last_received and time.monotonic() - self.last_received > 5:
            self.banner.configure(text="監控資料暫未更新，正在等待影像或通知", foreground=self.colors["amber"])
        if self.closing and not busy:
            self.root.destroy()
            return
        self.root.after(min(100, self.defaults.GUI_REFRESH_MS), self._refresh)

    def _close(self) -> None:
        if self.closing:
            return
        dirty = (self._form() != self.saved_form or self.camera_view.editing) and not self.preview
        if (self.controller.busy or dirty) and not self.dialog.askyesno("關閉控制面板", "關閉會停止監控；尚未儲存的設定將捨棄。確定關閉？", parent=self.root):
            return
        self.closing = True
        self.restart_pending = False
        self.roi_start_pending = self.monitor_after_roi = False
        self.controller.stop()
