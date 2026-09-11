# Story AssetBundle 高價值指令語意驗證報告 (Research R2)

**專案**：PCRD Story Map (`PCRD_transtool`)
**階段**：Issue #2 — Research R2 (High-Value Command Semantic Validation)
**狀態**：`COMPLETED` (待 External Review，僅代表本階段研究工作完成，不代表所有指令細節已確定)
**審計基準**：So-net 台服 CDN TruthVersion `00600025`（線上 Manifest 總量: 9,057 個 Story AssetBundle）
**樣本基準**：180 話確定性分層抽樣（Main 37, Chara 45, Guild 44, Event 41, System 13；與 R1 完全同源）
**分析腳本**：[`tools/diagnostics/audit_story_command_semantics.py`](tools/diagnostics/audit_story_command_semantics.py)
**約束邊界**：Production/source read-only. Writes are permitted only under scratch/.
**機器可讀產物**：`scratch/story_command_semantics_r2.json`

---

## 一、 執行摘要 (Executive Summary)

本研究（Research R2）在 R1 指令普查收斂出的 71 種二進位指令基礎上，針對音訊（Group A）、時序節奏（Group B）、立繪演出（Group C）、鏡頭視口（Group D）、地點橫幅（Group E）及互動分歧（Group F）等高價值指令群進行**資源前綴反轉**、**狀態轉移 N-Gram 上下文**與**透過 `ffprobe` 進行物理音訊時長對齊**。本報告嚴格依據專案 `Evidence-Calibrated Research Mode` 撰寫，區分直接觀察 (OBSERVED)、合理推論 (INFERRED) 與待驗證假說 (HYPOTHESIS)。

### 核心觀察與推論摘要

1. **資源前綴分佈特徵 (OBSERVED)**：
   - 語音前綴 `vo_`：在本次 180 話樣本中觀察到的 14,703 個 `vo_` 參照全部出現在 `cmd 12`（佔比 100.0%），樣本內未觀察到其他指令引用 `vo_` 前綴。
   - 音效前綴 `se_`：共 7,774 次出現，主要分佈於 `cmd 26`（4,570 次，58.79%）、`cmd 59`（1,715 次，22.06%）與 `cmd 54`（1,411 次，18.15%）。
   - 環境音前綴 `amb_`：共 1,335 次出現，分佈於 `cmd 67`（476 次，35.66%）、`cmd 26`（471 次，35.28%）、`cmd 51`（338 次，25.32%）與 `cmd 61`（50 次，3.75%）。
   - 背景音樂前綴 `bgm_`：共 1,322 次出現，分佈於 `cmd 9`（1,312 次，99.24%）、`cmd 103`（9 次，0.68%）與 `cmd 101`（1 次，0.08%）。
2. **時序指令並非音訊時長計時器 (INFERRED from Controlled Measurement)**：
   - 透過 `ffprobe` 實測 103 筆本地真實語音音檔時長（秒），並以語音邊界隔離（Voice Turn Window）排除非對白轉場指令：
     - 單句內部 `cmd 13` 累計總和與語音時長之皮爾森相關係數為 **$r = 0.6783$**（中高度正相關）。
     - 單句內部首個 `cmd 13` 與語音時長之相關係數為 **$r = 0.4161$**。
   - **反例佐證**：在樣本中觀察到語音音檔長度達 3.263 秒（如 `vo_adv_1001001_001`），但該語音段落內的 `cmd 13` 為空（累計值 0）。
   - **產品推論**：`cmd 13` 數值並非音訊播放計時器，Auto Play 功能不可依賴 `cmd 13` 倒數語音播放，必須以真實音訊事件 (Audio Ended) 或音訊實體時長為依據。
3. **場景橫幅文字呈現 (OBSERVED)**：
   - 提取 180 話抽樣中全部 16 筆 `cmd 100` 參數，觀察到其參數均為遊戲內對應的官方繁體中文場景地名（包含「蘭德索爾」、「拉比林斯的公會據點」、「月光學院」、「古城」及異空間遮罩「？？？」）。
