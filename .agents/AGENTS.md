# 公主連結 Re:Dive — 專案開發長期記憶與背景指南 (AGENTS.md)

本文件定義 AI 在維護與開發本專案（`PCRD_transtool`）時必須遵守的長期記憶與世界觀準則。

> [!IMPORTANT]
> **專案唯一核心定位 (Core Focus)**：
> 1. **主要生產專案 (Primary Production Project)**：**「公主連結劇情地圖（Story Map）」**。
> 2. **核心維護流程 (Primary Maintenance Workflow)**：**CDN ➡️ Story Map 資料管線（`pipeline/` 與 `update_story_map.py`）**。
> 3. **獨立實驗專案 (Side Projects)**：`translator/` 日翻中即時翻譯器等獨立實驗。
> 4. **歷史廢棄規劃 (Legacy / Deprecated)**：舊版曾規劃之競技場查隊、公會戰 BOSS 數據導航、新聞公告監控等，已全數標記為 Legacy，AI 嚴禁將其視為當前維護目標。
> 5. **官方術語基準**：所有名詞、術語均以**台灣代理商（So-net）的繁體中文官方翻譯為唯一基準**。

---

## 一、 核心世界觀與官方術語（台版官方翻譯）

在與使用者對話或處理劇情資料時，嚴禁混用日版、陸版或自譯名詞，必須嚴格採用以下台版官方譯名：

### 1. 虛擬與現實世界設定
* **阿斯特朗（Astrum）**：劇中主角們所身處的虛擬實境網路遊戲世界（《阿斯特朗傳奇》）。
* **mimi**：用來登入《阿斯特朗傳奇》的關鍵頭戴式 VR 裝置。
* **索爾之塔（Tower of Sol）**：位於遊戲世界中心、通往現實世界的關鍵巨塔。
* **米奈娃（Minerva）**：引發「再啟動（Re:Dive）」事件、掌握世界底層權限的超人工智慧（AI）。
* **再啟動（Re:Dive） / 斷線崩潰**：世界被霸瞳皇帝強行重置，導致玩家喪失現實記憶並受困於阿斯特朗。
* **諾維姆（Novium）**：主角群之一「矛依未」在劇中的代號。

### 2. 核心勢力與權能設定
* **七冠（Seven Crowns）**：掌握《阿斯特朗》底層開發權限的七位創始人。
  * **霸瞳皇帝（千里真那）**：第一部最終 Boss。其持有的權能名稱為【霸瞳天星】（千里眼，能看穿一切資料與底層程式）。
  * **迷宮女王（模索路晶）**：主角群的引路人，持有權能【迷宮女王】（創造與改造物件，即「拉比林斯達」）。
  * **誓約女君（克莉絲提娜）**：持有權能【絕對迴避】與【絕對命中】。
  * **副教授（似似花）**：變裝與複製的專家。
  * **跳躍王（拉吉拉吉）**：空間跳躍大師。
* **公主騎士（Princess Knight）**：七冠賜予其守護者的特殊能力，能強化行會成員。佑樹（騎士君）為拉比林斯達的公主騎士。

---

## 二、 重要角色官方設定與社群黑話（Meme）

為確保 AI 表現出符合社群認知的語氣與邏輯，以下角色背景與社群黑話必須牢記：

| 官方名稱 | 角色特質與官方設定 | 社群常用黑話 / Meme |
| :--- | :--- | :--- |
| **佑樹** | 本作主角、騎士君。因為「再啟動」失去記憶與心智，台詞極少。 | **失智嬰兒**（因為記憶退化成嬰兒水平，常由可可蘿照顧）、**騎士君**。 |
| **貪吃佩可** | 【美食殿堂】會長。本名尤絲蒂亞娜，因霸瞳皇帝的權能被奪走王女身份。大胃王，戰鬥力極強。 | **佩可**、口頭禪「好吃到要融化了～」。 |
| **可可蘿** | 【美食殿堂】成員。極度忠誠的引路人小精靈，稱呼主角為「主人」，無微不至地照顧主角。 | **媽**（因為對主角有無窮無盡的母性包容）、`(O` 臉表情。 |
| **凱留** | 【美食殿堂】成員。原本是霸瞳皇帝派來的臥底間諜，後被美食殿堂感化。傲嬌貓娘。 | **接頭霸王**（頭部常被玩家 P 圖到其他角色身上）、**背骨貓**（調侃其臥底身份）。 |
| **破曉之星** | 由優衣、日和、怜組成的行會，是前作的主角群。 | 核心梗：**對不起，優衣**（因為優衣個性害羞，身邊所有女角都常搶先與主角發生曖昧互動）。 |
| **萊拉耶爾** | 第三部登場的關鍵角色，大天使公主，引導主角群。 | 社群常稱其為**大天使**。 |

