# Posture Alarm｜樹莓派姿態與跌倒警報

以 Raspberry Pi 攝影機、MediaPipe Tasks PoseLandmarker 與既有規則式分類器進行姿態監控。
提供獨立 Tkinter GUI、床區 ROI 標記、GPIO 燈號／蜂鳴器、SHT31 溫濕度、LINE／Discord 通知、
SQLite 事件紀錄與 CSV 報表。

> 這是輔助監控／展示專案，不保證辨識所有跌倒，不能取代人工照護或緊急求助設備。
> 測試請使用錄影或安全模擬，不要為了測試刻意摔倒。

## 目前完成的功能與驗證範圍

| 項目 | 目前狀態 |
| --- | --- |
| GUI 控制面板 | 開始／停止監控、狀態診斷、硬體測試、設定儲存與重新啟動 |
| 鏡頭／ROI 分頁 | 啟動前確認四角床區、監控中套用 ROI、隱藏畫面不停止偵測 |
| 姿態模型 | 使用 Tasks API；模型為 models/pose_landmarker_lite.task |
| 跌倒判斷 | 原有事件、平滑分數、床區抑制、確認／恢復與冷卻機制保留 |
| PCB 硬體 | 綠燈 GPIO18、紅燈 GPIO22、蜂鳴器 GPIO17、SHT31 I²C 1／0x44 |
| LINE／Discord | GUI 設定與個別測試；確認跌倒時發送文字通知 |
| 資料紀錄 | SQLite 事件、文字日誌、既有 CSV 報表元件 |
| 樹莓派封裝 | 提供 ARM64 原生打包腳本；ARM 成品建置與實機驗收仍待執行 |

使用者已回報原始碼版本的 GUI、鏡頭／ROI、SHT31、LINE 群組推播及桌面開機啟動可操作。
這不代表封裝版本已通過硬體測試，也不代表已量測跌倒檢出率。
本機的無硬體測試與樹莓派實測必須分開看待。

## 快速啟動：既有樹莓派環境

在樹莓派的桌面終端機執行：

~~~bash
cd ~/posture_alarm
.venv/bin/python run_gui.py
~~~

1. 按「開始監控」，先進入「鏡頭／ROI」預覽。
2. 沿床區依序標記左上、右上、右下、左下；也可沿用已儲存範圍。
3. 按「確認 ROI 並開始監控」才會啟動姿態偵測。
4. 隱藏畫面或切到別的分頁，監控仍繼續；按「停止監控」才會停止。
5. 憑證或閾值修改後，儲存並重新啟動監控才套用新值。

ROI 是「床區／安全躺臥抑制」範圍，不是整個房間的偵測範圍，也不是無條件取消該區警報。
詳細流程見 [GUI 操作說明](gui_guide.md)。

Windows PowerShell 僅預覽介面，不開鏡頭、不控制 GPIO、不通知、不儲存：

~~~powershell
cd D:\posture_alarm
.\.venv\Scripts\python.exe run_gui.py --preview
~~~

## 安裝與環境

建議使用已能正常偵測的 64 位元 Raspberry Pi OS 與專案虛擬環境；不要為了封裝降級 Python。
從 GitHub 取得專案後，新的樹莓派環境可依既有安裝流程準備依賴：

~~~bash
git clone https://github.com/Rwei0921/posture_alarm.git
cd posture_alarm
~~~

既有 install_rpi.sh 是較早的完整安裝工具，會升級 pip 工具鏈並移除／重裝 MediaPipe；
**已經運作正常的環境不要重跑它**。請先閱讀腳本，確認需要完整安裝時才執行：

~~~bash
bash install_rpi.sh
.venv/bin/python -m pip install -r requirements.txt
sudo apt install -y python3-tk i2c-tools
~~~

虛擬環境需要看得到系統提供的 OpenCV、lgpio 等套件；安裝工具建立新環境時會使用
--system-site-packages。若虛擬環境早已存在，腳本不會自動重建，請勿直接刪掉現有環境。
MediaPipe 必須支援 Tasks PoseLandmarker，不能以舊 mp.solutions API 是否存在作判斷。