4. **互動分歧選項指令重新識別 (OBSERVED & INFERRED)**：
   - 早期假設之 `cmd 28, 30` 在 180 話樣本中出現次數均為 0。
   - 觀察到 `cmd 11` 在樣本中出現 780 次，參數為 `[選項文字, 跳轉標籤 ID]`，且其後 89.23% 緊接 `cmd 7`。證據支持 `cmd 11` 為玩家互動選項之指令。

---

## 二、 資源前綴反轉分析 (Resource-Prefix Inversion)

所有數值均由診斷工具 [`tools/diagnostics/audit_story_command_semantics.py`](tools/diagnostics/audit_story_command_semantics.py) 執行自動計算與 Invariant 檢查（各前綴 counts 加總等於 total，ratio 加總等於 1.0）：

| 資源前綴 | 前綴總次數 (prefix_total) | 關聯 Command ID | 出現次數 (count) | 佔該前綴比例 (ratio) | 典型參數樣本 | 觀察分析 |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **`vo_`** | **14,703** | **`cmd 12`** | **14,703** | **100.0%** (1.0) | `vo_adv_1001012_000`, `vo_adv_2004010_001` | 樣本內所有 `vo_` 均位於 `cmd 12`，無其他指令共用 |
| **`se_`** | **7,774** | `cmd 26` | 4,570 | **58.79%** (0.5879) | `se_adv_step_concrete_walk_come_01` | 單發音效播放 |
| | | `cmd 59` | 1,715 | **22.06%** (0.2206) | `se_adv_emote_sweat_02`, `se_adv_emote_shy_01` | 伴隨角色頭頂情緒氣泡之音效 |
| | | `cmd 54` | 1,411 | **18.15%** (0.1815) | `se_adv_whiteout_01`, `se_adv_magic_strike_01` | 特殊視覺／白屏／受擊音效 |
| | | `cmd 67` | 71 | **0.91%** (0.0091) | `se_adv_rock_debris_01` | 帶控制參數（延遲/循環）之音效 |
| | | `cmd 51` | 4 | **0.05%** (0.0005) | `se_adv_ambient_wind_01` | 氛圍類音效以音效指令載入 |
| | | `cmd 61` | 3 | **0.04%** (0.0004) | `se_adv_transition_whoosh_01` | 轉場邊界音效 |
| **`amb_`** | **1,335** | `cmd 67` | 476 | **35.66%** (0.3566) | `amb_adv_violet_aura_01` | 帶有參數控制之氛圍音 |
| | | `cmd 26` | 471 | **35.28%** (0.3528) | `amb_adv_water_stream_01` | 氛圍音以單發音效通道播放 |
| | | `cmd 51` | 338 | **25.32%** (0.2532) | `amb_adv_mystery_01`, `amb_adv_wind_01` | 常駐背景環境氛圍音循環 |
| | | `cmd 61` | 50 | **3.75%** (0.0375) | `amb_adv_violet_aura_01` | 轉場淡入淡出中指定之氛圍音 |
| **`bgm_`** | **1,322** | `cmd 9` | 1,312 | **99.24%** (0.9924) | `['stop', 'bgm_...']` | 背景音樂淡出／停止控制 |
| | | `cmd 103` | 9 | **0.68%** (0.0068) | `bgm_MC121`, `bgm_M86`, `bgm_MC230` | 話數開場／段落指定 BGM |
| | | `cmd 101` | 1 | **0.08%** (0.0008) | `bgm_M38` | 動畫片段銜接處曲目切換 |

---

## 三、 高價值指令群語意卡 (Command Semantic Cards)

### 🎵 Group A: 音訊領域 (Audio Domain)

#### `cmd 103` — 話數開場／段落背景音樂指定 (Start / Specify BGM)
- **DOMAIN**: Audio
- **ACTION**: 設定並啟動指定之背景音樂
- **ARGUMENT SCHEMA**: `[bgm_id: str]`（例：`['bgm_MC121']`, `['bgm_M86']`）
- **BLOCKING**: LIKELY Non-blocking
- **TIMING UNIT**: N/A
- **RESOURCE RELATION**: 參照 BGM 音軌資源（`bgm_` 前綴）
- **CONFIDENCE**: **HIGH-CONFIDENCE**
- **EVIDENCE (OBSERVED)**:
  - 180 話樣本中出現 9 次，集中於話數開端（idx 2 佔 55.6%），常接在標題 `cmd 0` 與大綱 `cmd 1` 之後（`1 -> 103 -> 46` 佔 33.3%）。
  - 參數全數為官方 OST 代號（如 `bgm_MC121`）。