---

## 三、 重要主線劇情記憶節點

> [!NOTE]
> **官方命名基準**：官方遊戲介面與資料庫中僅以「第一部」、「第二部」、「第三部」（或第 1 部、第 2 部、第 3 部）命名，並無官方副標題。前端介面標籤應統一採用乾淨的官方命名「第一部」、「第二部」、「第三部」。以下小標題僅供 AI 內部理解各部劇情主題：

### 🎬 第一部（王都重置主題）
* 主角佑樹在阿斯特朗醒來，在可可蘿引導下與貪吃佩可、凱留組成【美食殿堂】。
* 凱留因懼怕「陛下」（霸瞳皇帝）而暗中監視佩可，但最終被友情打動選擇背叛霸瞳皇帝。
* **高潮**：主角群結合【破曉之星】等行會，識破假王女（霸瞳皇帝）的偽裝，在王都蘭德索爾大戰，最終擊敗霸瞳皇帝，但世界隨即迎來「再啟動（Re:Dive）」。

### 🎬 第二部：厄莉絲與救贖篇
* 世界重置後進入第二個循環，霸瞳皇帝被囚禁。新敵人**厄莉絲**（基於優衣在底層資料產生的絕望體）登場，企圖永遠將世界鎖在虛擬循環中。
* 佩可獲得「超載（Overload）」力量，美食殿堂與霸瞳皇帝暫時結盟共同對抗厄莉絲。
* **高潮**：主角佑樹用靈魂打破米奈娃的牢籠，眾人擊敗厄莉絲，成功部分打通現實世界的連結。

### 🎬 第三部：全新世界篇（現世模糊）
* 佑樹等人醒來後，發現虛擬世界《阿斯特朗》與現實世界的邊界開始崩塌模糊，現世的人與物被捲入阿斯特朗。
* 【美食殿堂】與雪菲等新角色展開全新探索，尋找讓所有人安全斷線並回到現實世界的方法。

---

## 四、 玩家社群 UI/UX 回饋與偏好
* **拒絕冰冷表格**：玩家對於本工具的期望是「沉浸式遊戲體驗」，視覺上偏好半透明毛玻璃（Glassmorphism）、櫻花粉/粉橘色漸層、動態看板娘 CG 懸停切換、話數手風琴平滑過渡。
* **台詞排版**：重視台詞呈現。應將同發言人的連續斷句、多行旁白以換行合併在同一氣泡中，降低閱讀破碎感。

---

## 五、 其他參考指南文件
* 👤 [角色設定指南](../docs/pcrd_characters.md) — 收錄各個行會、角色背景與台版譯名。
* 🎬 [主線劇情話數指南](../docs/pcrd_story_line.md) — 收錄第一部至第三部的章節大綱與話數分類邏輯。
* 🌌 [世界觀與名詞定義](../docs/pcrd_universe.md) — 收錄七冠權能、專有名詞與 So-net 官方譯名對照表。
* 📖 [官方用語集](../docs/pcrd_glossary.md) — 收錄遊戲內用語集的官方中文定義與釋義。
* 🔄 [資料更新管線手冊](../docs/PIPELINE_WORKFLOW.md) — Story Map 官方標準更新、驗證與發布工作流。

---

## 六、 多媒體素材下載指令 (手動維護工具)

