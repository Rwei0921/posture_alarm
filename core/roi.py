"""Normalized bed-ROI geometry shared by the GUI and camera worker."""

from __future__ import annotations

import math
from typing import Any


ROI_KEYS = {"BED_ROI_ENABLED", "BED_POLYGON_ENABLED", "BED_ROI_SHOW"}
ROI_KEYS.update(f"BED_ROI_{axis}{index}" for axis in "XY" for index in (1, 2))
ROI_KEYS.update(f"BED_POLY_P{index}_{axis}" for index in range(1, 5) for axis in "XY")


def validate_points(points: Any) -> list[tuple[float, float]]:
    try:
        if len(points) != 4 or any(len(point) != 2 for point in points):
            raise ValueError
        result = [(float(x), float(y)) for x, y in points]
        if any(not math.isfinite(value) or not 0 <= value <= 1 for point in result for value in point):
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        raise ValueError("請在影像內依序點選四個角：左上、右上、右下、左下。") from None
    crosses = []
    for index in range(4):
        a, b, c = (result[(index + offset) % 4] for offset in range(3))
        crosses.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
    area = abs(sum(result[i][0] * result[(i + 1) % 4][1]
                   - result[(i + 1) % 4][0] * result[i][1] for i in range(4))) / 2
    if not (all(c > 0 for c in crosses) or all(c < 0 for c in crosses)) or area < 0.0005:
        raise ValueError("ROI 不可交叉、重疊或過小，請沿床區邊緣依序標記四個角。")
    return result


def roi_to_env(points: Any) -> dict[str, str]:
    points = validate_points(points)
    values = {"BED_ROI_ENABLED": "1", "BED_POLYGON_ENABLED": "1", "BED_ROI_SHOW": "1"}
    for index, (x, y) in enumerate(points, 1):
        values[f"BED_POLY_P{index}_X"] = str(x)
        values[f"BED_POLY_P{index}_Y"] = str(y)
    for axis, offset in (("X", 0), ("Y", 1)):
        values[f"BED_ROI_{axis}1"] = str(min(point[offset] for point in points))
        values[f"BED_ROI_{axis}2"] = str(max(point[offset] for point in points))
    return values


def roi_from_settings(values: dict[str, Any], defaults: Any) -> list[tuple[float, float]]:
    def get(key: str) -> Any:
        return values.get(key, getattr(defaults, key, 0))

    polygon_enabled = str(get("BED_POLYGON_ENABLED")).lower() in {"1", "true"}
    # 與 main._in_bed_roi 一致：多邊形開關優先於舊矩形開關。
    if not polygon_enabled and str(get("BED_ROI_ENABLED")).lower() not in {"1", "true"}:
        return []
    try:
        if polygon_enabled:
            return validate_points([(get(f"BED_POLY_P{i}_X"), get(f"BED_POLY_P{i}_Y")) for i in range(1, 5)])
        x1, y1, x2, y2 = (get(f"BED_ROI_{key}") for key in ("X1", "Y1", "X2", "Y2"))
        return validate_points([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
    except ValueError:
        return []


def apply_roi(defaults: Any, points: Any) -> list[tuple[float, float]]:
    # 先完整驗證，再於兩幀之間更新；分類器不會看到只有一半的新座標。
    values = roi_to_env(points)
    for key, value in values.items():
        setattr(defaults, key, value == "1" if key.endswith(("ENABLED", "SHOW")) else float(value))
    return validate_points(points)


def image_point(x: float, y: float, bounds: tuple[float, float, float, float]) -> tuple[float, float] | None:
    """將縮放後影像的座標轉成比例；黑邊不屬於可標記區域。"""
    left, top, width, height = bounds
    if width <= 0 or height <= 0 or not left <= x <= left + width or not top <= y <= top + height:
        return None
    return (x - left) / width, (y - top) / height