- **COUNTER-EVIDENCE / UNRESOLVED**:
  - 大多數常規話數在指令流中未出現 `cmd 103`，常規 BGM 多定義於資料庫 `story_detail`，僅在特殊主線或動畫插入章節觀察到二進位指令。
- **PRODUCT RELEVANCE**: Auto Play 背景音樂播放支援。

#### `cmd 101` — 動畫／過場曲目切換 (Transition BGM Switch)
- **DOMAIN**: Audio
- **ACTION**: 切換背景音樂
- **ARGUMENT SCHEMA**: `[bgm_id: str]`（樣本唯一值：`['bgm_M38']`）
- **BLOCKING**: UNRESOLVED
- **CONFIDENCE**: **LIKELY**（僅 1 次出現，不予 HIGH-CONFIDENCE）
- **RAW EVIDENCE (OBSERVED)**:
  - 話數: `2000001` (序章 前篇), 指令流索引: idx 5
  - 完整上下文序列：
    ```text
    [idx 3] cmd 46, args=['200000101', '0', '0']  (動畫片段 Part 1)
    [idx 4] cmd 61, args=['0.5']                 (淡入淡出 0.5s)
    [idx 5] cmd 101, args=['bgm_M38']             (cmd 101)
    [idx 6] cmd 46, args=['200000102']           (動畫片段 Part 2)
    ```
  - **精確序列關係**：緊接在淡入淡出 `cmd 61 ['0.5']` 之後，且位於第二段動畫 `cmd 46 ['200000102']` 之前（`61 -> 101 -> 46`）。
- **UNRESOLVED QUESTIONS**:
  - 樣本僅有 1 筆，無法確定其生命週期控制、是否強制覆寫前一曲目、或是否具備獨立音軌通道。

#### `cmd 26` — 單次音效觸發 (One-shot Sound Effect)
- **DOMAIN**: Audio
- **ACTION**: 播放指定單次音效
- **ARGUMENT SCHEMA**: `[se_id: str]`（例：`['se_adv_step_concrete_walk_come_01']`）
- **BLOCKING**: LIKELY Non-blocking
- **CONFIDENCE**: **HIGH-CONFIDENCE**
- **EVIDENCE (OBSERVED)**: 180 話樣本中出現 4,570 次（佔 `se_` 前綴 58.79%），高頻出現在台詞對白之前（`26 -> 6` 佔 26.90%）。

#### `cmd 67` — 參數化音效／循環控制 (Controlled SE / Loop Playback)
- **DOMAIN**: Audio
- **ACTION**: 帶有延遲、淡入或循環參數之音效播放
- **ARGUMENT SCHEMA**: `[sound_id: str, control_param: float/str?]`（例：`['se_adv_rock_debris_01', '2']`, `['se_adv_magic_anna_09_02_lp']`）
- **CONFIDENCE**: **HIGH-CONFIDENCE**
- **EVIDENCE (OBSERVED)**: 87.0% 參數帶有 `amb_` 或以 `_lp` 結尾，第二參數為數值字串（如 0.1, 2）。

#### `cmd 51` — 常駐環境氛圍音循環 (Ambience Loop)
- **DOMAIN**: Audio
- **ACTION**: 啟動環境背景音軌（風聲、雨聲、神秘雜音）
- **ARGUMENT SCHEMA**: `[amb_id: str]`（例：`['amb_adv_wind_01']`, `['amb_adv_mystery_01']`）
- **CONFIDENCE**: **HIGH-CONFIDENCE**
- **EVIDENCE (OBSERVED)**: 98.8% 參數以 `amb_adv_` 開頭，常緊接於場景切換 `cmd 5` 之後（`5 -> 51 -> 86` 佔 21.64%）。

---

### ⏱️ Group B: 時序與流程 (Timing & Flow Domain)