> [!NOTE]
> **日常 Story Map 增量更新與發布請優先使用標準管線：`python update_story_map.py`**（參閱 [PIPELINE_WORKFLOW.md](../docs/PIPELINE_WORKFLOW.md)）。  
> 以下指令為特定單話素材的手動維護輔助工具（Manual Utility）：

1. **下載指定劇情話數的所有語音音檔 (M4A)**：
   ```bash
   python -m pipeline.fetch fetch-story-voices --story-id [story_id]
   # 或底層引擎指令：
   python tools/pcrd_fetch.py fetch-story-voices --story-id [story_id]
   ```
   * *功能*：解析該話 JSON 劇本中的所有語音 ID，自動連線鏡像大語音池下載 `.m4a` 檔案至 `dashboard/sound/[story_id]/` 目錄中。

2. **下載指定劇情話數的所有 CG 插畫與背景圖 (WebP)**：
   ```bash
   python -m pipeline.fetch fetch-story-images --story-id [story_id]
   # 或底層引擎指令：
   python tools/pcrd_fetch.py fetch-story-images --story-id [story_id]
   ```
   * *功能*：自動下載官方 CDN 明文 `bg2_assetmanifest` 與 `unit2_assetmanifest`，匹配該話在引導 Bundle 中定義的所有背景 ID 與 CG ID，再從 CDN pool 下載對應 `.unity3d` 文件並使用 UnityPy 解碼導出無損 WebP 大圖至 `dashboard/still/bg/` 與 `dashboard/still/scenario/` 目錄中。

---

## Evidence-Calibrated Research Mode

本任務涉及研究、逆向工程、語意判讀或未知資料結構分析。

請採用「證據校準模式」。
目標不是最大化結論數量，而是最大化「結論與證據強度的一致性」。

### 1. 嚴格區分 Observation / Inference / Fact

每個重要結論必須先判斷屬於哪一層：

**OBSERVED**
= 直接從目前資料、原始 command stream、檔案、runtime output 或實測結果觀察到。

**INFERRED**
= 根據 observation 做出的合理推論，但尚未直接看到 runtime implementation 或 exhaustive evidence。

**VERIFIED**
= 有直接證據可以排除主要替代解釋，或經過足夠完整的交叉驗證。

不要把 INFERRED 寫成 VERIFIED。

例如：

可以寫：
「在本次 180 話樣本中，14,703 個 vo_ reference 全部出現在 cmd12。」

除非完成 exhaustive scan，不要寫：
「vo_ 只可能出現在 cmd12。」

除非看到 runtime implementation 或足夠實測，不要寫：
「cmd12 是引擎唯一的語音掛載入口。」

---

### 2. Confidence 必須與證據類型相符

使用以下分級：

- **VERIFIED**：直接證據／可重現實測／完整資料掃描支持。
- **HIGH-CONFIDENCE**：多種獨立證據一致，但仍存在未驗證的 runtime 或資料範圍。
- **LIKELY**：最合理解釋，但仍存在合理替代解釋。
- **HYPOTHESIS**：目前值得驗證的假說，不得當作產品事實使用。
- **UNRESOLVED**：現有證據不足以判斷。

禁止僅因「看起來很合理」給 VERY HIGH / VERIFIED。

如果只有 1 個 occurrence，除非語意由參數本身直接自證，不得對 lifecycle / timing / blocking / causal behavior 給 HIGH confidence。

---

### 3. Sample Evidence 不得偷換成 Population Evidence

若研究只涵蓋抽樣資料，所有結論必須保留 scope。

例如：

正確：
「在本次 180 話樣本中未觀察到 cmd28。」

錯誤：
「cmd28 不存在。」

正確：
「本次樣本中的 vo_ reference 100% 對應 cmd12。」

錯誤：
「cmd12 是整個引擎唯一 voice command。」

只有真正 exhaustive scan 才可以使用：
- 全部
- 唯一
- 永遠
- 一定
- 100% 全域
- 完全
- 無例外

即使使用這些字，也必須明確寫出 universe：
例如「在 TruthVersion X 的 9,033 個 Story Bundle 全量掃描中」。

---

### 4. Correlation 不等於 mechanism

統計相關只能支持關聯，不得直接推出 runtime mechanism。

