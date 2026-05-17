# posture_alarm 專案實作狀態（MediaPipe 版本）

最後更新：2026-04-09  
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
- `mark_bed_roi.py`：手動標記床區 ROI 工具
- `requirements.txt`：已改為 MediaPipe/OpenCV/requests 等依賴
- `structure.txt`：說明已更新為 MediaPipe 人體偵測語意
- `posture_alarm.service`：systemd 無頭部署範本
- `TUNING_GUIDE.md`：閾值調參指南

### Vision
- `vision/camera.py`：`Camera` 類別，支援 `rpicam` / `picamera2` / OpenCV
- `vision/person_detector.py`：`PersonDetector`，以關鍵點 visibility 判斷是否有人
- `vision/pose_estimator.py`：`PoseEstimator`，提取 33 點 landmarks（x/y/z/visibility）
- `vision/fall_classifier.py`：`FallClassifier`，依軀幹角度/肩髖高差/髖部速度 + 多幀分數 + 事件窗判定，並已做第一輪保守化調參

### Core
- `core/state_machine.py`：`PostureStateMachine`（含時間條件轉換）
- `core/utils.py`：logger、timestamp 與中文告警訊息格式工具

### Sensors
- `sensors/imu_mpu6050.py`：`IMU_MPU6050`（模擬模式 + 硬體模式骨架）

### Alert
- `alert/buzzer_led.py`：`BuzzerLED`（支援模擬模式）
- `alert/notifier_line.py`：`LineNotifier`（LINE Messaging API push）
- `alert/notifier_discord.py`：`DiscordNotifier`（Discord webhook）

### Storage
- `storage/db_sqlite.py`：`EventDB`（SQLite 事件紀錄，會自動建目錄 / 建表）
- `storage/reporter.py`：`Reporter`（日報/週報 CSV）

### UI
- `ui/overlay.py`：`Overlay`（狀態字樣、警報提示、關鍵點繪製）

### Tests
- `tests/test_state_machine.py`：狀態機轉換測試
- `tests/test_fall_classifier.py`：跌倒判定、多幀平滑與誤判回歸測試
- `tests/test_db.py`：SQLite 事件寫入與讀取測試
- `tests/test_notifiers.py`：LINE / Discord 通知測試
- `tests/test_utils.py`：時間格式與告警訊息測試
- `tests/test_config.py`：通知設定值測試

---

## 4) 已完成驗證

已執行匯入驗證，結果：`All imports OK`

驗證指令：

```bash
python -c "from vision.camera import Camera; from vision.person_detector import PersonDetector; from vision.pose_estimator import PoseEstimator; from vision.fall_classifier import FallClassifier; from core.state_machine import PostureStateMachine; from core.utils import setup_logger; from sensors.imu_mpu6050 import IMU_MPU6050; from alert.buzzer_led import BuzzerLED; from alert.notifier_line import LineNotifier; from alert.notifier_discord import DiscordNotifier; from storage.db_sqlite import EventDB; from storage.reporter import Reporter; from ui.overlay import Overlay; print('All imports OK')"
```

並已新增單元測試目錄，可使用以下指令執行：

```bash
python -m pytest tests/ -v
```

目前已補充驗證內容包含：

- SQLite 檔案型資料庫自動建立與 Reporter 讀取
- LINE / Discord notifier 行為與缺少 `requests` 時的 fail-soft 回傳
- `APP_TIMEZONE=Asia/Taipei` 下的時間格式一致性
- 跌倒判定第一輪保守化調參的 head-raise 誤判回歸測試

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

> 床區 ROI 手動標記：
```bash
python mark_bed_roi.py
```

> 每次啟動前都重新標記並直接啟動主程式：
```bash
python mark_bed_roi.py --run-main
```

> 展示模式問答設定與一鍵啟動：
```bash
python setup_demo.py
./run_demo.sh
```

> 或整合在 `main.py` 內（啟動時先標記床區）：
```bash
export BED_ROI_MARK_ON_START=1
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
- `BED_POLYGON_ENABLED`、`BED_POLY_P1~P4`（四點床區多邊形）
- `SHOW_WINDOW`（`1` or `0`）
- `APP_TIMEZONE`（預設 `Asia/Taipei`）
- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_TARGET_ID`
- `DISCORD_WEBHOOK_URL`
- `LOG_FILE_ENABLED`（預設 1）
- `LOG_FILE_PATH`（預設 `data/posture_alarm.log`）
- `SIMULATE_IMU`（預設 1）
- `SIMULATE_GPIO`（預設 0，使用實體 GPIO；設為 1 可改回模擬）
- `BUZZER_PWM_ENABLED`（預設 1，兩腳被動蜂鳴器使用 PWM）
- `BUZZER_PWM_FREQUENCY`（預設 2000）

---

## 7) 目前限制與已知風險

