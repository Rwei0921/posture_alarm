"""Tk camera canvas with normalized four-corner bed-ROI editing."""

from __future__ import annotations

import time
from typing import Any, Callable

from core.roi import image_point, validate_points


class CameraROI:
    def __init__(self, parent: Any, open_camera: Callable[[], None],
                 save: Callable[[bool], None], hide: Callable[[], None], resize: Callable[[], None]) -> None:
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.parent, self.resize = tk, parent, resize
        self.points: list[tuple[float, float]] = []
        self.active_points: list[tuple[float, float]] = []
        self.draft: list[tuple[float, float]] = []
        self.editing = False
        self.photo = None
        self.bounds = (0.0, 0.0, 0.0, 0.0)
        self.last_frame = 0.0
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1, minsize=60)
        guide = ttk.Label(parent, text="床區 ROI：依序點選 左上 → 右上 → 右下 → 左下。\n綠線＝執行中範圍；黃線＝尚未儲存的草稿。黑邊不能標記。",
                          style="Muted.TLabel", wraplength=700)
        guide.grid(row=0, column=0, sticky="ew", pady=(4, 6))
        self.canvas = tk.Canvas(parent, bg="#080E18", highlightthickness=1,
                                highlightbackground="#354D6B", takefocus=True, cursor="crosshair",
                                width=640, height=200)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<BackSpace>", lambda _: self.undo())
        self.canvas.bind("<Escape>", lambda _: self.cancel())
        self.canvas.bind("<Configure>", self._configure)
        bar = ttk.Frame(parent)
        bar.grid(row=2, column=0, sticky="ew", pady=6)
        buttons = (("開啟／重試鏡頭", open_camera, 0, 0), ("重新標記四角", self.mark, 0, 1),
                   ("退一步", self.undo, 0, 2), ("取消草稿", self.cancel, 0, 3),
                   ("儲存／套用 ROI", lambda: save(False), 1, 0),
                   ("確認 ROI 並開始監控", lambda: save(True), 1, 1),
                   ("隱藏鏡頭畫面", hide, 1, 3))
        for label, command, row, column in buttons:
            button = ttk.Button(bar, text=label, command=command)
            button.grid(row=row, column=column, columnspan=2 if row == 1 and column == 1 else 1,
                        sticky="ew", padx=(0, 6), pady=2)
        self.status = tk.StringVar(value="尚未開啟相機。選取此分頁即可預覽；設定期間尚未監控。")
        ttk.Label(parent, textvariable=self.status, wraplength=700, foreground="#FDE68A").grid(
            row=3, column=0, sticky="ew", pady=(0, 4))
        self._draw()

    @property
    def fresh(self) -> bool:
        return self.photo is not None and time.monotonic() - self.last_frame < 3.0

    def load_points(self, points: list[tuple[float, float]]) -> None:
        self.points = list(points)
        if not self.editing:
            self._draw()

    def receive(self, message: dict[str, Any]) -> None:
        try:
            self.photo = self.tk.PhotoImage(master=self.canvas, data=message["png"], format="png")
        except (self.tk.TclError, KeyError):
            self.clear("無法顯示預覽，請確認 Tk 8.6 以上版本。監控不受影響。")
            return
        self.last_frame = float(message.get("captured_at", 0))
        self.active_points = [tuple(point) for point in message.get("points", [])]
        self._draw()

    def clear(self, message: str = "鏡頭畫面已隱藏／停止。") -> None:
        self.photo = None
        self.last_frame = 0.0
        self.active_points = []
        self.status.set(message)
        self._draw()

    def _configure(self, _event: Any) -> None:
        self._draw()
        self.resize()

    def _draw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width, height = max(1, canvas.winfo_width()), max(1, canvas.winfo_height())
        self.bounds = (0.0, 0.0, 0.0, 0.0)
        if self.photo is None:
            canvas.create_text(width / 2, height / 2, text="等待鏡頭畫面…", fill="#B8C5D6")
            return
        # Tk 原生 PNG 免額外套件；不足空間時用整數縮小，確保黑邊與點選座標一致。
        factor = max(1, -(-self.photo.width() // width), -(-self.photo.height() // height))
        self.display_photo = self.photo.subsample(factor) if factor > 1 else self.photo
        image_width, image_height = self.display_photo.width(), self.display_photo.height()
        left, top = (width - image_width) / 2, (height - image_height) / 2
        self.bounds = (left, top, float(image_width), float(image_height))
        canvas.create_image(left, top, image=self.display_photo, anchor="nw")
        for points, color, label in ((self.active_points, "#86EFAC", "已套用"),
                                     (self.draft if self.editing else [], "#FDE68A", "草稿")):
            coords = [(left + x * image_width, top + y * image_height) for x, y in points]
            if len(coords) > 1:
                canvas.create_line(*[v for point in coords + (coords[:1] if len(coords) == 4 else []) for v in point],
                                   fill=color, width=3, dash=(6, 3) if label == "草稿" else ())
            for index, (x, y) in enumerate(coords, 1):
                canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill=color, outline="#080E18")
                if label == "草稿" or not self.editing:
                    text = canvas.create_text(x + 10, y + 10, text=f"{index}" if self.editing else f"ROI {index}",
                                              fill=color, anchor="nw")
                    background = canvas.create_rectangle(canvas.bbox(text), fill="#080E18", outline="#080E18")
                    canvas.tag_lower(background, text)

    def mark(self) -> None:
        if not self.fresh:
            self.status.set("請先開啟鏡頭並等到即時影像，再開始標記。")
            return
        self.editing = True
        self.draft = []
        self.status.set("標記草稿 0/4：請點左上角。原有 ROI 在儲存前仍有效。")
        self.canvas.focus_set()
        self._draw()

    def _click(self, event: Any) -> None:
        if not self.editing or not self.fresh or len(self.draft) >= 4:
            return
        point = image_point(event.x, event.y, self.bounds)
        if point is None:
            return
        self.draft.append(point)
        self._draft_status()
        self._draw()

    def _draft_status(self) -> None:
        next_corner = ("左上", "右上", "右下", "左下", "完成")[len(self.draft)]
        self.status.set(f"標記草稿 {len(self.draft)}/4：{next_corner}。完成四角後，按儲存或確認並開始。")

    def undo(self) -> None:
        if self.editing and self.draft:
            self.draft.pop()
            self._draft_status()
            self._draw()

    def cancel(self) -> None:
        self.editing = False
        self.draft = []
        self.status.set("已取消草稿，保留原本的 ROI。")
        self._draw()

    def selection(self) -> list[tuple[float, float]]:
        if not self.fresh:
            raise ValueError("相機影像尚未更新，請先開啟或重試鏡頭。")
        return validate_points(self.draft if self.editing else self.points)
