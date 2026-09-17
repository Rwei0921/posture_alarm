# Posture Alarm 硬體元件與接線

本文件是 `posture_alarm` 的硬體接線表。程式使用 Raspberry Pi 的 **BCM GPIO 編號**；`BCM GPIO` 和 `Physical Pin` 是兩種不同編號，請不要混用。

## 元件清單

必要元件：

1. Raspberry Pi 及 40-pin GPIO 排針
2. Raspberry Pi Camera Module 3 或 USB 攝影機
3. DHT22／AM2302 溫濕度感測器
4. LED，至少 2 顆
5. LED 串聯電阻 220Ω～330Ω，至少 2 顆
6. 5V 蜂鳴器
7. 5V 升壓／穩壓電源模組，依蜂鳴器所需電流選擇
8. 邏輯電位 N-MOSFET 或 NPN 電晶體，用來驅動 5V 蜂鳴器
9. MOSFET Gate 電阻約 1kΩ，以及 Gate 下拉電阻約 10kΩ
10. 麵包板與杜邦線

可選元件：

- 若使用裸 DHT22，準備 4.7kΩ～10kΩ 上拉電阻。
- 若使用磁性蜂鳴器或線圈型負載，增加反向二極體，例如 1N4007；壓電蜂鳴器通常不需要。
- 若升壓模組沒有穩定的 5V 輸出，準備萬用電表，接蜂鳴器前先調整並確認輸出。

## Raspberry Pi 接腳對照

| 裝置／訊號 | BCM GPIO | 實體 Pin | 電氣用途 |
|---|---:|---:|---|
| 蜂鳴器控制訊號 | GPIO17 | Pin 11 | 控制 MOSFET Gate 或電晶體 Base |
| LED_1 控制 | GPIO27 | Pin 13 | 跌倒警示燈 |
| LED_2 控制 | GPIO22 | Pin 15 | 第二顆跌倒警示燈 |
| DHT22 DATA | GPIO4 | Pin 7 | 單線資料訊號 |
| 3.3V | — | Pin 1 或 Pin 17 | DHT22 VCC |
| GND | — | Pin 6 | LED、DHT22、蜂鳴器驅動共地 |

## LED_1 與 LED_2 接法

兩顆 LED 的接法相同：

```text
GPIO27 / Physical Pin 13 ── 220~330Ω ── LED_1 陽極（+）
LED_1 陰極（-）           ─────────────── GND

GPIO22 / Physical Pin 15 ── 220~330Ω ── LED_2 陽極（+）
LED_2 陰極（-）           ─────────────── GND
```

LED 長腳通常是陽極（+），短腳通常是陰極（-）；仍應以 LED 本體或模組標示為準。若使用已內建電阻的 LED 模組，依模組的 `S/+/-` 或 `IN/VCC/GND` 標示接線，不要重複使用過小的電阻。

## DHT22 接法

### 三腳 DHT22 模組

依模組標示接：

```text
DHT22 VCC（+）  ── Raspberry Pi 3.3V，Physical Pin 1
DHT22 DATA（S） ── GPIO4，Physical Pin 7
DHT22 GND（-）  ── GND，Physical Pin 6
```

### 四腳裸 DHT22

感測器正面、格柵朝向自己時，常見由左至右是：

```text
Pin 1 VCC（+）  ── 3.3V
Pin 2 DATA      ── GPIO4 / Physical Pin 7
Pin 3 NC        ── 不接
Pin 4 GND（-）  ── GND
```

在 DATA 和 3.3V 之間加 4.7kΩ～10kΩ 上拉電阻：

```text
3.3V ── 4.7k~10kΩ ── DHT22 DATA / GPIO4
```

不同模組的腳位排列可能不同，實際接線前請以感測器絲印或資料表確認。DATA 上拉到 3.3V 是為了保護 Raspberry Pi 的 GPIO 邏輯輸入。

## 5V 升壓蜂鳴器接法

GPIO 不可以直接輸出 5V，也不應直接承擔大聲蜂鳴器的工作電流。GPIO17 只負責控制 MOSFET／電晶體，蜂鳴器的功率由 5V 電源模組提供。

### 使用 N-MOSFET 的建議接法

```text
升壓模組 +5V ───────── 蜂鳴器正極（+）
                         蜂鳴器負極（-） ── MOSFET Drain（D）

MOSFET Source（S） ───── 升壓模組 GND ───── Raspberry Pi GND

GPIO17 / Pin 11 ── 1kΩ ── MOSFET Gate（G）
MOSFET Gate（G） ── 10kΩ ── GND
```

注意事項：

- 升壓模組的 GND 必須和 Raspberry Pi GND 共地。
- 升壓模組的 +5V 絕對不要接到 GPIO17、GPIO27、GPIO22 或 GPIO4。
- 接上蜂鳴器前，先用萬用電表確認升壓輸出約 5.0V。
- MOSFET 必須是 3.3V 邏輯電位可充分導通的型號，並依蜂鳴器電流選擇額定值。
- 若蜂鳴器是磁性線圈型，請在蜂鳴器兩端加反向二極體；若是一般壓電蜂鳴器，通常不需要。
- 若升壓模組輸入端直接取自 Raspberry Pi，必須確認 Pi 的電源與升壓模組輸入電流足夠；較大聲或較大電流的蜂鳴器建議使用獨立 5V 電源。

### 主動式與被動式蜂鳴器

目前程式預設：

```env
BUZZER_GPIO_PIN=17
BUZZER_PWM_ENABLED=1
BUZZER_PWM_FREQUENCY=2000
```

- 兩腳被動蜂鳴器：使用 PWM，預設 2000Hz。
- 5V 主動式蜂鳴器：通常改成 `BUZZER_PWM_ENABLED=0`，使用開／關控制。

升高電壓不一定會讓聲音更大；實際音量還取決於蜂鳴器規格、共鳴頻率、驅動電流與外殼。請以蜂鳴器資料表的額定電壓和電流為準。

## 攝影機

Raspberry Pi Camera Module 3 使用 CSI 排線接到 Raspberry Pi 的 CSI 相機接口，不使用上述 GPIO。服務模式預設使用：

```env
CAMERA_BACKEND=rpicam
CAMERA_WIDTH=640
CAMERA_HEIGHT=480
```

USB 攝影機則使用 OpenCV，可將 `CAMERA_BACKEND` 設為 `opencv`。

## 硬體測試

在 Raspberry Pi 專案目錄執行：

```bash
source .venv/bin/activate
python test_bz_led.py --pwm-buzzer --frequency 2000 --duration 2 --repeat 3
python test_dht22.py --data-pin 4 --reads 5
```

如果尚未接硬體，只測試程式流程：

```bash
python test_bz_led.py --simulate --pwm-buzzer --duration 0.1 --repeat 1
python test_dht22.py --simulate
```

硬體測試時，請先確認 LED 電阻、DHT22 上拉電阻、升壓模組輸出電壓，以及所有 GND 是否共地。
