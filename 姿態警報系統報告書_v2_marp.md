---
marp: true
theme: default
paginate: true
size: 16:9
title: 姿態警報系統
description: 依據姿態警報系統報告書 v2 整理之 Marp 簡報稿
style: |
  :root {
    --color-background: #fcfcfc;
    --color-foreground: #2f2f2f;
    --color-dimmed: #6a6a6a;
    --color-accent: #111111;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "PingFang TC", "Noto Sans TC", sans-serif;
  }
  section {
    background: var(--color-background);
    color: var(--color-foreground);
    padding: 56px 70px;
  }
  h1, h2 {
    color: var(--color-accent);
    font-weight: 700;
    letter-spacing: 0.02em;
  }
  h1 {
    font-size: 1.9em;
    border-bottom: 1px solid #e8e8e8;
    padding-bottom: 0.25em;
    margin-bottom: 0.55em;
  }
  p, li {
    font-size: 1.02em;
    line-height: 1.75;
  }
  ul, ol {
    margin-top: 0.35em;
  }
  li {
    margin-bottom: 0.32em;
  }
  strong {
    color: var(--color-accent);
    font-weight: 700;
  }
  code {
    background: #f3f3f3;
    color: #222;
    padding: 0.14em 0.35em;
    border-radius: 6px;
  }
  blockquote {
    margin: 1.1em 0 0;
    padding: 0.8em 1.1em;
    border-left: 3px solid #cfcfcf;
    background: #f6f6f6;
    color: var(--color-dimmed);
  }
  section.lead {
    background: #111111;
    color: #f7f7f7;
    text-align: center;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
  }
  section.lead h1 {
    color: #ffffff;
    border-bottom: none;
    font-size: 2.7em;
    margin-bottom: 0.18em;
  }
  section.lead p,
  section.lead li {
    color: #d4d4d4;
    font-size: 1.08em;
  }
---

<!-- _class: lead -->

# 姿態警報系統

基於 Raspberry Pi 與 MediaPipe Pose 的跌倒偵測與警報系統

- 報告書版本：v2
- 簡報形式：Marp 簡約風簡報稿

---

# 專案背景與動機

- **高齡者跌倒** 是病房與照護場域的重要風險
- **人力巡房** 存在空窗期，尤其夜間更明顯
- 需要 **低成本、可長時間運作** 的自動化監測方案
- 目標是在 **邊緣裝置** 上完成即時偵測與警報

---

# 專案目標

- 使用攝影機持續監測人體姿態
- 在疑似跌倒時即時觸發 **本地與遠端警報**
- 保留事件紀錄，支援後續分析與報表匯出
- 以 **Raspberry Pi** 為核心，兼顧成本與部署性

---

# 專案摘要

- **硬體平台**：Raspberry Pi + 攝影機
- **關鍵技術**：MediaPipe Pose 人體骨架偵測
- **判定方式**：軀幹角度、肩髖高差、移動速度 + 狀態機
- **警報機制**：本地蜂鳴器 / LED + 遠端通知
- **資料管理**：SQLite 事件記錄 + CSV 報表匯出

---

<!-- _class: lead -->

# 核心技術與架構

MediaPipe Pose 與跌倒判定邏輯

---

# 系統核心功能

- 即時擷取 **33 個人體骨架關鍵點**
- 規則式跌倒判定與 **多幀平滑**
- **床區 ROI** 抑制正常躺床誤判
- 多管道警報與通知機制
- 事件記錄與日報 / 週報輸出
- 久坐或長時間異常狀態提醒

---

# 技術架構

- **開發語言**：Python 3
- **視覺處理**：OpenCV
- **姿態估計**：MediaPipe Pose
- **資料儲存**：SQLite
- **硬體介接**：GPIO 控制蜂鳴器與 LED

> **系統流程**  
> `Camera -> Pose -> Fall Classifier -> State Machine -> Alert / Notify / DB / Overlay`

---

# 跌倒偵測邏輯

