# Story AssetBundle 高價值指令語意驗證報告 (Research R2)

**專案**：PCRD Story Map (`PCRD_transtool`)
**階段**：Issue #2 — Research R2 (High-Value Command Semantic Validation)
**狀態**：`COMPLETED` (待 External Review，僅代表本階段研究工作完成，不代表所有指令細節已確定)
**審計基準**：So-net 台服 CDN TruthVersion `00600025`（線上 Manifest 總量: 9,057 個 Story AssetBundle）
**樣本基準**：180 話確定性抽樣（Main 55, Chara 31, Guild 31, Event 32, System 31；分層 100 + 富媒體 25 + 自適應 55，Manifest SHA-256: `6b0a6e61669d0671baa47e225fb53842d31c9b33fbdeaae324418564b8a00a5c`；抽樣策略源自 R1，但未證明 story-level identity）
**分析腳本**：[`tools/diagnostics/audit_story_command_semantics.py`](tools/diagnostics/audit_story_command_semantics.py)
**約束邊界**：Production/source read-only. Writes are permitted only under scratch/.
**機器可讀產物**：`scratch/story_command_semantics_r2.json`

---

## 一、 執行摘要 (Executive Summary)

本研究（Research R2）在 R1 指令普查收斂出的 71 種二進位指令基礎上，針對音訊（Group A）、時序節奏（Group B）、立繪演出（Group C）、鏡頭視口（Group D）、地點橫幅（Group E）及互動分歧（Group F）等高價值指令群進行**資源前綴反轉**、**狀態轉移 N-Gram 上下文**與**透過 `ffprobe` 進行物理音訊時長對齊**。本報告嚴格依據專案 `AGENTS.md` 之 `Evidence-Calibrated Research Mode` 撰寫，嚴格區分直接觀察 (OBSERVED)、合理推論 (INFERRED) 與待驗證假說 (HYPOTHESIS)。

### 核心觀察與推論摘要

1. **資源前綴分佈特徵 (OBSERVED)**：
   - 語音前綴 `vo_`：在本次 180 話樣本中觀察到的 14,703 個 `vo_` 參照全部出現在 `cmd 12`（佔比 100.0%），樣本內未觀察到其他指令引用 `vo_` 前綴。
   - 音效前綴 `se_`：共 7,774 次出現，主要分佈於 `cmd 26`（4,570 次，58.79%）、`cmd 59`（1,715 次，22.06%）與 `cmd 54`（1,411 次，18.15%）。
   - 環境音前綴 `amb_`：共 1,335 次出現，分佈於 `cmd 67`（476 次，35.66%）、`cmd 26`（471 次，35.28%）、`cmd 51`（338 次，25.32%）與 `cmd 61`（50 次，3.75%）。
   - 背景音樂前綴 `bgm_`：共 1,322 次出現，分佈於 `cmd 9`（1,312 次，99.24%）、`cmd 103`（9 次，0.68%）與 `cmd 101`（1 次，0.08%）。
2. **時序指令與本地語音長度子集對齊 (OBSERVED / INFERRED / HYPOTHESIS)**：
   - **OBSERVED (子集測量)**：針對本地可取得音檔之 103 個語音段落（集中於 `1001001`, `1001002`, `1001003` 3 話，覆蓋率為 103 / 14,703 = 0.7005%，狀態為 `PARTIAL_LOCAL_AUDIO`），以嚴格語音邊界隔離（Voice Turn Window）排除轉場指令後，單句內部 `cmd 13` 累計值與語音時長之皮爾森相關係數為 **$r = 0.6783$**；首個 `cmd 13` 相關係數為 **$r = 0.4161$**。同時觀察到語音長度達 3.263 秒但段落內 `cmd 13` 為空（累計值 0）的反例（`vo_adv_1001001_001`）。
   - **INFERRED (LIKELY)**：最合理解釋為語句間隔或打字機演出停頓延遲 (delay/pacing)，其數值與語音長度在此子集中存在中度節奏相關，但反例顯示其並非通用語音長度計時器。
   - **HYPOTHESIS / UNRESOLVED**：時間單位為 frame @ 30fps 仍屬假說；執行期是否為 blocking 機制尚未確認。
   - **PRODUCT IMPLICATION**：Auto Play 功能**不可依賴 `cmd 13` 作為語音播放時長**，必須以真實音訊事件 (Audio Ended) 或音訊實體時長為依據。
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
    [idx 4] cmd 61, args=['0.5']                 (淡入淡出 0.5)
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
- **ARGUMENT SCHEMA**: `[timing_value: numeric]`（常見：`['15']`, `['30']`, `['45']`, `['35']`, `['25']`, `['20']`, `['10']`）
- **BLOCKING**: **HYPOTHESIS / UNRESOLVED**（待二進位反編譯或 runtime trace 確認）
- **TIMING UNIT**: **HYPOTHESIS / UNRESOLVED**（推測可能為 Frames @ 30fps，但未經反編譯或 wall-clock 實測確認）
- **CONFIDENCE**:
  - 語意領域 (Timing / Delay / Pacing): **HIGH-CONFIDENCE**
  - 時間單位與阻塞屬性 (Frames @ 30fps / Blocking): **HYPOTHESIS / UNRESOLVED**
