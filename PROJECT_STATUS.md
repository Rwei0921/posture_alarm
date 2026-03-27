# posture_alarm 專案實作狀態（MediaPipe 版本）

最後更新：2026-03-27  
目的：讓人與 AI 都能快速理解目前做到哪裡、怎麼跑、接下來做什麼。

---

## 1) 專案目標

`posture_alarm` 目標是以攝影機姿態估計為主，偵測跌倒/異常姿勢，並觸發警報、通知與事件紀錄。

本階段已從「YOLO + MediaPipe Pose」方案，統一改為「純 MediaPipe」方案。

---

## 2) 架構現況

### 現行流程
Camera  
-> MediaPipe Pose（人體存在 + 姿態關鍵點）  
-> Fall Classifier（事件 + 分數平滑判定）  
-> State Machine（NORMAL / SUSPECT_FALL / FALLEN / SEDENTARY）  
-> Alert + Notifier + DB 記錄 + Overlay 顯示

---

## 3) 已完成模組與檔案

### Root
- `config.py`：全域設定（相機、閾值、通知、資料路徑）
- `main.py`：主迴圈與模組整合
- `requirements.txt`：已改為 MediaPipe/OpenCV/requests 等依賴
- `structure.txt`：說明已更新為 MediaPipe 人體偵測語意
- `posture_alarm.service`：systemd 無頭部署範本
- `TUNING_GUIDE.md`：閾值調參指南

### Vision
- `vision/camera.py`：`Camera` 類別，支援 `rpicam` / `picamera2` / OpenCV
- `vision/person_detector.py`：`PersonDetector`，以關鍵點 visibility 判斷是否有人
- `vision/pose_estimator.py`：`PoseEstimator`，提取 33 點 landmarks（x/y/z/visibility）
- `vision/fall_classifier.py`：`FallClassifier`，依軀幹角度/肩髖高差/髖部速度 + 多幀分數 + 事件窗判定

### Core
- `core/state_machine.py`：`PostureStateMachine`（含時間條件轉換）
- `core/utils.py`：logger 與 timestamp 工具

### Sensors
- `sensors/imu_mpu6050.py`：`IMU_MPU6050`（模擬模式 + 硬體模式骨架）

### Alert
- `alert/buzzer_led.py`：`BuzzerLED`（支援模擬模式）
- `alert/notifier_line.py`：`LineNotifier`
- `alert/notifier_telegram.py`：`TelegramNotifier`

### Storage
- `storage/db_sqlite.py`：`EventDB`（SQLite 事件紀錄）
- `storage/reporter.py`：`Reporter`（日報/週報 CSV）

### UI
- `ui/overlay.py`：`Overlay`（狀態字樣、警報提示、關鍵點繪製）

### Tests
- `tests/test_state_machine.py`：狀態機轉換測試
- `tests/test_fall_classifier.py`：跌倒判定與多幀平滑測試
- `tests/test_db.py`：SQLite 事件寫入與讀取測試

---

## 4) 已完成驗證

已執行匯入驗證，結果：`All imports OK`

驗證指令：

```bash
python -c "from vision.camera import Camera; from vision.person_detector import PersonDetector; from vision.pose_estimator import PoseEstimator; from vision.fall_classifier import FallClassifier; from core.state_machine import PostureStateMachine; from core.utils import setup_logger; from sensors.imu_mpu6050 import IMU_MPU6050; from alert.buzzer_led import BuzzerLED; from alert.notifier_line import LineNotifier; from alert.notifier_telegram import TelegramNotifier; from storage.db_sqlite import EventDB; from storage.reporter import Reporter; from ui.overlay import Overlay; print('All imports OK')"
```

並已新增單元測試目錄，可使用以下指令執行：

```bash
python -m pytest tests/ -v
```

---

## 5) 在樹莓派測試方式（目前建議）

1. 安裝依賴
```bash
pip install -r requirements.txt
```

2. 先跑匯入驗證（上面那條）

3. 執行主程式
```bash
python main.py
```

> 若使用 Raspberry Pi Camera Module 3（CSI），建議：
```bash
export CAMERA_BACKEND=rpicam
export CAMERA_WIDTH=640
export CAMERA_HEIGHT=480
python main.py
```

4. 手動測試項目
- 畫面是否正常讀取
- 是否能看到狀態字樣與關鍵點
- 模擬姿態變化時，狀態是否切換
- FALLEN 時是否觸發蜂鳴/通知/DB 寫入
- 退出時可用 `q` / `Q` / `Esc`（視窗模式）或 `Ctrl+C`（終端）

---

## 6) 環境變數（可選）

- `CAMERA_SOURCE`（例如 `0`）
- `CAMERA_BACKEND`（`auto` / `rpicam` / `picamera2` / `opencv`）
- `RPICAM_FPS`、`RPICAM_TIMEOUT_MS`（`rpicam` 後端參數）
- `FALL_EVENT_MIN_HIP_DROP`、`FALL_EVENT_WINDOW_SECONDS`（跌倒事件窗）
- `BED_ROI_ENABLED`、`BED_ROI_X1`、`BED_ROI_Y1`、`BED_ROI_X2`、`BED_ROI_Y2`（床區域抑制誤報）
- `SHOW_WINDOW`（`1` or `0`）
- `LINE_NOTIFY_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `SIMULATE_IMU`（預設 1）
- `SIMULATE_GPIO`（預設 1）

---

## 7) 目前限制與已知風險

- 跌倒判定已改為事件 + 分數平滑，仍需依病房鏡頭角度進行實測調參
- 已加入通知冷卻機制（`ALERT_COOLDOWN_SECONDS`），仍需現場驗證冷卻秒數是否符合照護流程
- 硬體端（GPIO/IMU）仍以「模擬可跑」為主，真實寄存器讀值流程可再補強
- 無攝影機或無 GUI 環境下，需關閉視窗顯示（`SHOW_WINDOW=0`）

> 進度更新：通知冷卻與多幀平滑已完成，後續重點為實地調參與資料累積。

---

## 8) systemd 部署（無頭模式）

1. 複製 service：

```bash
sudo cp posture_alarm.service /etc/systemd/system/posture_alarm.service
```

2. 啟用與啟動：

```bash
sudo systemctl daemon-reload
sudo systemctl enable posture_alarm
sudo systemctl start posture_alarm
```

3. 查狀態與日誌：

```bash
sudo systemctl status posture_alarm
journalctl -u posture_alarm -f
```

### 卡住時快速清理

```bash
pkill -f "python main.py"
pkill -f rpicam-vid
```

---

## 9) 下一步建議（優先順序）

1. 針對病房情境校正 `BED_ROI_*` 與 `FALL_EVENT_*`，降低「主動躺下」誤報  
2. 累積 8 小時以上場域數據，驗證誤報率目標（< 1 / 8h）  
3. 將病床躺臥分流為獨立狀態（例如 `LYING_SAFE`）以利後續分析  
4. 補充整合測試（含通知冷卻與長時間運行）  
5. 依照實測結果更新 `TUNING_GUIDE.md` 的場域預設值

---

## 10) 快速結論

目前專案已完成第一版端到端骨架，並成功通過模組匯入驗證。  
可以在樹莓派上直接執行 `python main.py` 進行現場測試，接下來重點是「實測調參 + 通知去重 + 硬體細節補強」。