## 設定檔

GUI 自動讀取專案根目錄的 demo.env，不必手動 source。
首次設定可以使用既有 setup_demo.py，或複製 posture_alarm.env.example 後編輯；
不要覆蓋已經含有效憑證／ROI 的 demo.env。

目前 PCB 的關鍵設定如下；它不是完整設定檔，也不要拿它覆蓋通知憑證：

~~~ini
SIMULATE_GPIO=0
BUZZER_GPIO_PIN=17
BUZZER_PWM_ENABLED=1
BUZZER_PWM_FREQUENCY=2000
LED_GPIO_PIN=18
LED_2_ENABLED=1
LED_2_GPIO_PIN=22

ENV_SENSOR_BACKEND=sht31
SHT31_I2C_BUS=1
SHT31_I2C_ADDRESS=0x44
DHT22_ENABLED=0
DHT22_FALLBACK_ENABLED=0

GUI_ROI_ON_START=1
GUI_PREVIEW_FPS=5
~~~

SHT31 的選擇開關是 ENV_SENSOR_BACKEND，**不是 SHT31_ENABLED**。
DHT22 留作舊硬體與選用備援，並非目前 PCB 的主要感測器。
setup_demo.py 仍保留舊 DHT22 設定，但感測器後端預設仍由 config.py 選擇 sht31。

demo.env、LINE Token、Discord Webhook、nano 的 demo.env.save* 都不可提交或公開。
GUI 使用純量解析與原子寫入；Linux 儲存時限制為擁有者可讀寫，不執行設定內的 shell 指令。

## PCB 接腳與燈號

使用 BCM 編號；實體 Pin 編號只是排針位置，不可混用。

| 元件 | BCM GPIO／介面 | 樹莓派實體 Pin |
| --- | --- | --- |
| 綠燈 LED1 | GPIO18 | 12 |
| 紅燈 LED2 | GPIO22 | 15 |
| 蜂鳴器驅動控制 | GPIO17 | 11 |
| SHT31 SDA | GPIO2／I²C 1 | 3 |
| SHT31 SCL | GPIO3／I²C 1 | 5 |

| 狀態 | 綠燈 | 紅燈 | 蜂鳴器 |
| --- | --- | --- | --- |
| 取得影像且完成偵測，尚未確認跌倒 | 亮 | 滅 | 不響 |
| 確認跌倒 FALLEN | 滅 | 亮 | 響 |
| 啟動中、停止監控、獨立鏡頭／ROI 預覽 | 滅 | 滅 | 不響 |
| 暫時無影像 | 滅 | 滅 | 不新增警報；已響的警報保留至恢復判斷或停止 |

綠燈不表示一定看得到人體，也不代表溫濕度、網路或通知傳送成功。
GUI 顯示的是 GPIO 輸出命令，沒有實體電氣回授。
疑似跌倒尚未確認、久坐及安全躺臥不會提早啟動紅燈／跌倒推播。

現有 SEA-1295Y 被動蜂鳴器由 2N2222A 驅動，使用 5V 電源與 2000Hz PWM；
不要將蜂鳴器電流直接接到 GPIO，也不可把 5V 接入 GPIO。
LED 限流與電源極性依既有 PCB；這次軟體更新沒有要求改線。
見 [現有 PCB 說明](PCB_HARDWARE.md)。舊的 [元件接線文件](hardware_components.md)
包含 GPIO27／DHT22 的歷史方案，不能直接當成現有板子的接線表。

SHT31 使用前請先啟用 I²C，停止監控後檢查：

~~~bash
sudo raspi-config
sudo i2cdetect -y 1
~~~

一般預設會看到 44；掃描成功不等於已完成感測值讀取驗證。

## LINE／Discord 通知

在 GUI 的「LINE / Discord」分頁填寫：

