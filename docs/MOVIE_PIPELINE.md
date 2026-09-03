# 公主連結 Re:Dive — 高畫質劇情動畫與官方中文字幕壓制管線指南

本文件記錄主線劇情高畫質動畫（PC/DMM 來源）下載、官方 Unity 繁體中文字幕二進位提取、雙軌混音與 1080p 硬字幕壓制的完整工具鏈與技術規範。

---

## 一、 技術原理與資料來源

### 1. 影像來源：日版 DMM（PC 平台）高碼率頻道
* **Manifest 位址**：
  - 台版 CDN 鏡像：`https://img-pc.so-net.tw/dl/Resources/{TruthVersion}/Jpn/Movie/PC/High/manifest/movie2manifest`
  - 日版官方 Akamai：`http://prd-priconne-redive.akamaized.net/dl/Resources/{TruthVersion}/Jpn/Movie/PC/High/manifest/movie2manifest`
* **下載 Pool 規則**：
  `https://img-pc.so-net.tw/dl/pool/Movie/{PoolHash[:2]}/{PoolHash}`
* **特性**：
  - 視訊規格：日本動畫原生 **24.000 fps (24/1 fps)**，H.264 / MPEG-1 裸流。
  - 音訊規格：內建獨立音軌（BGM 配樂 + SE 音效 + VO 角色配音）。

### 2. 字幕來源：官方 Unity AssetBundle 二進位提取
* **Manifest 檔案**：`storydata2_assetmanifest`
* **字幕 Bundle 命名模式**：`a/storydata_movie_{StoryID}.unity3d` 或 `a/storydata_tw_movie_{StoryID}.unity3d`
* **底層結構**：
  MonoBehaviour 物件中包含 `recordList` 陣列，儲存官方繁中毫秒級時間軸（`startTime`, `endTime`）與台詞文本（`text`）。

---

## 二、 核心工具清單

| 工具檔案 | 功能描述 | 主要參數與指令 |
| :--- | :--- | :--- |
| [`tools/process_hd_subtitled_movies.py`](../tools/process_hd_subtitled_movies.py) | **核心旗艦管線**：下載 PC High 影像、提取台版字幕、24fps 影音同步、1080p Lanczos 升頻、50pt 遊戲原生樣式字幕壓制。 | `python tools/process_hd_subtitled_movies.py --all`<br>`python tools/process_hd_subtitled_movies.py --chapter 13` |
| [`tools/download_part3_movies.py`](../tools/download_part3_movies.py) | 批次下載官方第三部原始過場動畫（`.usm` 格式），按章節子目錄自動歸檔。 | `python tools/download_part3_movies.py` |
| [`tools/unpack_part3_movies.py`](../tools/unpack_part3_movies.py) | USM 裸流解包與基礎多軌混音，轉為一般常規 `.mp4` 影片。 | `python tools/unpack_part3_movies.py` |

---

## 三、 字幕視覺排版標準規範 (1080p)

為 1:1 還原遊戲實機視覺體驗，ASS 字幕樣式嚴格採用以下參數：
* **基準畫布**：`PlayResX: 1920`, `PlayResY: 1080`
* **字型族系**：`Microsoft JhengHei UI`（粗體 Bold）
* **字級大小**：`Fontsize: 50`
* **描邊邊框**：`Outline: 2.8`（高對比純黑邊，OutlineColour: `&H00000000`）
* **文字顏色**：純白 `&H00FFFFFF`
* **陰影模式**：`Shadow: 0`（完全無陰影）
* **版面邊距**：`MarginV: 55`（置中對齊 Alignment: 2）

---

## 四、 輸出目錄與 Git 安全門禁

所有多媒體產出檔案均存放在本地資料夾，受 [`.gitignore`](../.gitignore) 嚴格保護：
* **帶字幕 1080p 影片**：`downloads/movies/part3_hd_subtitled/ch{章節:02d}/`
* **原始動畫封包**：`downloads/movies/part3/ch{章節:02d}/`
* **Git 忽略規則**：已配置 `downloads/`、`*.usm` 與 `*.mp4`，確保大體積多媒體絕不污染程式碼倉庫與 GitHub Pages 部署包。