#### `cmd 13` — 子句停頓與動畫間歇延遲 (Script Animation & Inter-phrase Delay)
- **DOMAIN**: Timing / Script Flow
- **ACTION**: 暫停腳本推進，供打字機換行、標點停頓或立繪動作同步展示
- **ARGUMENT SCHEMA**: `[frames: int/float]`（常見：`['15']`, `['30']`, `['45']`, `['20']`）
- **BLOCKING**: **HYPOTHESIS** (待執行期驗證)
- **TIMING UNIT**: **HYPOTHESIS: Frames @ 30fps** (30 單位約 1.0 秒，待執行期反編譯或即時鐘表實測確認)
- **CONFIDENCE**: **HIGH-CONFIDENCE (功能定位為停頓延遲) / HYPOTHESIS (特定幀率與阻塞機制)**
- **EVIDENCE (OBSERVED & MEASURED)**:
  - 180 話樣本中出現 38,567 次，**80.72%** 的序列分佈為 `6 -> 13 -> 6`（對白分句之間）。
  - 離散值分佈高度集中於整數檔位：`15` (15.7%), `30` (14.2%), `20` (8.8%), `10` (8.4%), `45` (6.2%)。
  - **ffprobe 實測對齊 (103 筆樣本)**：單句內部 `cmd 13` 總和與語音時長之皮爾森相關係數為 **$r = 0.6783$**。
- **COUNTER-EVIDENCE (OBSERVED)**:
  - 存在語音長度達 3.263 秒但後續 `cmd 13` 為空的案例（`vo_adv_1001001_001`）。
  - 證實 `cmd 13` 並非語音播放完成計時器。
- **PRODUCT RELEVANCE**: Auto Play 模式下推薦作為語句內部標點間隔依據，但不能取代語音實際時長。

#### `cmd 27` — 幕簾過渡／轉場黑屏等待 (Scene Transition Curtain Wait)
- **DOMAIN**: Timing / Scene Transition
- **ACTION**: 等待場景黑屏／淡出遮蔽
- **ARGUMENT SCHEMA**: `[fade_in: float, fade_out: float]`（常見 `['1', '1']`, `['1', '0.3']`）
- **BLOCKING**: LIKELY Blocking
- **TIMING UNIT**: LIKELY Seconds
- **CONFIDENCE**: **HIGH-CONFIDENCE**
- **EVIDENCE (OBSERVED)**: 常見於話數結尾（`9 -> 27 -> [EOF]` 佔 13.91%）或切換背景前（`27 -> 5` 佔 18.81%）。

#### `cmd 61` — 畫面轉場淡入淡出時長 (Screen Fade Duration)
- **DOMAIN**: Visual Transition / Timing
- **ACTION**: 指定全螢幕淡入或淡出之持續時長
- **ARGUMENT SCHEMA**: `[duration: float, optional_param?]`（常見 `['1']`, `['0.5']`）
- **TIMING UNIT**: LIKELY Seconds
- **CONFIDENCE**: **HIGH-CONFIDENCE**
- **EVIDENCE (OBSERVED)**: 數值主要為 `1.0` (68.4%) 與 `0.5` (24.1%)，常與轉場特效 `cmd 31` 或環境音 `cmd 51` 配套出現。

---

### 🎭 Group C: 角色立繪演出 (Character Staging Domain)

#### `cmd 68` — 角色立繪站位指定 (Character Slot Placement)
- **DOMAIN**: Character Visual
- **ACTION**: 將指定角色立繪放置於特定插槽與圖層
- **ARGUMENT SCHEMA**: `[unit_id: int/str, slot: str, layer: int]`（例：`['190011', 'C', '1']`, `['100611', 'L', '4']`）
- **SLOT ENUM OBSERVED**: `C`, `L`, `R`, `LC`, `RC`
- **CONFIDENCE**: **HIGH-CONFIDENCE**
- **EVIDENCE (OBSERVED)**: 出現 6,337 次，參數 2 嚴格為位置符號，參數 1 為官方 Unit ID。

#### `cmd 3` — 角色面部表情切換 (Character Face Expression)
- **DOMAIN**: Character Visual
- **ACTION**: 切換登場角色之表情
- **ARGUMENT SCHEMA**: `[unit_id: int/str, expression_id: int]`（例：`['190011', '1']`, `['100111', '6']`）
- **CONFIDENCE**: **HIGH-CONFIDENCE**
- **EVIDENCE (OBSERVED)**: 66.02% 緊接在語音 `cmd 12` 之後，78.84% 下一個指令為對白 `cmd 6`（`12 -> 3 -> 6` 佔 48.88%）。

