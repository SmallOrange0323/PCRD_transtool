# Phase F2B: Official ACTIVE_TRUTH_VERSION Resolution Investigation & Closure Report

> [!IMPORTANT]
> **本報告為 PCRD 資料管線 Phase F2B 官方活躍版本解析調研之最終結算報告 (Final Closure)**。  
> 遵循 Evidence-Calibrated Research Mode，嚴格區分 **OBSERVED**（直接實測資料）、**INFERRED**（合理推論）與 **VERIFIED**（有完整驗證之事實）。  
> 本階段為純唯讀調研，未修改生產管線，未更動資料庫，未執行 commit、push 或 deploy。

---

## 1. 核心架構結論 (Architectural Conclusion)

在本專案支援的工程範疇與維護原則下：

1. **未發現官方明文可直接解析之 `ACTIVE_TRUTH_VERSION` 來源**：
   官方 Game Server 握手端點回傳不透明 Base64-wrapped binary 封包，直接 MessagePack 解析未成功。
2. **官方 CDN 探測僅能證明 `CDN_AVAILABLE_VERSION`**：
   CDN 的靜態存在性（HTTP 200）僅證明資源已上傳至 CDN 池，絕對不得作為伺服器當前啟用（`ACTIVE_TRUTH_VERSION`）之證據。
3. **客戶端 / APK 逆向工程明確超出專案範疇 (Explicitly Out of Scope)**：
   使用者已明確裁定，從台版客戶端 APK 逆向動態封包加解密與金鑰衍生流程並非本專案之可行路徑，因此不作進一步探索。
4. **生產更新管線架構維持現狀**：
   生產管線繼續採用：
   $$\text{remote\_wthee\_api} \longrightarrow \text{ACTIVE\_TRUTH\_VERSION}$$
   接著執行：
   $$\text{explicit TruthVersion} \longrightarrow \text{So-net 官方 CDN} \longrightarrow \text{Raw Master DB} \longrightarrow \text{0061 Schema Mapping} \longrightarrow \text{Normalized DB}$$
5. **第三方依賴邊界聲明**：
   第三方（wthee API）**僅作為輕量版號探針**，專案已在 Phase F2A 完全切斷對第三方 `redive_tw.db` 資料庫檔案下載與格式依賴。所有 Master DB 二進位資產與欄位正規化 100% 由本地代碼自主承擔。

---

## 2. 核心語意界定 (Semantic Distinction)

本專案各層級代碼與文檔嚴格遵守以下名詞定義，兩者在邏輯與時間上均不對等：

$$\text{CDN\_AVAILABLE\_VERSION} \neq \text{ACTIVE\_TRUTH\_VERSION}$$

| 概念名詞 | 定義 | 證據依據 | 產品意涵 |
| :--- | :--- | :--- | :--- |
| **`CDN_AVAILABLE_VERSION`** | 特定 TruthVersion 之 Manifest 與 Master Bundle 已經在 So-net CDN（`img-pc.so-net.tw`）存在且可下載。 | CDN HEAD / GET 返回 HTTP 200。 | 僅代表營運「預上架」，無法證明線上營運已經切換，不能作為自動推進生產 DB 的依據。 |
| **`ACTIVE_TRUTH_VERSION`** | 當前線上伺服器與客戶端正式握手並要求使用的活躍 TruthVersion。 | 伺服器握手通訊或權威版本發布。 | 代表遊戲當前正式世界線，為生產更新與卡池資料的唯一依據。 |

---

## 3. 官方端點探測候選訊號矩陣 (Observed Candidate Signals)