- **OBSERVED**:
  - **指令出現次數 (command_occurrence_count)**: 38,567 次（與序列上下文 total_occurrences 一致）。
  - **觀察數值筆數 (numeric_value_count)**: 38,567 筆（每指令皆為 1 個數值參數）。
  - 序列關係：**80.72%** 呈現 `6 -> 13 -> 6`（對白分句之間）。
  - 數值分佈：min=0.0, max=195.0, mean=35.91, median=30.0, p25=20.0, p75=45.0。前四大高頻離散值：`30.0` (15.25%), `15.0` (14.82%), `45.0` (8.86%), `35.0` (7.97%)。
  - **ffprobe 實測子集對齊 (103 筆樣本)**：在 3 話既有音檔子集中，單句內部 `cmd 13` 總和與語音時長之皮爾森相關係數為 **$r = 0.6783$**；首個 `cmd 13` 與語音時長之相關係數為 **$r = 0.4161$**。
  - **反例佐證 (OBSERVED)**：在樣本中觀察到語音長度達 3.263 秒但相鄰 `cmd 13` 為空的案例（`vo_adv_1001001_001`，累計總和為 0）。
- **INFERRED (LIKELY)**:
  - 最合理解釋為語句間隔或打字機演出停頓延遲 (delay/pacing)，其數值與語音長度存在粗略節奏相關，但反例顯示其並非通用語音長度計時器。
- **HYPOTHESIS / UNRESOLVED**:
  - 時間單位是否為 30fps 幀數、執行期是否阻塞協程或等待使用者輸入。
- **PRODUCT IMPLICATION**:
  - Auto Play 功能**不可依賴 `cmd 13` 作為語音播放時長**。

#### `cmd 27` — 幕簾過渡／轉場黑屏等待 (Scene Transition Curtain Wait)
- **DOMAIN**: Timing / Scene Transition
- **ACTION**: 等待場景黑屏／淡出遮蔽
- **ARGUMENT SCHEMA**: `[param_1: numeric, param_2: numeric]`（常見 `['1', '1']`, `['1', '0.3']`, `['0.5', '0.5']`）
- **BLOCKING**: **HYPOTHESIS / UNRESOLVED**（待 runtime trace 確認）
- **TIMING UNIT**: **HYPOTHESIS / UNRESOLVED**（推測為秒，但缺乏反編譯或 wall-clock 實測確認）
- **CONFIDENCE**:
  - 語意領域 (Scene Transition / Curtain Wait): **HIGH-CONFIDENCE**
  - 時間單位與阻塞屬性 (Seconds / Blocking): **HYPOTHESIS / UNRESOLVED**
- **EVIDENCE (OBSERVED)**:
  - **指令出現次數 (command_occurrence_count)**: 654 次（與序列上下文 total_occurrences 一致）。
  - **觀察數值筆數 (numeric_value_count)**: 1,308 筆（每指令皆為 2 個數值參數，654 × 2 = 1,308）。
  - 序列關係：常見於話數結尾（`9 -> 27 -> [EOF]` 佔 13.91%）或切換背景前（`27 -> 5` 佔 18.81%）。
  - 數值分佈：min=0.0, max=1.0, mean=0.95, median=1.0, p25=1.0, p75=1.0。高頻值：`1.0` (92.51%), `0.5` (4.28%), `0.3` (2.52%), `0.0` (0.31%)。

