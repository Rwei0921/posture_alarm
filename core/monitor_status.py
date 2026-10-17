"""GUI telemetry that observes, but never changes, alarm decisions."""

from __future__ import annotations

from typing import Any


def explain_status(snapshot: dict[str, Any]) -> str:
    if snapshot.get("phase") == "starting":
        return "正在初始化相機與姿態模型"
    if snapshot.get("phase") == "stopped":
        return "監控已停止，等待開始"
    if snapshot.get("phase") == "error":
        return "監控已結束，請檢查相機、模型及設定；修正後可重新開始"
    if not snapshot.get("camera_ok"):
        return "尚未取得相機影像，等待下一幀"
    if snapshot.get("state") == "FALLEN":
        if snapshot.get("gpio_simulated"):
            return "已確認跌倒；GPIO 為模擬模式，實體警報不會響"
        return "已確認跌倒，警報輸出已啟動；通知結果請查看事件"
    if not snapshot.get("person_present"):
        return "未通過人體／關鍵點可見度檢查；目前無法進行跌倒判斷"
    if snapshot.get("safe_lying_detected"):
        return "床區安全躺臥抑制生效，本幀未送入跌倒判斷"
    if snapshot.get("state") == "SUSPECT_FALL":
        if snapshot.get("fall_detected"):
            return "疑似跌倒，等待確認時間；達標才會進入 FALLEN"
        return "仍在疑似狀態，但本幀分數未達標；等待再次達標或逾時"
    reasons = []
    if not snapshot.get("recent_event"):
        reasons.append("沒有保留中的跌倒事件（單純躺平不一定觸發）")
    limits = snapshot.get("thresholds", {})
    angle = snapshot.get("trunk_angle_deg")
    diff = snapshot.get("hip_shoulder_diff")
    if angle is not None and angle < limits.get("FALL_TRUNK_ANGLE_THRESHOLD_DEG", 55):
        reasons.append("身體角度未達姿勢門檻")
    if diff is not None and diff > limits.get("FALL_HIP_SHOULDER_DIFF_THRESHOLD", 0.12):
        reasons.append("髖肩高度差超過姿勢門檻")
    if snapshot.get("fall_score", 0) < limits.get("FALL_SCORE_THRESHOLD", 0.7):
        reasons.append("平滑分數未達門檻")
    return "；".join(reasons) or "等待狀態機確認；診斷值僅供觀察，不會改變判斷"