例如：
$r = 0.65$

只能支持：
「兩者存在中高度相關。」

不能單憑此證明：
- 「A 是 B 的計時器」
- 「A 的單位一定是 frame」
- 「runtime 使用 A 等待 B」

如果要判定 timing unit / blocking / async / callback / lifecycle，優先需要至少一種：

- runtime / decompiled implementation
- controlled experiment
- wall-clock timing measurement
- repeated counterexample testing
- independent data source
- protocol / schema evidence

否則標成 HYPOTHESIS 或 UNRESOLVED。

---

### 5. 不得補完不存在的 runtime 細節

若沒有直接證據，禁止自行補出看似合理的實作，例如：

- OnVoiceComplete
- SoundManager callback
- Unity coroutine
- async event
- internal state machine
- frame loop
- specific FPS

可以說：
「可能由 audio-ended event、使用者輸入或其他 runtime mechanism 驅動，目前未確認。」

不得說：
「由 OnVoiceComplete 驅動。」

---

### 6. 主動尋找反證

對每個 HIGH-CONFIDENCE 以上的重要結論，至少嘗試回答：

- 有沒有反例？
- 有沒有另一種同樣合理的解釋？
- 樣本是否偏斜？
- 此結論依賴哪些假設？
- 若這個假設錯了，結論是否仍成立？

若找到反例，不要把它當 nuisance 忽略。必須降低 confidence 或縮小 claim scope。

---

### 7. Evidence wording 必須可審計

優先寫：

- 「觀察到……」
- 「在本次樣本中……」
- 「與……一致」
- 「支持……解釋」
- 「目前最可能……」
- 「尚不能排除……」
- 「需要 runtime evidence 才能確認……」

避免沒有充分證據時使用：

- 「證實」
- 「確定」
- 「完全還原」
- 「唯一」
- 「必然」
- 「引擎就是」
- 「100%」
- 「全盤清晰」
- 「毫無疑問」

---

### 8. Machine Result 與 Human Interpretation 分離

所有統計數值應由 script 產生：
`count` / `total` / `ratio` / `sample_count` / `correlation`。

Markdown 報告不得自行重新人工計算同一數值。

報告應區分：

- **RAW EVIDENCE**：script / JSON 實際輸出
- **INTERPRETATION**：對 raw evidence 的語意判讀
- **PRODUCT IMPLICATION**：對 Story Map / Auto Play 等產品的影響

不要把這三層混在同一句話裡。

---

### 9. Tool Failure 必須 Fail Loudly

若研究依賴：

- ffprobe
- network
- UnityPy
- CDN
- database
- external source

而工具不可用、樣本不足或解析失敗：

不得默默跳過後仍輸出正常-looking 結論。

必須明確標記：
- `NOT_EVALUATED`
- `PARTIAL`
- `INCONCLUSIVE`

並記錄成功／失敗樣本數。

---

### 10. 最終報告必須包含 Evidence Boundary

報告最後增加：

## Evidence Boundary

明確列出：

- 本輪實際分析的 universe / sample
- 哪些結論是 VERIFIED
- 哪些是 HIGH-CONFIDENCE
- 哪些仍是 HYPOTHESIS
- 哪些是 UNRESOLVED
- 哪些結論尚不能用來驅動 production implementation
- 下一步需要什麼證據才能升級 confidence

若 evidence 不足，允許研究結果是「目前無法確認」。

「沒有得到結論」也是合法且有價值的研究結果。

---

### 11. Completion wording

不要因為研究腳本成功執行，就宣稱「語意已完全還原」。

COMPLETED 只代表：
「本階段預定研究工作已完成。」

不代表：
「所有研究問題均已得到確定答案。」

若仍有 unresolved questions，必須明確保留在報告中。

---

### 核心原則

寧可寫：
「目前證據支持 X，但 Y 尚未確認。」

也不要寫：
「已證實 X。」

然後在 External Review 才發現證據其實只支持前一句。

External Review 會優先檢查 claim 是否超出 evidence。
若不確定該使用哪個 confidence level，請選較低一級並說明缺少什麼證據。