#### `cmd 61` — 畫面轉場淡入淡出時長 (Screen Fade Duration)
- **DOMAIN**: Visual Transition / Timing
- **ACTION**: 指定全螢幕淡入或淡出之持續時長
- **ARGUMENT SCHEMA**: `[param_1: numeric, param_2: optional_param?]`（常見 `['1']`, `['0.5']`）
- **BLOCKING**: **HYPOTHESIS / UNRESOLVED**（待 runtime trace 確認）
- **TIMING UNIT**: **HYPOTHESIS / UNRESOLVED**（推測為秒，但缺乏反編譯或 wall-clock 實測確認）
- **CONFIDENCE**:
  - 語意領域 (Screen Fade Duration): **HIGH-CONFIDENCE**
  - 時間單位與阻塞屬性 (Seconds / Blocking): **HYPOTHESIS / UNRESOLVED**
- **EVIDENCE (OBSERVED)**:
  - **指令出現次數 (command_occurrence_count)**: 332 次（與序列上下文 total_occurrences 一致）。
  - **觀察數值筆數 (numeric_value_count)**: 333 筆（331 次帶 1 參數，1 次帶 2 參數）。
  - 序列關係：常與轉場特效 `cmd 31` 或環境音 `cmd 51` 配套出現。
  - 數值分佈：min=0.5, max=3.0, mean=1.01, median=1.0, p25=1.0, p75=1.0。高頻值：`1.0` (97.90%), `0.5` (0.90%), `3.0` (0.60%), `2.0` (0.60%)。

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

### 1. 樣品清單與解析審計 (Sample Manifest & Parsing Accounting)

所有樣本清單、解析狀態與音檔覆蓋計數均由診斷腳本精確記帳並持久化於 JSON 根部：

| 記帳層級 | 指標項目 | 數值 | 狀態 / 解釋 |
| :--- | :--- | :---: | :--- |
| **Sample Manifest Accounting** | `sample_manifest_count` | 180 | 確定性抽樣清單總話數 |
| | `sample_manifest_sha256` | `6b0a6e61669d0671baa47e225fb53842d31c9b33fbdeaae324418564b8a00a5c` | Canonical JSON SHA-256 數位簽名 |
| | 樣品類別組成 (by Category) | Main: 55, Chara: 31, Guild: 31, Event: 32, System: 31 | 5 大類別加總等於 180 |
| | 抽樣類型組成 (by Type) | stratified: 100, rich_media: 25, adaptive: 55 | 3 種來源加總等於 180 |
| **Bundle Parsing Accounting** | `requested_story_samples` | 180 | 確定性抽樣計畫請求數 |
| | `successfully_parsed_stories` | 180 | 成功載入並完成二進位指令流解析之話數 |
| | `failed_story_parses` | 0 | 解析失敗話數（100% 成功） |
| **Audio Alignment Accounting** | `voice_turn_candidates` | 14,703 | 180 話中符合語音轉場（Voice Turn Window）之候選總數 |
| | `local_audio_present` | 103 | 本地既有音檔存在之樣本數（來自話數 `1001001`, `1001002`, `1001003`） |
| | `local_audio_missing` | 14,600 | 本地未下載音檔之候選總數（Fail Loudly 記帳） |
| | `audio_coverage_ratio` | 0.007005 (0.7005%) | 本地音檔覆蓋比例 (`103 / 14703`) |
| | `coverage_status` | `PARTIAL_LOCAL_AUDIO` | 音訊覆蓋範圍狀態判定（僅子集評估） |
| | `alignment_story_count` | 3 | 實測音檔來源之話數數量 |
| | `alignment_story_ids` | `['1001001', '1001002', '1001003']` | 實測音檔所屬話數 ID 清單（各 48, 30, 25 筆） |
| | `probe_attempted` | 103 | 嘗試執行 `ffprobe` 時長探測次數 |
| | `probe_success` | 103 | 成功獲取音訊精確時長次數 |
| | `probe_failed` | 0 | 探測失敗次數 |
| | `max_alignment_samples` | 150 | 對齊上限閾值參數 |
| | `successful_alignment_samples` | 103 | 最終納入統計與關聯計算之有效樣本數 |
| | `alignments` 完整陣列長度 | 103 | 機器可讀 JSON 中保存之完整 provenance 記錄數 |
| **Tool Execution Status** | `evaluation_status` | `EVALUATED` | 工具執行狀態（可重現探測完成） |
| | `ffprobe_path_used` | `C:\FFmpeg\bin\ffprobe.EXE` | 執行期探測使用之實體二進位路徑 |