本專案建立獨立診斷工具 [`tools/diagnostics/probe_official_active_truth_version.py`](file:///e:/OneDrive%20-%20%E5%AF%B0%E5%AE%87%E7%9F%A5%E8%AD%98%E7%A7%91%E6%8A%80%E8%82%A1%E4%BB%BD%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/PCRD_tool/tools/diagnostics/probe_official_active_truth_version.py)，對 So-net 官方通訊基礎設施進行實測：

### 3.1 訊號矩陣總表

| 頻道 | 端點名稱 | 目標 URL | HTTP 狀態 | 分類評級 | 觀察特徵 (Observed Features) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **game_api** | `check_agreement` | `https://api-pc.so-net.tw/check/check_agreement` | 200 OK | `PROTOCOL_UNRESOLVED` | Base64-wrapped binary（解碼長度 224B），16-byte 對齊前綴，32-char Hex 尾部。直接 MessagePack 解析不成功。 |
| **game_api** | `game_start` | `https://api-pc.so-net.tw/check/game_start` | 200 OK | `PROTOCOL_UNRESOLVED` | Base64-wrapped binary（解碼長度 320B），16-byte 對齊前綴，32-char Hex 尾部。直接 MessagePack 解析不成功。 |
| **game_api** | `check_version` | `https://api-pc.so-net.tw/check/check_version` | 200 OK | `PROTOCOL_UNRESOLVED` | Base64-wrapped binary（解碼長度 224B），直接 MessagePack 解析不成功。 |
| **cdn_static** | `cdn_root` | `https://img-pc.so-net.tw/dl/` | 403 Forbidden | `NO_GLOBAL_INDEX` | 具體 HTTP 證據顯示無 Directory Indexing，無法列出目錄。 |
| **cdn_static** | `cdn_resources_root` | `https://img-pc.so-net.tw/dl/Resources/` | 403 Forbidden | `NO_GLOBAL_INDEX` | 具體 HTTP 證據顯示無 Directory Indexing。 |
| **cdn_static** | `cdn_manifest_json` | `https://img-pc.so-net.tw/dl/Resources/manifest.json` | 404 Not Found | `NO_GLOBAL_INDEX` | 具體 HTTP 證據顯示不存在全域未版本化清單。 |
| **cdn_static** | `cdn_version_json` | `https://img-pc.so-net.tw/dl/Resources/version.json` | 404 Not Found | `NO_GLOBAL_INDEX` | 具體 HTTP 證據顯示不存在全域版本索引。 |
| **cdn_static** | `cdn_android_manifest`| `https://img-pc.so-net.tw/dl/Resources/Android/manifest`| 404 Not Found | `NO_GLOBAL_INDEX` | 具體 HTTP 證據顯示不存在平台未版本化清單。 |

### 3.2 實測細節與客觀分析 (Evidence-Calibrated)
- **OBSERVED**：
  1. 官方 Game Server API 端點允許在無登入 session 下發送請求，連線均返回 HTTP 200。
  2. 回應 Body 均為 ASCII Base64 字串，解碼後為二進位數據。
  3. 二進位數據長度皆為 16 bytes 之倍數加上 32 字元的 ASCII 十六進位雜湊結尾（例如 `224 = 192 + 32`、`320 = 288 + 32`）。
  4. 多次對同一端點發送相同空 POST 請求，每次回傳之二進位內容皆不相同，尾部 32 字元 Hex Digest 亦隨之變動。
  5. 直接將回傳數據視為標準 MessagePack 進行 unpack 會遭遇解碼例外（格式不符）。
- **INFERRED**：
  - 伺服器端握手封包採用了動態的封包加密/信封機制（例如隨機 IV 或動態 Session Token 混淆），且尾部 32 字元為校驗雜湊。
- **VERIFIED**：
  - 在缺乏台版客戶端對應的通訊協議解密實作下，無法以純 HTTP 輕量客戶端直接萃取明文 `TruthVersion`。

---

## 4. 工程決策與依賴邊界 (Engineering Decision & Provenance Boundary)

1. **維持現有 ACTIVE_TRUTH_VERSION 解析**：
   - 繼續由 `pipeline/fetch.py::resolve_remote_truth_version()` 透過 `remote_wthee_api` 作為版號探針。
   - 此設計兼顧管線輕量性、低維護負擔與高穩定性。
2. **Phase F2A 成果完整保留且完全隔離**：
   - 透過 TruthVersion 獲取官方 CDN Master DB、Bundle 解包、SQLite 解混淆、0061 欄位補全正規化，全部由本專案自主代碼完成，絕不退回 wthee 資料庫下載。
3. **診斷工具資產化**：
   - 診斷工具 `tools/diagnostics/probe_official_active_truth_version.py` 納入工具箱，供未來需要驗證官方通訊特徵或 CDN 連通性時快速調用。

---

## 5. 結算狀態 (Final Closure Status)

```text
========================================================================================
F2B STATUS: CLOSED — OFFICIAL ACTIVE VERSION RESOLUTION NOT AVAILABLE WITHIN SUPPORTED SCOPE
========================================================================================
1. Official Plaintext Active TruthVersion: NOT IDENTIFIED
2. Official CDN Manifest Scanning: CDN_AVAILABLE_ONLY (Existence != Activation)
3. Client / APK Protocol Decryption: EXPLICITLY OUT OF SCOPE
4. Production Pipeline: MAINTAINED (wthee probe -> Official CDN -> Repo-owned Normalized DB)
========================================================================================
```