#### `cmd 4` — 角色立繪退場／隱藏 (Character Dismiss)
- **DOMAIN**: Character Visual
- **ACTION**: 將角色立繪從舞台中淡出移除
- **ARGUMENT SCHEMA**: `[unit_id: int/str]`（例：`['190011']`, `['100111']`）
- **CONFIDENCE**: **HIGH-CONFIDENCE**
- **EVIDENCE (OBSERVED)**: 98.69% 下一個指令為姿態重置 `cmd 50`。

#### `cmd 59` — 角色頭頂動態情緒符號演出 (Emote Bubble with SE)
- **DOMAIN**: Visual Staging / FX
- **ACTION**: 在角色頭頂座標彈出動態氣泡符號並播放專屬音效
- **ARGUMENT SCHEMA**: `[emote_name: str, unit_id: int/str, offset_x: int, offset_y: int, se_name: str]`  
  （例：`['shy1_R', '102211', '-135', '465', 'se_adv_emote_shy_01']`、`['sweat2_R', '100111', '90', '525', 'se_adv_emote_sweat_02']`）
- **CONFIDENCE**: **HIGH-CONFIDENCE**
- **EVIDENCE (OBSERVED)**: 1,828 次出現，參數結構高度規整，包含 Emote 名稱、Unit ID、2D 像素座標及專屬 `se_adv_emote_...` 音效。

---

### 🎥 Group D: 鏡頭與螢幕特效 (Camera & Screen FX)

#### `cmd 70` — 全螢幕色彩遮罩／閃爍 (Screen Color Flash / Tint)
- **DOMAIN**: Screen FX
- **ACTION**: 設定全螢幕著色覆蓋
- **ARGUMENT SCHEMA**: `[r: int, g: int, b: int]`（常見：`['255', '255', '255']` 白閃、`['0', '0', '0']` 黑幕）
- **CONFIDENCE**: **HIGH-CONFIDENCE**
- **EVIDENCE (OBSERVED)**: 參數皆為 0..255 的三元組數值。

#### `cmd 86` / `87` / `88` — 鏡頭平移與縮放 (Camera Pan & Zoom)
- **DOMAIN**: Camera Viewport
- **ACTION**: 
  - `cmd 86`: 鏡頭位置座標 `[x, y, (z?)]`
  - `cmd 87`: 鏡頭平移動畫路徑 `[target_x, target_y, duration]`
  - `cmd 88`: 鏡頭縮放倍率 `[scale]`（例：`['2']`, `['1']`）
- **CONFIDENCE**: **LIKELY**（參數形態吻合，但底層 Unity Camera 矩陣映射待確認）

#### `cmd 29` — 鏡頭震動演出 (Camera Shake)
- **DOMAIN**: Camera Viewport
- **ACTION**: 產生畫面搖晃震動演出
- **ARGUMENT SCHEMA**: `[shake_intensity: float, shake_duration: float]`（例：`['1', '1']`, `['0.5', '0.1']`）
- **CONFIDENCE**: **HIGH-CONFIDENCE**
- **EVIDENCE (OBSERVED)**: 47.46% 緊隨巨響音效 `cmd 26`（如地震、岩石碎裂）之後。

---

### 🏷️ Group E: 地點橫幅 (Location Banner Domain)

#### `cmd 100` — 官方場景／地點名稱橫幅 (Official Location Banner)
- **DOMAIN**: UI / Location Banner
- **ACTION**: 在畫面左上方展示章節當前場景地名橫幅卡片
- **ARGUMENT SCHEMA**: `[location_name: str]`
- **CONFIDENCE**: **HIGH-CONFIDENCE**
- **EVIDENCE (OBSERVED)**: 180 話抽樣中共提取出 16 筆記錄，文字全數為官方正規繁體中文地名。

---

### 🔀 Group F: 玩家互動與分歧選項 (Interactive Choice Domain)