> [!NOTE]
> **完整 Provenance 保存**：所有 103 筆對齊樣本之完整溯源資料（包含 `story_id`, `voice_id`, `actual_duration_sec`, `voice_command_index`, `segmentation_end_index`, `included_cmd13_indices`, `included_cmd13_values`, `cmd13_count`, `cmd13_sum`, `cmd13_first`）均 100% 完整保存於 `scratch/story_command_semantics_r2.json` 的 `"alignments"` 陣列中，且 `successful_alignment_samples == len(alignments) == 103`。同時提供 `"alignment_preview"`（前 10 筆）便於快速預覽。

### 2. 時序指令數值分佈特徵 (Distribution Profile)

所有數值統計值均直接由診斷腳本輸出，明確區分指令出現次數與數值參數計數：

| 指令 ID | 指令出現次數 (command_occurrence_count) | 觀察數值筆數 (numeric_value_count) | 每指令參數數分佈 (numeric_values_per_command) | 最小值 (min) | 最大值 (max) | 平均值 (mean) | 中位數 (median) | P25 | P75 | 前四大高頻離散數值 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`cmd 13`** | 38,567 | 38,567 | 1 參數: 38,567 (100.0%) | 0.0 | 195.0 | 35.91 | 30.0 | 20.0 | 45.0 | **30.0** (15.25%), **15.0** (14.82%), **45.0** (8.86%), **35.0** (7.97%) |
| **`cmd 27`** | 654 | 1,308 | 2 參數: 654 (100.0%) | 0.0 | 1.0 | 0.95 | 1.0 | 1.0 | 1.0 | **1.0** (92.51%), **0.5** (4.28%), **0.3** (2.52%), **0.0** (0.31%) |
| **`cmd 61`** | 332 | 333 | 1 參數: 331 (99.7%), 2 參數: 1 (0.3%) | 0.5 | 3.0 | 1.01 | 1.0 | 1.0 | 1.0 | **1.0** (97.90%), **0.5** (0.90%), **3.0** (0.60%), **2.0** (0.60%) |

### 3. ffprobe 實測對齊方法學與結果

- **語音邊界隔離 (Voice Turn Window)**：
  - 以 `cmd 12` 為起點，遇到邊界終止集合 `{12, 7, 11, 5, 27, 46, 49}` 或話數結尾 EOF 時強制 flush，確保非對白轉場指令不會被誤計入該句對白。
- **對齊結果**：
  - 實測對齊樣本數: 103 筆（來自 3 話主線：`1001001`、`1001002`、`1001003`）；
  - 皮爾森相關係數 (語音時長 vs 句內 `cmd 13` 累計總和): **$r = 0.6783$**；
  - 皮爾森相關係數 (語音時長 vs 句內首個 `cmd 13`): **$r = 0.4161$**。
- **反例分析 (Counter-example)**：
  - 語音 `vo_adv_1001001_001` 實體音訊長度為 3.263 秒，但在該 Voice Turn Window 內未出現任何 `cmd 13`（累計總和為 0）。
  - 此反例充分證明 `cmd 13` 並非通用語音播放長度計時器。

---

## 六、 證據邊界聲明 (Evidence Boundary)

依據專案 `AGENTS.md` 規範，明確界定本研究成果之證據層級與邊界：