- 跌倒判定已改為事件 + 分數平滑，且已做第一輪保守化調參；仍需依病房鏡頭角度進行實測調參
- 已支援四點床區多邊形標記，較矩形 ROI 更適合斜角病房鏡頭
- 已加入通知冷卻機制（`ALERT_COOLDOWN_SECONDS`），仍需現場驗證冷卻秒數是否符合照護流程
- LINE 已改為 Messaging API，Discord 已改為 webhook；仍需用正式 token / webhook 在樹莓派實機驗證送達穩定度
- SQLite 已接到主流程，事件會自動寫入 `data/events.db`，但舊資料若是 UTC 格式不會自動轉換
- 日誌、DB 與告警訊息已統一走 `APP_TIMEZONE`；目前通知顯示為中文時間格式
- 硬體端（GPIO/IMU）仍以「模擬可跑」為主，真實寄存器讀值流程可再補強
- 無攝影機或無 GUI 環境下，需關閉視窗顯示（`SHOW_WINDOW=0`）

> 進度更新：SQLite、LINE/Discord、時間一致性與第一輪跌倒保守化調參已完成，後續重點為實地調參與資料累積。

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

1. 針對病房情境校正 `BED_ROI_*` 與 `FALL_EVENT_*`，降低「主動躺下 / 抬頭」誤報  
2. 累積 8 小時以上場域數據，驗證誤報率目標（< 1 / 8h）  
3. 將病床躺臥分流為獨立狀態（例如 `LYING_SAFE`）以利後續分析  
4. 補充整合測試（含通知送達、冷卻與長時間運行）  
5. 依照實測結果更新 `TUNING_GUIDE.md` 的場域預設值

---

## 10) 各階段完成度

| 功能 | 狀態 | 說明 |
|------|------|------|
| **純 MediaPipe 架構** | ✅ 已完成 | 已移除 YOLO，全面使用 MediaPipe Pose |
| **核心模組**（Vision / Core / Sensors / Alert / Storage / UI） | ✅ 已完成 | 共 14 個模組檔案，匯入驗證通過 |
| **主迴圈整合** (`main.py`) | ✅ 已完成 | 425 行，含 BED ROI 互動標記、縮放顯示 |
| **通知冷卻機制** (`ALERT_COOLDOWN_SECONDS`) | ✅ 已完成 | 預設 60 秒冷卻，避免 FALLEN 連續推播 |
| **多幀平滑分數制** (`FallClassifier`) | ✅ 已完成 | `deque` 環形緩衝區 + `score_threshold` |
| **跌倒事件閘控** (`FALL_EVENT_*`) | ✅ 已完成 | 髖部下降量 + 事件時間窗，抑制慢躺誤報 |
| **LINE / Discord 通知** | ✅ 已完成 | LINE Messaging API push + Discord webhook，Telegram 已移除 |
| **SQLite 正式接線** | ✅ 已完成 | 啟動時自動建檔 / 建表，`Reporter` 可直接讀取同一 DB |
| **時間一致性** | ✅ 已完成 | 日誌、DB、告警訊息統一使用 `APP_TIMEZONE`，通知為中文時間格式 |
| **BED ROI 抑制** | ✅ 已完成 | 矩形 ROI + 四點多邊形，含互動標記工具 |
| **單元測試** (`tests/`) | ✅ 已完成 | state machine / classifier / DB / notifier / config / utils 共 6 檔 |
| **systemd 部署** (`posture_alarm.service`) | ✅ 已完成 | 無頭模式服務範本 |
| **調參指南** (`TUNING_GUIDE.md`) | ✅ 已完成 | 含高/低角度預設值與疑難排解 |
| **第一輪跌倒保守化調參** | ✅ 已完成 | 已提高角度 / 速度 / hip drop 條件，先降低床上抬頭誤報 |
| **實地調參與資料累積** | 🔶 待進行 | 需在樹莓派實際場域測試調整閾值 |
| **`LYING_SAFE` 狀態分流** | ⬜ 未開始 | 計畫將病床正常躺臥獨立為安全狀態 |
| **整合測試** | ⬜ 未開始 | 端到端長時間運行穩定性測試 |
| **硬體 IMU 寄存器讀值** | ⬜ 未開始 | `_read_hardware()` 仍為骨架 |

---

## 11) 快速結論

專案已完成所有第一版功能開發，包括：核心偵測流程、SQLite 事件紀錄、LINE/Discord 通知、通知冷卻、多幀平滑判定、BED ROI 誤報抑制、時間一致性修正、單元測試、systemd 部署範本與調參指南。  
可在樹莓派上以 `python main.py` 或 `systemctl start posture_alarm` 啟動。  
**目前階段重點已轉為「實地場域測試 → 資料累積 → 閾值校正 → 狀態分流優化」。**