#### `cmd 11` — 玩家分支選項定義 (Player Interactive Choice)
- **DOMAIN**: Script Branching / Interaction
- **ACTION**: 定義畫面彈出之選項按鈕文字及玩家選擇後的跳轉標籤
- **ARGUMENT SCHEMA**: `[choice_text: str, target_label_id: int/str]`  
  （例：`['保護這些人！', '2']`、`['也要幫助騎士團的騎士們！', '3']`）
- **CONFIDENCE**: **HIGH-CONFIDENCE**
- **EVIDENCE (OBSERVED)**:
  - 180 話樣本中出現 780 次。
  - **89.23%** 緊接 `cmd 7`（等待玩家點擊輸入）。
  - 當存在多個分歧時，連續出現多個 `cmd 11`（如 `11 -> 11 -> 7` 佔 10.0%）。
- **COUNTER-EVIDENCE (OBSERVED)**:
  - 早期假設之 `cmd 28, 30` 在本次 180 話樣本中出現次數均為 0。

---

## 四、 地點橫幅 (cmd 100) 全量清單 (OBSERVED)

180 話抽樣中所提取之全部 16 筆 `cmd 100` 原始記錄：

| 序號 | 話數 ID (Story ID) | 話數類別 | 指令流索引 (idx) | 提取文字 (Location Text) |
| :---: | :--- | :--- | :---: | :--- |
| 1 | `2007005` | Main (第2部) | 6 | **古城** |
| 2 | `2009001` | Main (第2部) | 8 | **拉比林斯的公會據點** |
| 3 | `2104006` | Main (第2部) | 155 | **月光學院～操場～** |
| 4 | `2104006` | Main (第2部) | 232 | **月光學院** |
| 5 | `2109002` | Main (第2部) | 6 | **蘭德索爾** |
| 6 | `2201007` | Main (第3部) | 6 | **吉歐‧提格尼亞～平原～** |
| 7 | `2201007` | Main (第3部) | 1491 | **帕菲之城～城堡前廣場～** |
| 8 | `2005006` | Main (第2部) | 127 | **歐拉爾高山～山腰～** |
| 9 | `2210006` | Main (第3部) | 2498 | **吉歐‧尼布爾黑爾～馬車內～** |
| 10 | `2210006` | Main (第3部) | 2782 | **吉歐‧尼布爾黑爾～遺灰沙漠～** |
| 11 | `2205001` | Main (第3部) | 30 | **吉歐‧格黑納～叢林～** |
| 12 | `2212001` | Main (第3部) | 31 | **巨鯨城～脊柱的祕密房間～** |
| 13 | `2212001` | Main (第3部) | 1243 | **巨鯨城～療養室～** |
| 14 | `2208004` | Main (第3部) | 993 | **吉歐‧格黑納～競技場～** |
| 15 | `2000002` | Main (第2部) | 20 | **？？？** |
| 16 | `2102007` | Main (第2部) | 6 | **？？？** |

---

## 五、 時序數值分佈與語音長度實測 (Timing vs Voice Duration)

### 1. 數值分佈特徵 (Distribution Profile)

| 指令 ID | 樣本總數 | 最小值 | 最大值 | 平均值 | 中位數 | P25 | P75 | 前四大高頻離散值 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`cmd 13`** | 38,567 | 0.0 | 3600.0 | 32.5 | 30.0 | 15.0 | 45.0 | **15** (15.7%), **30** (14.2%), **20** (8.8%), **10** (8.4%) |
| **`cmd 27`** | 654 | 0.05 | 10.0 | 0.98 | 1.0 | 0.5 | 1.0 | **1.0** (47.2%), **0.5** (15.3%), **0.3** (11.6%), **2.0** (5.8%) |
| **`cmd 61`** | 332 | 0.1 | 5.0 | 0.92 | 1.0 | 0.5 | 1.0 | **1.0** (68.4%), **0.5** (24.1%), **2.0** (3.3%), **0.3** (1.8%) |

### 2. ffprobe 實測對齊方法學校正 (Methodology Before vs After)

- **原始方法學 (Before)**：
  - 邊界僅以「下一個 `cmd 12`」為結束，未隔離非對白轉場指令；
  - 話數結尾 EOF 時最後一個語音未執行 flush。
  - 實測樣本數: 100；$r$ (duration vs cmd13 sum): **0.6554**；$r$ (first): **0.4274**。
