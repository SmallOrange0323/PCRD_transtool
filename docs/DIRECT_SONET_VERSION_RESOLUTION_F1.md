# Phase F1: Direct So-net Version Resolution Investigation Report

> [!IMPORTANT]
> **本報告為 PCRD 資料管線 Phase F1 獨立調研成果 (Investigation Only)**。  
> 遵循 Evidence-Calibrated Research Mode，嚴格區分 **OBSERVED**（直接實測資料）、**INFERRED**（合理推論）與 **VERIFIED**（有完整驗證之事實）。  
> 唯讀調研過程未修改任何生產管線代碼，未觸碰資料庫，未執行 commit、push 或 deploy。

---

## 1. 核心概念嚴格界定 (Conceptual Boundary)

本報告與後續管線架構必須嚴格區分以下兩種概念，兩者**絕對不相等**：

$$\text{CDN\_AVAILABLE\_VERSION} \neq \text{ACTIVE\_TRUTH\_VERSION}$$

1. **`CDN_AVAILABLE_VERSION`（最高可觀察 CDN 版本 / `highest_observed_cdn_version`）**：
   - **定義**：該版本之 `masterdata2_assetmanifest` 確實已在 So-net CDN（`img-pc.so-net.tw`）成功部署且可公開存取（HTTP 200）。
   - **性質**：僅代表靜態資源「已上傳至 CDN 池」，極可能為**營運預上架（Pre-deployment）**，或尚未正式對玩家客戶端開放。
2. **`ACTIVE_TRUTH_VERSION`（正式營運活躍版本）**：
   - **定義**：遊戲正式 Game Server 在客戶端連線握手（CheckVersion/CheckAgreement）時，要求正式客戶端使用的 TruthVersion。
   - **性質**：代表遊戲當前真正運行的世界線版本。

---

## 2. 官方訊號探測成果與分析 (Part A & D)

### 2.1 官方 Game Server API 探測
- **探測端點**：`https://api-pc.so-net.tw/check/check_agreement` 與 `https://api-pc.so-net.tw/check/game_start`
- **OBSERVED**：
  - 發送空 POST 請求時返回 `HTTP 200 OK`，`Content-Type: application/x-msgpack`，長度 300 bytes。
  - Payload 內容為不透明官方二進位回應（opaque official binary response / protocol unresolved）。
- **結論**：
  - 官方確實存在純官方握手端點，且在無帳號登入狀態下即可連線。
  - **但協議尚未解析 (Protocol Unresolved)**：在缺乏可重現之 cipher / mode / key derivation 證據前，不得定性其加密算法（非確定性 AES-CBC 或其他實作）。若無台服客戶端 APK 逆向提取動態金鑰與解密 MessagePack，無法從中直接萃取明文 `truth_version`。這屬於高成本認證/加密握手，不適合作為輕量 CI/CD 管線的日常探針。

### 2.2 官方 CDN 探測 (img-pc.so-net.tw)
- **OBSERVED**：
  - CDN 屬於純靜態存儲，無 Directory Indexing，亦無任何 `latest.json` 或 `/latest` redirect 路由。
  - 所有版本資源以 `{TruthVersion}` 作為 URL Path 節點。

---

## 3. Direct CDN Candidate Scanner 實測數據 (Part B, D & E)