- LINE Channel Access Token：Messaging API 的存取權杖，不是 Channel secret。
- LINE Target ID：個人的 userId，或群組的 groupId；不是自己的可搜尋 LINE ID，也不是 Channel ID。
- Discord Webhook URL：欲接收通知頻道的 Webhook；空白代表停用。

多人共用時，啟用官方帳號的 Allow bot to join group chats，將它加入目標群組，
取得該群組事件 source.groupId 後填入 Target ID。
目前只接收「一個個人 ID 或一個群組 ID」，不支援逗號分隔多人 ID。
詳見 [LINE 官方群組說明](https://developers.line.biz/en/docs/messaging-api/group-chats/)。

GUI 的個別測試使用尚未儲存的欄位內容，並須按確認才發送；
儲存後要重啟監控，正式警報才使用新設定。測試文字為：

> Posture Alarm GUI test notification

正式通知為純文字，例如：

> 姿勢警報：偵測到跌倒，時間：2026年10月25日 15:30:20

目前不附照片或影片，也不推播久坐、溫度或濕度。
持續處於 FALLEN 時依 ALERT_COOLDOWN_SECONDS 重送，預設 60 秒；
通知傳送失敗也受相同冷卻限制，不會每幀連續重試。

群組 ID 擷取工具若僅存在於某台樹莓派，不能視為本倉庫已附帶的功能。
本倉庫的 line_group_setup_prompt.md 是實作需求文件，不是已完成的接收器。
若使用第三方 Webhook 擷取網站，群組事件會送往第三方；勿輸入 Token／Channel secret，
完成後停用 Webhook 並刪除擷取紀錄。已知 Target ID 的一般 push 不依賴持續運作的接收器。

test_notify.py 會嘗試測試 LINE 和 Discord 兩條管道，不是只測 LINE；
可能傳回的 HTTP 400／401 請分別檢查收件對象／Token，勿貼出真實憑證。

## 閾值與跌倒判斷限制

GUI 提供「平衡／恢復預設」與「敏感（測試用）」以及個別閾值調整，
但不會繞過人體可見度、移動事件、床區抑制或狀態機。

- 降低角度／分數／速度門檻、提高髖肩高度差上限，通常較容易達標，但也可能增加誤報。
- 事件保留時間不能短於跌倒確認時間；目前有效預設為至少 1.2 秒。
- FALLEN 的解除要求連續非跌倒達到恢復時間，預設 5 秒。
- 靜止躺平但沒有近期跌倒事件，仍可能不會報警；不能只靠把閾值調敏感保證涵蓋。
- 先看 GUI 的人體、角度、速度、分數、事件與床區診斷，再小幅調整。

見 [GUI 閾值說明](gui_guide.md) 與 [調校指南](TUNING_GUIDE.md)。

## 日誌、資料庫與報表

原始碼模式的預設位置：

| 資料 | 位置 |
| --- | --- |
| 設定／ROI／憑證 | demo.env |
| 文字日誌 | data/posture_alarm.log |
| SQLite 事件 | data/events.db |
| CSV 報表輸出目錄 | reports/ |

Reporter 元件保留供既有工具或外部排程使用，不宣稱 GUI 會自動排程匯出。
LOG_FILE_PATH 可指定檔案或目錄；絕對路徑設定優先於預設位置。

## CLI、硬體測試與開機啟動

原有 CLI 仍可使用；run_demo.sh 會載入 demo.env：

~~~bash
cd ~/posture_alarm
bash run_demo.sh
~~~

獨立硬體診斷：

~~~bash
.venv/bin/python test_bz_led.py --simulate --pwm-buzzer
.venv/bin/python test_bz_led.py --pwm-buzzer --frequency 2000 --duration 1 --repeat 2
.venv/bin/python test_sht31.py --bus 1 --address 0x44
~~~

非模擬測試會操作硬體；蜂鳴器可能很大聲，先停止監控再執行。
GUI 硬體測試會先亮綠燈約 0.5 秒，再亮紅燈並鳴叫約 0.5 秒；
獨立 test_bz_led.py 仍保留逐顆測試及全部閃爍流程，與正式監控燈號用途不同。
舊 DHT22／ROI 工具 test_dht22.py、mark_bed_roi.py 與 --run-main 操作仍保留。

桌面 GUI 自動啟動應在使用者圖形桌面登入後執行 run_gui.py；
目前已設定好的桌面自動啟動不會被本次更新改寫。
posture_alarm.service 是「無 GUI」的 systemd 範本，預設以 pi 使用者執行，
設定來自 /etc/posture_alarm.env；不要同時啟動 GUI 監控與此服務搶用鏡頭／GPIO。
不需要桌面時才依範本調整實際使用者與路徑後安裝：

~~~bash
sudo cp posture_alarm.service /etc/systemd/system/posture_alarm.service
sudo cp -n posture_alarm.env.example /etc/posture_alarm.env
sudo nano /etc/posture_alarm.env
sudo systemctl daemon-reload
sudo systemctl enable --now posture_alarm
journalctl -u posture_alarm -f
~~~

## 樹莓派執行檔封裝

提供 build_rpi.py 與獨立的 requirements_build.txt；不會自動升級原本的執行套件。
請在已能正常運作的 ARM64 樹莓派環境執行：

~~~bash
cd ~/posture_alarm
.venv/bin/python -m pip install -r requirements_build.txt
.venv/bin/python build_rpi.py --check
.venv/bin/python build_rpi.py --mode onedir
~~~

資料夾版實機驗收通過後，再建立單檔版：

~~~bash
.venv/bin/python build_rpi.py --mode onefile
~~~

成品位於 dist/ 下的新目錄；私密設定、資料庫與日誌不會自動複製，也不會覆蓋舊成品。
腳本產生桌面捷徑但不自動安裝或更改開機設定。
樹莓派成品是 Linux ARM64 執行檔，不是 Windows EXE；Windows 不能直接替這台樹莓派打包。
**目前只完成封裝支援與無硬體回歸測試；ARM 建置、MediaPipe 推論及硬體實測尚待在樹莓派完成。**
完整移轉、驗收及限制見 [封裝指南](packaging_guide.md)。

## 測試與常見問題

Windows PowerShell：

~~~powershell
cd D:\posture_alarm
.\.venv\Scripts\python.exe -m pytest tests -q
~~~

樹莓派：

~~~bash
.venv/bin/python -m pytest tests -q
~~~

測試使用模擬邊界，不要求相機、實體 GPIO、GUI 視窗或真實通知。
本次更新（2026-10-25）在 Windows 本機執行：160 項測試通過，匯入檢查與 Git 變更格式檢查通過。
新增封裝檢查覆蓋資源／資料路徑、子程序參數、系統鏡頭的函式庫環境、
私密資料排除、舊成品保留和錯誤訊息去敏；不等於真正執行過 ARM 封裝成品。

| 問題 | 檢查方向 |
| --- | --- |
| GPIO 初始化失敗／自動退回模擬 | 在同一個 .venv 驗證 gpiozero、lgpio 匯入與 GPIO 權限；勿以 root 執行作永久解法 |
| 系統有 lgpio，但 .venv 匯入失敗 | 確認虛擬環境是否能讀系統套件；勿因小問題刪掉環境 |
| /dev/i2c-1 不存在 | 先啟用 I²C，再檢查權限與 0x44／0x45 |
| mediapipe 沒有 solutions | 目前使用 Tasks API；確認程式已更新及 .task 模型存在 |
| GUI 沒出現 | 確認由桌面工作階段啟動且 Tkinter 可用；純 SSH 會退回 CLI |
| 跌倒未通知 | 依序看人體、事件、床區、確認狀態、通知設定、網路及冷卻時間 |
| 兩燈都滅但 GUI 還開著 | 可能尚未開始監控、正在 ROI 預覽、影像中斷或使用模擬 GPIO |
| 更新被 Git 拒絕 | 先停止，備份並檢查本機變更；不要強制覆蓋樹莓派尚未同步的修改 |