- **修正後方法學 (After)**：
  - 定義嚴格 Voice Turn Window：以 `cmd 12` 為起點，遇到邊界終止集合 `{12, 7, 11, 5, 27, 46, 49}` 或話數結尾 EOF 時強制 flush；
  - 保存完整 provenance（包含 `story_id`, `voice_id`, `voice_cmd_idx`, `end_idx`, `cmd13_indices`, `cmd13_values`）；
  - 實測樣本數: 103（涵蓋話數末尾補齊之 3 筆樣本）；
  - 皮爾森相關係數 (duration vs cmd13 sum): **$r = 0.6783$**；
  - 皮爾森相關係數 (duration vs cmd13 first): **$r = 0.4161$**。
- **工具可重現性 (Reproducibility)**：
  - 探索順序：CLI `--ffprobe` ➡️ `shutil.which("ffprobe")` ➡️ Windows fallback。
  - 本次狀態：`EVALUATED`（路徑: `C:\FFmpeg\bin\ffprobe.EXE`，成功: 103，失敗: 0）。

---

## 六、 證據邊界聲明 (Evidence Boundary)

依據專案 `AGENTS.md` 規範，明確界定本研究成果之證據層級與邊界：

### 1. 分析母體與抽樣範圍
- **母體範圍 (Population Universe)**：So-net 台服 CDN TruthVersion `00600025` 共 9,057 個 Story AssetBundle。
- **抽樣範圍 (Sample Scope)**：180 個 Story AssetBundle（涵蓋 Main 37, Chara 45, Guild 44, Event 41, System 13）。非全域窮盡掃描。

### 2. 結論分級 (Confidence Stratification)

- **VERIFIED (已證實事實)**：
  - 僅限由資料本身直接自證之客觀記錄：
    - 在 180 話樣本中，`vo_` 前綴出現 14,703 次且 100% 位於 `cmd 12`。
    - 抽樣中 16 筆 `cmd 100` 參數 100% 為官方繁體中文地名。
    - 存在語音時長達 3.263 秒但相鄰 `cmd 13` 為空的實測反例（`vo_adv_1001001_001`）。
- **HIGH-CONFIDENCE (高度可信推論)**：
  - `cmd 11` 為玩家分支選項指令（780 次出現，89.23% 接 `cmd 7` 輸入等待）。
  - `cmd 68` 為角色站位指令、`cmd 3` 為面部表情切換、`cmd 4` 為立繪退場、`cmd 59` 為表情氣泡。
  - `cmd 13` 數值並非語音長度計時器，而是劇本演出停頓延遲。
- **LIKELY (最合理解釋)**：
  - `cmd 103` 為話數開場／段落指定 BGM。
  - `cmd 101` 為特定動畫片段銜接處之 BGM 切換。
  - `cmd 86`, `87`, `88` 分別對應鏡頭座標、平移路徑與縮放。
- **HYPOTHESIS (待驗證假說，不得作為生產事實)**：
  - `cmd 13` 之物理時間單位為「Frames @ 30fps」（雖高度吻合 15, 30, 45 等整數倍，但尚未取得二進位反編譯或即時鐘表計時驗證）。
  - `cmd 13` 在遊戲運行時是否屬於 Blocking（阻塞型）指令。
- **UNRESOLVED (現有證據不足以判斷)**：
  - 引擎底層語音播畢通知機制（是否為 `OnVoiceComplete` 事件回調或獨立協程）。
  - `cmd 101` 的生命週期與通道覆寫邏輯（僅 1 筆樣本，無法推論一般性規則）。

### 3. 生產實作約束 (Production Constraints)
- **禁止預設假設**：後續 Auto Play 或播放器開發，**嚴禁將 `cmd 13` 視為語音長度**。
- **持久化約束**：本研究為純調研，不預先承諾將所有演出指令持久化至現有 `dashboard/story/*.json`，架構方案留待後續設計審查評估。
- **完成定義聲明**：R2 `COMPLETED` 僅代表本階段預定調研工作完成，不代表所有指令之底層執行期機制已完全確定。
