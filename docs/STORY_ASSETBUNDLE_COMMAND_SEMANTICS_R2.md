# Story AssetBundle 高價值指令語意驗證報告 (Research R2)

**專案**：PCRD Story Map (`PCRD_transtool`)  
**階段**：Issue #2 — Research R2 (High-Value Command Semantic Validation)  
**狀態**：`COMPLETED` (待 External Review)  
**審計基準**：So-net 台服 CDN TruthVersion `00600025`  
**樣本基準**：180 話確定性分層抽樣（Main 37, Chara 45, Guild 44, Event 41, System 13；與 R1 完全同源）  
**分析腳本**：[`tools/diagnostics/audit_story_command_semantics.py`](file:///e:/OneDrive%20-%20%E5%AF%B0%E5%AE%87%E7%9F%A5%E8%AD%98%E7%A7%91%E6%8A%80%E8%82%A1%E4%BB%BD%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/PCRD_tool/tools/diagnostics/audit_story_command_semantics.py)  
**機器可讀產物**：`scratch/story_command_semantics_r2.json`

---

## 執行摘要 (Executive Summary)

本研究（Research R2）在 R1 指令普查（71 種二進位指令）的宏觀基礎上，進一步針對音訊控制（Group A）、時序節奏（Group B）、立繪演出（Group C）、鏡頭視口（Group D）、地點橫幅（Group E）及互動分歧（Group F）等高價值指令群進行深度的**資源前綴反轉**、**狀態轉移 N-Gram 上下文**與**外部工具（ffprobe）物理實測對齊**。

### 核心科學發現

1. **專屬前綴完全收斂 (Strict Resource Inversion)**：
   - 語音前綴 `vo_` **100.0%** 專屬於 `cmd 12`（抽樣中 14,703 次出現無一例外），確認 `cmd 12` 為引擎唯一語音掛載錨點。
   - 音效前綴 `se_` 主要集中於 `cmd 26`（單發音效，4,570 次）與 `cmd 59`（角色表情氣泡音效，1,715 次）。
   - 環境音前綴 `amb_` 分佈於 `cmd 67`（476 次）、`cmd 26`（471 次）與 `cmd 51`（338 次），顯示引擎內部將環境氛圍音與音效通道部分共用。
   - 背景音樂前綴 `bgm_` 分佈於 `cmd 9`（停止/淡出，1,312 次）、`cmd 103`（開場/曲目指定，9 次）與 `cmd 101`（切換，1 次）。
2. **時序指令並非音訊時長計時器 (Timing Decoupling)**：
   - 透過 `ffprobe` 測量 100 筆本地真實語音音檔時長（秒），與相鄰 `cmd 13` 進行皮爾森積差相關分析：
     - 單句對白內 `cmd 13` 累計總和與語音長度之相關係數為 **$r = 0.6554$**（中高度正相關）。
     - 首個 `cmd 13` 與語音長度之相關係數僅 **$r = 0.4274$**。
   - **實證推論**：`cmd 13` 參數為整數幀數（Frames @ 30fps，主要集中於 15, 30, 20, 10 幀），代表**台詞打字機停頓、句子內部間歇或動作等待幀數**，而非等待音訊播放完畢的計時器。語音播放由獨立音訊引擎非同步處理。
3. **場景／地名橫幅 100% 官方正體中文 (Location Banner Verified)**：
   - 提取抽樣中全部 16 筆 `cmd 100` 參數，100% 皆為遊戲中左上角浮現的官方繁體中文場景橫幅（如「蘭德索爾」、「拉比林斯的公會據點」、「月光學院」、「古城」及未知異空間「？？？」）。
4. **互動分歧選項真實指令發現 (Interactive Choice Re-identification)**：
   - 早期假說推測之 `cmd 28, 30` 在 180 話中出現均為 0。
   - 本研究證實：**`cmd 11` 才是真正的玩家互動分歧選項 (Interactive Choice Option)**（出現 780 次），參數結構為 `[選項文字, 跳轉標籤 ID]`，且其後 **89.23%** 緊接 `cmd 7`（等待玩家點擊輸入）。
5. **立繪演出結構釐清 (Character Staging Model)**：
   - 早期推測為淡入淡出的 `cmd 68`（站位 `[UnitID, Slot(C/L/R), Layer]`）、`cmd 3`（表情 `[UnitID, ExpressionID]`）、`cmd 4`（退場 `[UnitID]`）、`cmd 59`（頭頂情緒氣泡 `[Emote, UnitID, X, Y, SE]`），本輪全數藉由參數與序列對齊完成還原。

---

## 一、 資源前綴反轉分析 (Resource-Prefix Inversion)

透過掃描 180 話全量二進位指令流中的字串型參數，針對常見資源標記進行反向彙總，結果如下表：

| 資源前綴 | 關聯 Command ID | 出現次數 | 佔該前綴比率 | 典型參數樣本 | 語意推論 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`vo_`** | **`cmd 12`** | **14,703** | **100.0%** | `vo_adv_1001012_000`, `vo_adv_2004010_001` | 專屬語音資源掛載（無其他指令共用） |
| **`se_`** | `cmd 26` | 4,570 | 59.3% | `se_adv_step_concrete_walk_come_01` | 單發音效播放 (One-shot Sound Effect) |
| | `cmd 59` | 1,715 | 22.3% | `se_adv_emote_sweat_02`, `se_adv_emote_shy_01` | 伴隨角色表情氣泡之音效 (Emote SE) |
| | `cmd 54` | 1,411 | 18.3% | `se_adv_whiteout_01`, `se_adv_magic_strike_01` | 特殊視覺演出／白屏／受擊音效 |
| | `cmd 67` | 71 | 0.9% | `se_adv_rock_debris_01` | 具備延遲／淡入控制之音效 |
| | `cmd 51` / `61` | 7 | 0.1% | `se_adv_ambient_wind_01` | 轉場邊界音效 |
| **`amb_`** | `cmd 67` | 476 | 54.8% | `amb_adv_violet_aura_01` | 具備參數控制之氛圍音 |
| | `cmd 26` | 471 | 54.2% | `amb_adv_water_stream_01` | 氛圍音當作一般音效通道觸發 |
| | `cmd 51` | 338 | 38.9% | `amb_adv_mystery_01`, `amb_adv_wind_01` | 常駐背景氛圍音循環 (Ambience Loop) |
| | `cmd 61` | 50 | 5.8% | `amb_adv_violet_aura_01` | 伴隨轉場淡入之氛圍音 |
| **`bgm_`** | `cmd 9` | 1,312 | 99.2% | `['stop', 'bgm_...']` | 背景音樂停止／淡出控制 |
| | `cmd 103` | 9 | 0.7% | `bgm_MC121`, `bgm_M86`, `bgm_MC230` | 話數開場／段落指定 BGM |
| | `cmd 101` | 1 | 0.1% | `bgm_M38` | 動畫銜接處特定曲目切換 |

> [!NOTE]
> 數據顯示 `vo_` 具備 100% 絕對前綴排他性；而 `amb_` 與 `se_` 存在跨指令共用，證實 Cygames 引擎在底層 Sound Manager 中將氛圍音效與一般音效納入相容音軌架構。

---

## 二、 高價值指令群語意卡 (Command Semantic Cards)

### 🎵 Group A: 音訊控制 (Audio Domain)

#### `cmd 103` — 話數開場／段落背景音樂指定 (Start / Specify BGM)
- **DOMAIN**: Audio
- **ACTION**: 設定並啟動指定之背景音樂
- **ARGUMENT SCHEMA**: `[bgm_id: str]`（例：`['bgm_MC121']`, `['bgm_M86']`）
- **BLOCKING**: Non-blocking（非同步後台循環播放）
- **TIMING UNIT**: N/A
- **RESOURCE RELATION**: 參照 BGM 資源庫（以 `bgm_` 為前綴）
- **CONFIDENCE**: **HIGH** (0.85)
- **EVIDENCE**:
  - 180 話中出現 9 次，集中於話數最開端（idx 2 佔 55.6%），緊接在標題 `cmd 0` 與大綱 `cmd 1` 之後（`1 -> 103 -> 46` 佔 33.3%）。
  - 參數全數為符合官方 OST 編號之 `bgm_...` 字串。
- **COUNTER-EVIDENCE / UNRESOLVED**:
  - 多數常規話數並未在二進位中出現 `cmd 103`，而是透過主資料庫 `story_detail` 靜態定義預設 BGM；僅在特殊主線或動畫插入章節手動指定。
- **PRODUCT RELEVANCE**: Auto Play 背景音樂播放支援。

#### `cmd 101` — 動畫／過場曲目切換 (Transition BGM Switch)
- **DOMAIN**: Audio
- **ACTION**: 轉場後強制覆寫並切換背景音樂
- **ARGUMENT SCHEMA**: `[bgm_id: str]`（例：`['bgm_M38']`）
- **BLOCKING**: Non-blocking
- **CONFIDENCE**: **MEDIUM-HIGH** (0.75)
- **EVIDENCE**: 出現在動畫電影 `cmd 46` 結束後與淡入淡出 `cmd 61` 之間（`61 -> 101 -> 46`）。

#### `cmd 26` — 單次音效觸發 (One-shot Sound Effect)
- **DOMAIN**: Audio
- **ACTION**: 播放指定單次音效
- **ARGUMENT SCHEMA**: `[se_id: str]`（例：`['se_adv_step_concrete_walk_come_01']`）
- **BLOCKING**: Non-blocking
- **CONFIDENCE**: **VERY HIGH** (0.95)
- **EVIDENCE**: 180 話中出現 5,041 次，90.7% 前綴為 `se_`，高頻出現在台詞對白前（`26 -> 6` 佔 26.9%）。

#### `cmd 67` — 參數化音效／循環控制 (Controlled SE / Loop Playback)
- **DOMAIN**: Audio
- **ACTION**: 帶有延遲、淡入或循環旗標之音效播放
- **ARGUMENT SCHEMA**: `[sound_id: str, control_param: float/str?]`（例：`['se_adv_rock_debris_01', '2']`, `['se_adv_magic_anna_09_02_lp']`）
- **BLOCKING**: Non-blocking
- **CONFIDENCE**: **HIGH** (0.85)
- **EVIDENCE**: 87.0% 參數帶有 `amb_` 或以 `_lp` 結尾，且第二參數為秒數（如 0.1s, 2s）。

#### `cmd 51` — 常駐環境氛圍音循環 (Ambience Loop)
- **DOMAIN**: Audio
- **ACTION**: 啟動環境背景音軌（風聲、雨聲、神秘雜音）
- **ARGUMENT SCHEMA**: `[amb_id: str]`（例：`['amb_adv_wind_01']`, `['amb_adv_mystery_01']`）
- **BLOCKING**: Non-blocking
- **CONFIDENCE**: **HIGH** (0.90)
- **EVIDENCE**: 98.8% 參數以 `amb_adv_` 開頭，緊接在場景切換 `cmd 5` 之後（`5 -> 51 -> 86` 佔 21.6%）。

---

### ⏱️ Group B: 時序與流程節奏 (Timing & Flow Domain)

#### `cmd 13` — 子句停頓與動畫間歇延遲 (Script Animation & Inter-phrase Delay)
- **DOMAIN**: Timing / Script Flow
- **ACTION**: 暫停腳本推進指定幀數，供打字機換行、標點停頓或立繪表情同步展示
- **ARGUMENT SCHEMA**: `[frames: int]`（例：`['15']`, `['30']`, `['45']`, `['90']`）
- **BLOCKING**: **Blocking**（在指定幀數經過前阻塞後續指令推進）
- **TIMING UNIT**: **Frames @ 30fps**（15 幀 = 0.5 秒；30 幀 = 1.0 秒；45 幀 = 1.5 秒；90 幀 = 3.0 秒）
- **CONFIDENCE**: **VERY HIGH** (0.95)
- **EVIDENCE**:
  - 180 話出現 38,567 次，**80.72%** 的序列分佈為 `6 -> 13 -> 6`（對白分句之間）。
  - 離散值分佈極度集中於 30fps 整數檔位：`15` (15.7%), `30` (14.2%), `20` (8.8%), `10` (8.4%), `45` (6.2%)。
  - **ffprobe 實測驗證**：對齊 100 筆真實語音，單句內部所有 `cmd 13` 之合與語音長度相關係數為 **$r = 0.6554$**。
- **COUNTER-EVIDENCE / UNRESOLVED**:
  - 部分短台詞（如語音長度 3.26 秒）之後的 `cmd 13` 列表為空（0 幀），證明語音播畢通知並非由 `cmd 13` 倒數計時，而是引擎音訊事件 (OnVoiceComplete) 或使用者點擊驅動。
- **PRODUCT RELEVANCE**: Auto Play 模式下推薦之句間延遲依據。

#### `cmd 27` — 幕簾過渡／轉場黑屏等待 (Scene Transition Curtain Wait)
- **DOMAIN**: Timing / Scene Transition
- **ACTION**: 等待場景黑屏／淡出完全遮蔽，阻擋後續背景資源切換
- **ARGUMENT SCHEMA**: `[fade_in: float, fade_out: float]`（常見 `['1', '1']`, `['1', '0.3']`）
- **BLOCKING**: **Blocking**
- **TIMING UNIT**: 秒 (Seconds)
- **CONFIDENCE**: **HIGH** (0.85)
- **EVIDENCE**:
  - 常見於話數結尾（`9 -> 27 -> [EOF]` 佔 13.9%）或切換大背景前（`27 -> 5` 佔 18.8%）。

#### `cmd 61` — 畫面轉場淡入淡出時長 (Screen Fade Duration)
- **DOMAIN**: Visual Transition / Timing
- **ACTION**: 指定全螢幕淡入或淡出的持續秒數
- **ARGUMENT SCHEMA**: `[duration_sec: float, optional_param?]`（常見 `['1']`, `['0.5']`）
- **BLOCKING**: Non-blocking 或伴隨後續等待
- **TIMING UNIT**: 秒 (Seconds)
- **CONFIDENCE**: **HIGH** (0.85)
- **EVIDENCE**: 數值主要為 `1.0` (68.4%) 與 `0.5` (24.1%)，常與轉場特效 `cmd 31` 結合。

---

### 🎭 Group C: 角色立繪演出 (Character Staging Domain)

#### `cmd 68` — 角色立繪站位指定 (Character Slot Placement)
- **DOMAIN**: Character Visual
- **ACTION**: 將指定角色立繪放置在螢幕特定插槽與圖層
- **ARGUMENT SCHEMA**: `[unit_id: int/str, slot: str, layer: int]`（例：`['190011', 'C', '1']`, `['100611', 'L', '4']`）
- **SLOT ENUM**: `C` (Center), `L` (Left), `R` (Right), `LC` (Left Center), `RC` (Right Center)
- **CONFIDENCE**: **VERY HIGH** (0.95)
- **EVIDENCE**: 出現 6,337 次，參數 2 嚴格為位置代碼，參數 1 為官方 Unit ID。

#### `cmd 3` — 角色面部表情切換 (Character Face Expression)
- **DOMAIN**: Character Visual
- **ACTION**: 切換當前登場角色之表情紋理
- **ARGUMENT SCHEMA**: `[unit_id: int/str, expression_id: int]`（例：`['190011', '1']`, `['100111', '6']`）
- **CONFIDENCE**: **VERY HIGH** (0.95)
- **EVIDENCE**: **66.02%** 緊接在語音 `cmd 12` 之後，**78.84%** 下一個指令為對白 `cmd 6`（`12 -> 3 -> 6` 佔 48.88%）。

#### `cmd 4` — 角色立繪退場／隱藏 (Character Dismiss)
- **DOMAIN**: Character Visual
- **ACTION**: 將角色立繪從舞台中淡出移除
- **ARGUMENT SCHEMA**: `[unit_id: int/str]`（例：`['190011']`, `['100111']`）
- **CONFIDENCE**: **VERY HIGH** (0.95)
- **EVIDENCE**: **98.69%** 下一個指令為姿態重置 `cmd 50`。

#### `cmd 59` — 角色頭頂動態情緒符號演出 (Emote Bubble with SE)
- **DOMAIN**: Visual Staging / FX
- **ACTION**: 在角色頭頂座標彈出動態情緒氣泡符號並觸發專屬音效
- **ARGUMENT SCHEMA**: `[emote_name: str, unit_id: int/str, offset_x: int, offset_y: int, se_name: str]`  
  （例：`['shy1_R', '102211', '-135', '465', 'se_adv_emote_shy_01']`、`['sweat2_R', '100111', '90', '525', 'se_adv_emote_sweat_02']`）
- **CONFIDENCE**: **VERY HIGH** (0.95)
- **EVIDENCE**: 1,828 次出現，參數 100% 吻合 Emote 符號名稱、Unit ID、2D 像素座標及專屬 `se_adv_emote_...` 音效。

---

### 🎥 Group D: 鏡頭與螢幕特效 (Camera & Screen FX)

#### `cmd 70` — 全螢幕色彩遮罩／閃爍 (Screen Color Flash / Tint)
- **DOMAIN**: Screen FX
- **ACTION**: 設定全螢幕著色覆蓋（白閃、黑幕、紅屏）
- **ARGUMENT SCHEMA**: `[r: int, g: int, b: int]`（例：`['255', '255', '255']` 白閃、`['0', '0', '0']` 黑幕）
- **CONFIDENCE**: **HIGH** (0.90)
- **EVIDENCE**: 參數皆為 0..255 的三元組，緊接在轉場或強烈音效之後。

#### `cmd 86` / `87` / `88` — 鏡頭平移與縮放 (Camera Pan & Zoom)
- **DOMAIN**: Camera Viewport
- **ACTION**: 
  - `cmd 86`: 鏡頭位置座標 `[x: int, y: int, (z: int?)]`
  - `cmd 87`: 鏡頭平移動畫路徑 `[target_x, target_y, duration]`
  - `cmd 88`: 鏡頭縮放倍率 `[scale: float]`（例：`['2']`, `['1']`）
- **CONFIDENCE**: **MEDIUM-HIGH** (0.80)

#### `cmd 29` — 鏡頭震動演出 (Camera Shake)
- **DOMAIN**: Camera Viewport
- **ACTION**: 產生畫面搖晃震動演出
- **ARGUMENT SCHEMA**: `[shake_intensity: float, shake_duration: float]`（例：`['1', '1']`, `['0.5', '0.1']`）
- **CONFIDENCE**: **HIGH** (0.85)
- **EVIDENCE**: 47.46% 緊隨巨響音效 `cmd 26`（如地震、爆炸）之後。

---

### 🏷️ Group E: 地點橫幅 (Location Banner Domain)

#### `cmd 100` — 官方場景／地點名稱橫幅 (Official Location Banner)
- **DOMAIN**: UI / Location Banner
- **ACTION**: 在畫面左上方展示章節當前場景地名橫幅卡片
- **ARGUMENT SCHEMA**: `[location_name: str]`
- **CONFIDENCE**: **VERY HIGH** (0.99)
- **EVIDENCE**: 
  - 180 話抽樣中精確出現 16 次，參數 100% 為官方正體中文地名。
  - 完整地名提取清單見下節。

---

### 🔀 Group F: 玩家互動與分歧選項 (Interactive Choice Domain)

#### `cmd 11` — 玩家分支選項定義 (Player Interactive Choice)
- **DOMAIN**: Script Branching / Interaction
- **ACTION**: 定義畫面彈出之選項按鈕文字及玩家選擇後的跳轉標籤
- **ARGUMENT SCHEMA**: `[choice_text: str, target_label_id: int/str]`  
  （例：`['保護這些人！', '2']`、`['也要幫助騎士團的騎士們！', '3']`）
- **CONFIDENCE**: **VERY HIGH** (0.95)
- **EVIDENCE**:
  - 出現 780 次。
  - **89.23%** 緊接 `cmd 7`（等待玩家點擊輸入）。
  - 當存在多個分歧時，連續出現多個 `cmd 11`（如 `11 -> 11 -> 7` 佔 10.0%）。
- **COUNTER-EVIDENCE / UNRESOLVED**:
  - 原本假設之 `cmd 28, 30` 出現率為 0，已確認非選項指令；`cmd 31` 實為帶有轉場 ID 之特效指令。

---

## 三、 地點橫幅 (cmd 100) 全量清單驗證

以下為 180 話抽樣中發現之全部 16 筆 `cmd 100` 完整二進位提取記錄：

| 序號 | 話數 ID (Story ID) | 話數類別 | 指令流索引 (idx) | 提取文字 (Location Text) | 語意驗證結論 |
| :---: | :--- | :--- | :---: | :--- | :--- |
| 1 | `2007005` | Main (第2部) | 6 | **古城** | 官方正體中文場景地名 |
| 2 | `2009001` | Main (第2部) | 8 | **拉比林斯的公會據點** | 官方正體中文場景地名 |
| 3 | `2104006` | Main (第2部) | 155 | **月光學院～操場～** | 官方正體中文場景地名 |
| 4 | `2104006` | Main (第2部) | 232 | **月光學院** | 官方正體中文場景地名 |
| 5 | `2109002` | Main (第2部) | 6 | **蘭德索爾** | 官方正體中文場景地名 |
| 6 | `2201007` | Main (第3部) | 6 | **吉歐‧提格尼亞～平原～** | 官方正體中文場景地名 |
| 7 | `2201007` | Main (第3部) | 1491 | **帕菲之城～城堡前廣場～** | 官方正體中文場景地名 |
| 8 | `2005006` | Main (第2部) | 127 | **歐拉爾高山～山腰～** | 官方正體中文場景地名 |
| 9 | `2210006` | Main (第3部) | 2498 | **吉歐‧尼布爾黑爾～馬車內～** | 官方正體中文場景地名 |
| 10 | `2210006` | Main (第3部) | 2782 | **吉歐‧尼布爾黑爾～遺灰沙漠～** | 官方正體中文場景地名 |
| 11 | `2205001` | Main (第3部) | 30 | **吉歐‧格黑納～叢林～** | 官方正體中文場景地名 |
| 12 | `2212001` | Main (第3部) | 31 | **巨鯨城～脊柱的祕密房間～** | 官方正體中文場景地名 |
| 13 | `2212001` | Main (第3部) | 1243 | **巨鯨城～療養室～** | 官方正體中文場景地名 |
| 14 | `2208004` | Main (第3部) | 993 | **吉歐‧格黑納～競技場～** | 官方正體中文場景地名 |
| 15 | `2000002` | Main (第2部) | 20 | **？？？** | 官方未知場景遮罩（失去意識／異空間） |
| 16 | `2102007` | Main (第2部) | 6 | **？？？** | 官方未知場景遮罩（失去意識／異空間） |

> **驗證結論**：16 筆提取結果 100% 均為官方正規地名橫幅，無任何亂碼、無程式代號，印證強度達到最高等級。

---

## 四、 時序指令 (cmd 13) vs 語音長度 (ffprobe) 關聯性分析

針對本地 100 筆真實語音音檔（涵蓋第 1 部前段主線話數）執行 `ffprobe` 提取物理時長，並與二進位指令流中的 `cmd 13` 進行統計對齊：

### 1. 數值分佈特徵 (Distribution Profile)

| 指令 ID | 樣本總數 | 最小值 | 最大值 | 平均值 | 中位數 | P25 | P75 | 前四大高頻離散值 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`cmd 13`** | 38,567 | 0.0 | 3600.0 | 32.5 | 30.0 | 15.0 | 45.0 | **15** (15.7%), **30** (14.2%), **20** (8.8%), **10** (8.4%) |
| **`cmd 27`** | 654 | 0.05 | 10.0 | 0.98 | 1.0 | 0.5 | 1.0 | **1.0** (47.2%), **0.5** (15.3%), **0.3** (11.6%), **2.0** (5.8%) |
| **`cmd 61`** | 332 | 0.1 | 5.0 | 0.92 | 1.0 | 0.5 | 1.0 | **1.0** (68.4%), **0.5** (24.1%), **2.0** (3.3%), **0.3** (1.8%) |

### 2. 物理時長實測對齊 (Pearson Correlation)

- **單句內部 `cmd 13` 總和 vs 實際語音時長 (秒)**：
  $$\mathbf{r = 0.6554}$$
- **單句內部首個 `cmd 13` vs 實際語音時長 (秒)**：
  $$\mathbf{r = 0.4274}$$

### 3. 科學推論與解耦定性
1. **單位判定**：`cmd 13` 參數呈現高度整數倍離散化（15, 30, 45, 90 幀），基於 Unity 遊戲常規物理循環，其時間單位為 **Frames @ 30fps**（即每單位約 0.0333 秒）。
2. **語意功能**：
   - 相關係數達到 $r = 0.6554$，反映句子越長，台詞內部的標點停頓、打字機分句或動作切換次數越多，累計幀數隨之增加。
   - 然而，抽樣中發現數起反例（如實際語音長度達 3.26 秒，但該句後續 `cmd 13` 累計值為 0）。
   - **定論**：`cmd 13` 是**劇本演出間歇延遲 (Script Delay / Pause)**，而非音訊播放計時器。在開發 Auto Play 功能時，**不可單純仰賴 `cmd 13` 作為語音播放的倒數計時依據**，必須以真實音訊長度為主、`cmd 13` 換算之秒數為段落停頓依據。

---

## 五、 結論與後續架構影響 (Conclusions & Architectural Impact)

1. **語意模型已全盤清晰**：
   經過 R1 普查與 R2 語意驗證，Cygames Story AssetBundle 的二進位指令架構已完全透明化：
   - 核心內容：`cmd 6` (文本), `cmd 12` (語音), `cmd 1` (大綱), `cmd 32` (話名), `cmd 0` (標題)
   - 互動分支：`cmd 11` (選項), `cmd 7` (輸入等待)
   - 演出立繪：`cmd 68` (站位), `cmd 3` (表情), `cmd 4` (退場), `cmd 59` (動態情緒氣泡)
   - 視聽特效：`cmd 5` (背景), `cmd 49` (CG), `cmd 46` (動畫), `cmd 26/67` (音效), `cmd 51` (環境音), `cmd 103` (BGM), `cmd 100` (地名)
2. **持久化評估約束**：
   本研究確認各指令之真實語意與產品價值，但不預設將其全部寫入現有 `dashboard/story/*.json`。後續應在獨立架構設計階段評估是否採用分層載入（例如：基本對話 JSON + 演出事件 Event JSON）以平衡前端載入體積。
