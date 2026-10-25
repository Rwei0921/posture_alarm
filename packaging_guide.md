# 樹莓派封裝與驗收

本專案支援以 PyInstaller 建立 ARM64 Linux 的資料夾版與單檔版。
這是新增的建置支援，**尚未在本次 Windows 工作環境產生或驗收 ARM 成品**。
請先完成資料夾版的實機驗收，再考慮單檔版；不要直接替換已在照護／展示中使用的版本。

## 前置條件

- 在目標樹莓派本機或相容的 ARM64 Linux 環境建置；不能使用 Windows EXE。
- 建議與部署機使用相同的 Raspberry Pi OS 版本／架構。
- 先確認原始碼版本的 GUI、模型、相機、GPIO、I²C 與通知可運作。
- 使用既有 .venv，不降級 Python、不升級原有套件、不重建虛擬環境。
- 打包工具獨立放在 requirements_build.txt；只有建置端需要 PyInstaller。
- 仍需要系統的 rpicam-vid、顯示環境、GPIO／I²C 權限與相機驅動；封裝不是硬體驅動安裝器。
- 預設後端 rpicam 是本次封裝檢查的必要條件；選用 Picamera2／DHT22 後端仍需個別實測。

PyInstaller 不支援直接跨作業系統建置，Linux 成品也受系統函式庫版本影響。
參考 [官方需求](https://pyinstaller.org/en/stable/requirements.html) 與
[單檔／資料夾模式](https://pyinstaller.org/en/stable/operating-mode.html)。

## 建立資料夾版

在樹莓派桌面終端機執行：

```bash
cd ~/posture_alarm
.venv/bin/python -m pip install -r requirements_build.txt
.venv/bin/python build_rpi.py --check
.venv/bin/python build_rpi.py --mode onedir
```

--check 只檢查環境、匯入、模型與 rpicam-vid，不開相機／GPIO，不發通知，也不讀取 demo.env。
若失敗，先修好原本環境；腳本不會自動安裝缺少的套件或降級 MediaPipe。
原始碼使用動態匯入，因此打包腳本會明確收集 MediaPipe、OpenCV、GPIO 與 SHT31 的 fcntl。

每次建置使用 build/、dist/ 下全新的版本目錄，失敗也不刪除舊成品。
結束時會列出這次的實際路徑，例如：

```text
dist/posture_alarm_onedir_日期_隨機碼/
├── posture_alarm.desktop
└── posture_alarm/
    ├── posture_alarm
    └── _internal/        # 封裝模型與函式庫，不要移除
```

不要只複製資料夾版裡的執行檔；必須保留完整成品資料夾。
跨電腦傳輸建議使用保留符號連結的 tar 封存格式，避免一般 ZIP 或不支援符號連結的隨身碟破壞函式庫。

## 首次設定與資料位置

程式在執行檔旁讀取／寫入 demo.env、data/ 與 reports/，不使用臨時解壓目錄保存資料。
因此請放在 pi 使用者可寫入的資料夾，不要直接放進唯讀／需 root 權限的系統目錄。

1. 將現有 demo.env **手動複製**到成品執行檔旁，檢查權限為 0600。
2. 不要把含憑證的設定或 data/、reports/ 放入公開發行包；打包腳本不會自動帶入它們。
3. 若希望保留舊事件，停止舊監控後再備份／複製既有 data/、reports/，不要覆蓋新版本已產生的資料。
4. 原 demo.env 中的 LOG_FILE_PATH 絕對路徑仍會生效；要改成新位置需手動調整，不會自動搬移。
5. 模型的預設位置由封裝資源提供，不改變 .task 模型內容；若設定外部自訂模型，建議使用絕對路徑。

預設 GUI 會在使用者按儲存時才寫入設定。初次沒有設定時，通知停用；
GPIO／感測器仍依 config.py 的實體硬體預設值，不能把無設定的啟動當成無硬體預覽。
需要安全查看介面時，明確加上 --preview。

## 驗收成品

先在終端機中執行「腳本印出的實際執行檔路徑」，以下路徑需自行替換：

```bash
/完整成品路徑/posture_alarm --self-test
/完整成品路徑/posture_alarm --preview
```

--self-test 檢查封裝匯入與內建模型檔存在，不讀 demo.env、不建立模型實例、不開硬體、不發通知；
即使通過，也不代表模型內容、攝影機或警報實測成功。
--preview 不開硬體、不發通知，也不儲存設定。

關閉預覽後，停止原本的 GUI／systemd 監控，再執行成品，不要讓兩份程式搶相機與 GPIO。
逐項確認：

- [ ] GUI 開啟、監控前 ROI 預覽與四角確認。
- [ ] 監控模型成功建立並持續更新影像／診斷值。
- [ ] 隱藏／顯示影像不停止監控，監控中可套用 ROI。
- [ ] 正常監控亮 GPIO18 綠燈；確認跌倒亮 GPIO22 紅燈並控制 GPIO17 蜂鳴器。
- [ ] GUI 硬體測試先綠燈，再紅燈與蜂鳴器，停止後全部關閉。
- [ ] SHT31 溫濕度更新；若使用選用後端，也另做實機驗證。
- [ ] 按確認後個別測試 LINE／Discord，儲存並重啟監控後套用。
- [ ] 設定、ROI、事件資料與日誌在程式結束及重新啟動後仍存在。
- [ ] 影像故障時綠燈不誤亮；關閉 GUI 後鏡頭與 GPIO 釋放。

請用錄影或安全模擬測試，不要刻意跌倒。真實 LINE／Discord 測試會發送訊息。

## 單檔版

資料夾版上述項目驗收通過後，再執行：

```bash
cd ~/posture_alarm
.venv/bin/python build_rpi.py --mode onefile
```

新的版本目錄會包含一個 posture_alarm 執行檔與一個桌面捷徑。
「單檔」指程式及其封裝依賴；設定、資料庫、日誌仍刻意保持外部檔案。
每次啟動需要解壓，較資料夾版慢，並需要支援執行與符號連結的暫存空間。
完整重做上述驗收，不可把資料夾版的成功當成單檔版已驗收。

## 桌面捷徑與開機啟動

腳本在成品目錄生成 posture_alarm.desktop，指向這次成品的絕對路徑，不透過 shell。
可手動將它複製到桌面，依桌面環境允許啟動；移動執行檔位置後必須同步更新捷徑的 Exec。
它不會自動複製到桌面、應用程式選單或 ~/.config/autostart，也不會改寫原有開機設定。

若要讓開機改用封裝版，先完成驗收，備份原有自動啟動設定，再手動替換目標；
只保留一份監控啟動來源。GUI 必須在圖形桌面登入後啟動，無桌面的 systemd 服務不能直接代替。

## 問題排查與安全

- 先由終端機執行成品，保留錯誤型別；不要貼出完整 demo.env、Token 或 Webhook。
- 若背景程序未啟動，確認是這版的 --worker 模式，不是用封裝檔去執行 control_worker.py。
- 系統 rpicam-vid 子程序會使用原本的系統函式庫路徑；封裝內部監控子程序則保留封裝環境。
- 不要使用 sudo 執行單檔程式來迴避權限問題；先修正使用者的相機、GPIO、I²C 權限。
- 本機無 ARM64 執行環境，沒有產生可下載的樹莓派二進位成品；請勿將腳本／模擬測試視為實機驗收。

參考 [PyInstaller 執行時路徑](https://pyinstaller.org/en/stable/runtime-information.html)
及 [外部系統程式注意事項](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application)。
