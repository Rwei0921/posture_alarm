# Existing PCB support

BCM outputs default to LED1 GPIO18, LED2 GPIO22, and buzzer GPIO17.
The SEA-1295Y passive 5V 50mA buzzer uses the existing 2N2222A driver;
keep `BUZZER_PWM_ENABLED=1` and `BUZZER_PWM_FREQUENCY=2000`.
No wiring changes are required.

## 綠燈／紅燈用途

接腳維持不變：LED1（GPIO18）為綠燈，LED2（GPIO22）為紅燈。

| 狀態 | 綠燈 | 紅燈 | 蜂鳴器 |
| --- | --- | --- | --- |
| 成功取得影像並完成偵測，尚未確認跌倒 | 亮 | 滅 | 不響 |
| 確認跌倒（FALLEN） | 滅 | 亮 | 響 |
| 啟動中、停止監控、獨立鏡頭／ROI 預覽 | 滅 | 滅 | 不響 |
| 暫時取不到影像 | 滅 | 滅 | 不新增警報；若原本已響則維持至恢復判斷或停止 |

綠燈代表影像與姿態偵測流程正在正常運作，不代表畫面內一定有人，
也不是 SHT31、網路或通知傳送成功的指示燈。
疑似跌倒尚未確認、久坐及安全躺臥不會提早點亮紅燈或發送跌倒通知；
仍沿用現有狀態機與警報冷卻時間。
監控中的 GUI ROI 編輯不會暫停偵測，因此正常指示仍會依監控狀態顯示；
OpenCV 的手動 ROI 標記會暫停偵測，期間兩燈熄滅。

GUI 的「測試 LED／蜂鳴器」會先亮綠燈約 0.5 秒，再亮紅燈並鳴叫約 0.5 秒，
結束後全部關閉。`LED_2_ENABLED=0` 時紅燈停用，但蜂鳴器與綠燈不受影響。
`SIMULATE_GPIO=1` 只回報預期輸出，不會讓實體燈亮起。
獨立的 `test_bz_led.py` 仍保留逐顆測試與全部閃爍的接線檢查流程，
不代表正式監控時兩顆燈會同時亮。

The default environment backend is `ENV_SENSOR_BACKEND=sht31`.
Enable Raspberry Pi I2C and ensure the runtime user can access `/dev/i2c-1`.
The sensor uses Linux i2c-dev directly, with no additional Python packages.
`SHT31_I2C_BUS=1` and `SHT31_I2C_ADDRESS=0x44` select the PCB sensor;
the address can also be configured as `0x45` or a decimal integer.

Use `DHT22_FALLBACK_ENABLED=1` with `DHT22_ENABLED=1` to try the existing
DHT22 backend whenever an SHT31 sample fails. This requires the existing
DHT22 hardware and optional Adafruit dependency. Use
`ENV_SENSOR_BACKEND=dht22` for DHT22 alone, or `none` to disable sensing.
`ENV_READ_INTERVAL_SECONDS`, `ENV_LOG_INTERVAL_SECONDS`, and `ENV_SHOW`
control polling, logs, and overlay; their defaults retain the legacy DHT22
settings. Keep the read interval at least two seconds when using DHT22.
The last successful sample remains displayed and included in the existing
`temperature_c` and `humidity_pct` event payload fields after read failures.
Notification message formats are unchanged.

Run hardware diagnostics from the project environment:

```bash
python test_sht31.py --bus 1 --address 0x44
python test_sht31.py --simulate
python test_bz_led.py --pwm-buzzer --frequency 2000
```

Hardware tests access the existing PCB only when simulation is omitted.