透過診斷工具 [`tools/diagnostics/probe_sonet_versions.py`](file:///e:/OneDrive%20-%20%E5%AF%B0%E5%AE%87%E7%9F%A5%E8%AD%98%E7%A7%91%E6%8A%80%E8%82%A1%E4%BB%BD%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/PCRD_tool/tools/diagnostics/probe_sonet_versions.py) 進行實地 HEAD 與輕量 Manifest GET 驗證：

### 3.1 關鍵版本驗證矩陣 (Target Matrix)

| TruthVersion | CDN 狀態 (Status) | HTTP Code | Manifest 大小 | masterdata MD5 | Masterdata Pool Hash | Probe 延遲 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`00600025`** | **EXISTS** | 200 | 97 B | `136b8730f1e1f233452d6bc09d9d25ed` | `d93a6e336023c2fe` | 141 ms |
| **`00610001`** | **EXISTS** | 200 | 97 B | `2f6e9bcde1e06fa99e9be1fd555d8d5f` | `5d7ee633e20eabe7` | 314 ms |
| **`00610002`** | **EXISTS** | 200 | 97 B | `66f8d13053709fa2b3d83214710b3595` | `4e9786dd9deabbc5` | 125 ms |
| **`00610003`** | **EXISTS** | 200 | 97 B | `98ae47db3501a3cf882b406ce1e98bb4` | `a170564f77cfc427` | 506 ms |
| **`00610004`** | **EXISTS** | 200 | 97 B | `98ae47db3501a3cf882b406ce1e98bb4` | `a170564f77cfc427` (共用) | 192 ms |
| **`00610005`** | **EXISTS** | 200 | 97 B | `19f074d6c6e73aa89947841ec4301a5b` | `18b4384fcaaf46b2` | 235 ms |
| **`00610006`** | **EXISTS** | 200 | 97 B | `6a439df6cecf9040316e6d1945f448c3` | `96c7bef6cb8bde2b` | 169 ms |
| **`00610007`** | **EXISTS** | 200 | 97 B | `b161fbcd7407df9f2226886eeb828b09` | `8835ae79b608ae98` | 124 ms |
| **`00610008`** | **EXISTS** | 200 | 97 B | `e590b77dd2a9062a4181ba3ea8f545c5` | `ea31a8de308910be` | 150 ms |
| **`00610009`** | **NOT_FOUND** | 404 | - | - | - | 186 ms |
| **`00610010`** | **NOT_FOUND** | 404 | - | - | - | 179 ms |
| **`00620001`** | **NOT_FOUND** | 404 | - | - | - | 142 ms |

### 3.2 歷史 Gap 真相還原 (Observation vs Invariant)

- **OBSERVED**：
  在本次實測樣本中，`00610001`～`00610008` 連續存在，中間無 404。  
  **重要約束**：此結果僅為本次樣本的 **Observation（觀察事實）**，**絕對不是 Protocol Invariant（協議保證不變量）**。官方流水線仍隨時可能因為內部測試版作廢而產生號碼跳躍。
- **INFERRED (歷史紀錄為何呈現跳號)**：
  本地 `version_history.json` 出現 `00610002` ➡️ `00610007` 的原因，不是 CDN 伺服器端跳號，而是**本地執行更新時的時間間隔（採樣稀疏）**所致。
- **VERIFIED (真正的 Gap 出現在 Major Prefix 跨越)**：
  - `00500033` 結束（`00500034` 為 404）➡️ 直接躍升為 `00600001`。
  - `00600025` 結束（`00600026` 為 404）➡️ 直接躍升為 `00610001`。
  - 前綴 `0050`、`0060`、`0061` 對應遊戲 App 的主程式大版本（如 App 5.0、6.0、6.1）。

---

## 4. 關鍵問題精確答覆 (10 Questions & Answers)

### Q1. 是否找到官方 ACTIVE_TRUTH_VERSION 訊號？
**【答】尚未找到低成本明文的官方 ACTIVE 訊號 (NO)**。  
官方 Game API 端點（`api-pc.so-net.tw`）回傳之版本資訊為不透明二進位封包（protocol unresolved），無法在不持有台服動態解密金鑰的情況下直接讀取。

### Q2. 若有，是否不需第三方、不需登入或高成本認證？
**【答】不符合 (HIGH FRICTION)**。  
雖然連線該端點不需玩家帳號密碼，但解密其二進位封包需要逆向維護台服加密協議，成本與維護負擔過高。

### Q3. 若沒有，CDN scanning 能證明什麼、不能證明什麼？
**【答】**
- **能證明（VERIFIED）**：
  - 證明 So-net 已經在 CDN 上架了某版本的 Manifest 與 Master DB。
  - 證明該版本的 Master DB 可以被解密並建立 Provenance 鏈（Hash 對齊）。
- **不能證明（UNRESOLVED）**：
  - 不能證明該版本目前已在線上正式對玩家開放（無法排除是維護前的預上架）。
  - 不能證明該版本對應的所有卡面、語音、背景已在 Pool 就緒。

### Q4. 00610002～00610007 的實際 CDN existence 結果？
**【答】本次實測 00610001～00610008 連續存在 (100% EXISTS)**。  
中間的 00610003～00610006 全部返回 HTTP 200，且各自具備合法的 `masterdata_master.unity3d` Pool Hash。

### Q5. 是否確認版本號會出現 gap？
**【答】分層確認**：
- **同前綴內**：在本次針對 0050、0060、0061 的實測樣本中未觀察到 gap，但不得視為 protocol invariant。
- **跨前綴時**：必然出現 gap（如 `00600025` ➡️ `00610001`，中間跳過所有 00600026+ 號碼）。

### Q6. prefix 跨越應採什麼搜尋策略？
**【答】雙層窗口步進策略 (Two-Tier Window Probe)**：
1. **Tier 1 (同前綴探測)**：從當前版本向後探測（例如 `num + 1` 到 `num + 15`，容忍 bounded gap）。
2. **Tier 2 (前綴溢出躍升)**：若當前前綴遭遇連續 5 個以上 404，探測器應主動嘗試 `prefix + 1` 的前幾個號碼（例如當 `00610009`、`00610010` 404 時，探測 `00620001` 與 `00620002`）。

### Q7. 是否能建立可靠 production resolver？
**【答】可以建立「CDN 資源就緒解析器 (CDN Readiness Resolver)」，但不能單獨作為「營運狀態確認器」**。  
此 Resolver 可以 100% 擺脫第三方，自主算出線上 CDN 目前釋出的最高版本號 `highest_observed_cdn_version`。

### Q8. 若只能取得 highest_observed_cdn_version，是否足以取代目前 wthee freshness gate？
**【答】不足以直接取代新鮮度確認門禁**。  
- 因為 $\text{CDN\_AVAILABLE\_VERSION} \neq \text{ACTIVE\_TRUTH\_VERSION}$。
- Asset Completeness Gate **只能證明我們網站所需的角色卡面與語音已就緒，絕不能證明 Game Server 已正式切換該 TruthVersion**。
- 若要在無第三方情況下部署，必須建立明確的營運政策（例如：只要必要資產齊全即視為發布就緒），而非宣稱新鮮度已獲官方確認。

### Q9. 建議 Phase F2 分流規劃
**【答】本研究強烈建議分流為 F2A 與 F2B 兩個獨立階段**：

- **F2A — Direct So-net Master DB Acquisition: GO**  
  - **目標**：移除 wthee 的第二項 critical dependency（`redive_tw.db` 下載）。
  - **理由**：直接從 So-net CDN 下載並解密 Master DB 的技術路徑完全可行、自洽且高可靠，能確保資料庫來源 100% 官方正版。
- **F2B — Official Active TruthVersion Resolution: INVESTIGATION REQUIRED**  
  - **目標**：評估是否能無成本或低成本解析官方 `ACTIVE_TRUTH_VERSION`。
  - **現況**：目前 Game API 為 opaque binary，需進一步研究是否具備免逆向之替代官方訊號，不宜貿然冒進接入生產。

### Q10. 不修改任何 production code
**【已嚴格遵守】**。未修改任何 `pipeline/`、`dashboard/` 或生產代碼。

---

## 5. 目前生產依賴現況與 F2A 目標 (Critical Dependencies)

目前管線中對 `wthee.xyz` 存在兩項 Production Critical Dependency：
1. **TruthVersion Probe**（呼叫 `/db/info/v2` 探測最新版號）
2. **`redive_tw.db` Download**（在需要更新時下載其解密資料庫）

> [!NOTE]
> **F2A 核心目標**：**只移除第 2 項（`redive_tw.db` 下載）**。  
> 讓資料庫的獲取徹底回歸 So-net 官方來源，建立由官方 Manifest 驅動、經完整 SQLite 驗證與原子替換的 canonical primitive。