主要依據三個特徵：

1. **軀幹角度** 偏離垂直線
2. **肩髖高差** 是否接近水平
3. **髖部速度** 是否出現短時間劇烈變化

判定概念：

- 身體姿態接近水平
- 且伴隨快速變化或明顯下墜
- 再經過多幀平滑後才觸發跌倒判定

---

# 跌倒判定參數範例

- **軀幹角度閾值**：約 55 度
- **肩髖高差閾值**：約 0.12
- **時間確認機制**：疑似跌倒需經過短時間觀察
- **多幀平滑**：降低單幀誤判

> 重點不是只看單一姿勢，而是綜合評估：  
> **姿勢 × 速度 × 時間連續性**

---

# 多幀平滑與誤報抑制

- 使用滑動視窗累積數幀結果
- 避免單一畫面抖動就直接觸發警報
- 區分 **慢慢躺下** 與 **真正跌倒**
- 配合床區 ROI，降低正常臥床造成的誤判

---

# 床區 ROI 設計

- 可手動標記病床或休息區域
- 當人在床區內時，可降低或抑制跌倒誤判
- 特別適合病房、安養中心與固定鏡頭場景

> **優點**  
> 符合照護現場使用情境，並可大幅減少「正常躺床」誤判

---

# 狀態機設計

系統狀態包含：

- `NORMAL`：正常
- `SUSPECT_FALL`：疑似跌倒
- `FALLEN`：確認跌倒
- `SEDENTARY`：久坐 / 久不活動

> 透過狀態轉換避免頻繁跳動，提升整體穩定性

---

<!-- _class: lead -->

# 系統整合與應用

警報、通知、資料紀錄與模組化設計

---

# 警報與通知機制

- **本地端**：蜂鳴器、LED
- **遠端**：通訊軟體通知
- 確認跌倒時，同步通知照護者
- 避免只靠畫面監看而錯過緊急事件

---

# 資料紀錄與報表

- 使用 **SQLite** 紀錄事件
- 記錄狀態變化與跌倒事件時間
- 可匯出 CSV 日報與週報

資料用途：

- 追蹤異常事件
- 回顧系統表現
- 協助後續調整閾值與規則

---

# 軟體模組分工

- `vision/`：相機、姿態估計、跌倒分類
- `core/`：狀態機、共用工具
- `alert/`：警報與通知
- `storage/`：資料庫與報表
- `ui/`：畫面疊字與顯示

> 模組化設計有助於後續維護與擴充

---

# 系統優點

- 成本相對低，適合邊緣部署
- 可 24 小時持續運作
- 不依賴高階 GPU
- 兼顧即時性與可維護性
- 可依場域調整閾值與床區設定

---

# 開發挑戰

- 真正困難點在於 **降低誤報**，而不只是偵測跌倒
- 相機角度、床位位置、人體姿勢都會影響判定
- 正常躺下、翻身、抬頭等動作容易接近跌倒特徵
- 需要用平滑與 ROI 來提高實用性

---

<!-- _class: lead -->

# 成果與展望

目前進度與後續方向

---

# 目前成果

- 已完成姿態估計與跌倒判定流程
- 已加入多幀平滑與床區抑制機制
- 已具備本地警報與遠端通知能力
- 已建立事件記錄與報表輸出功能
- 已可在 Raspberry Pi 平台上運行

---

# 未來規劃

- 進行更長時間的實地測試
- 蒐集更多真實場域資料
- 進一步降低誤報率
- 增加更細緻的姿態狀態分類
- 依不同鏡頭環境建立更合適的預設閾值

---

# 結論

- 本系統展示了 **低成本姿態警報方案** 的可行性
- MediaPipe Pose 可在嵌入式設備上提供足夠的人體姿態資訊
- 結合規則判定、狀態機與 ROI，可提升照護場域安全性
- 後續重點將放在場域驗證、資料累積與誤報優化

---

<!-- _class: lead -->

# 謝謝聆聽

Q & A