### 1. 分析母體與抽樣範圍
- **母體範圍 (Population Universe)**：So-net 台服 CDN TruthVersion `00600025` 共 9,057 個 Story AssetBundle。
- **抽樣範圍 (Sample Scope)**：獨立確定性 180 個 Story AssetBundle（Main 55, Chara 31, Guild 31, Event 32, System 31；分層 100 + 富媒體 25 + 自適應 55，Manifest SHA-256: `6b0a6e61669d0671baa47e225fb53842d31c9b33fbdeaae324418564b8a00a5c`）。
- **樣品同源性聲明**：本抽樣隊列採用源自 R1 的抽樣演算法策略生成，但現有 R1 機器產物未持久化全量 180 話之 story ID 清單，**未證明與 R1 為 story-level 完全一致之樣品**。
- **音訊對齊邊界與集中性揭露**：
  - 皮爾森相關係數測量範圍為「本地可取得音檔之 103 個 voice-turn 子集」，覆蓋率為 0.7005%（103 / 14,703），覆蓋狀態判定為 `PARTIAL_LOCAL_AUDIO`。
  - 103 筆實測樣本高度集中於 3 話主線章節（`1001001` 共 48 筆、`1001002` 共 30 筆、`1001003` 共 25 筆），不得外推為 14,703 個候選母體之全域相關性。
  - 工具執行狀態 `EVALUATED` 僅代表探測工具鏈執行成功，不代表音訊母體已全量評估。

### 2. 結論分級 (Confidence Stratification)

- **VERIFIED (已證實事實)**：
  - 僅限由資料本身直接自證之客觀記錄：
    - 在 180 話樣本中，`vo_` 前綴出現 14,703 次且 100% 位於 `cmd 12`。
    - 抽樣中 16 筆 `cmd 100` 參數 100% 為官方繁體中文地名。
    - 存在語音時長達 3.263 秒但相鄰 `cmd 13` 為空的實測反例（`vo_adv_1001001_001`）。
- **HIGH-CONFIDENCE (高度可信推論)**：
  - `cmd 11` 為玩家分支選項指令（780 次出現，89.23% 接 `cmd 7` 輸入等待）。
  - `cmd 68` 為角色站位指令、`cmd 3` 為面部表情切換、`cmd 4` 為立繪退場、`cmd 59` 為表情氣泡。
  - `cmd 13` 語意領域為劇本演出或分句間隔停頓延遲 (pacing/delay)，其數值在實測子集中與文本/語音長度存在中度正相關。
  - `cmd 27` 語意領域為幕簾過渡／轉場黑屏等待。
  - `cmd 61` 語意領域為全螢幕畫面淡入淡出。
- **LIKELY (最合理解釋)**：
  - `cmd 103` 為話數開場／段落指定 BGM。
  - `cmd 101` 為特定動畫片段銜接處之 BGM 切換。
  - `cmd 86`, `87`, `88` 分別對應鏡頭座標、平移路徑與縮放。
- **HYPOTHESIS / UNRESOLVED (待驗證假說，不得作為生產事實)**：
  - **時序物理單位**：`cmd 13` 之物理單位是否為「Frames @ 30fps」；`cmd 27` 與 `cmd 61` 之物理單位是否為「Seconds」（均缺乏反編譯或 wall-clock 實測證據）。
  - **執行期阻塞機制**：`cmd 13`、`cmd 27`、`cmd 61` 在 Unity 執行期是否屬於 Blocking（阻塞型）指令、是否涉及協程等待或非同步計時。
  - **引擎語音回調機制**：底層語音播畢通知機制（是否為 `OnVoiceComplete` 事件回調或獨立協程）。
  - **單例指令通道規則**：`cmd 101` 的生命週期與通道覆寫邏輯（僅 1 筆樣本，無法推論一般性規則）。

### 3. 生產實作約束 (Production Constraints)
- **禁止預設假設**：後續 Auto Play 或播放器開發，**嚴禁將 `cmd 13` 視為通用語音長度**。
- **持久化約束**：本研究為純調研，不預先承諾將所有演出指令持久化至現有 `dashboard/story/*.json`，架構方案留待後續設計審查評估。
- **完成定義聲明**：R2 `COMPLETED` 僅代表本階段預定調研工作完成，不代表所有指令之底層執行期機制已完全確定。
