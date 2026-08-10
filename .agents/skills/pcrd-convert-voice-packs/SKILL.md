---
name: pcrd-convert-voice-packs
description: >-
  將從 So-net CDN 下載的語音封包（.acb/.awb 格式）解碼並轉換為網頁可播放的 .m4a 格式，輸出至 dashboard/sound/story_vo/。必須指定 --prefix 參數進行局部轉換，嚴禁全量重建。使用時機：新主線話數或活動劇情的語音封包已下載完畢，需要讓前端播放語音時。
---

# PCRD 語音封包轉換 Skill

## Overview

遊戲的語音封包以 `.acb` / `.awb` 格式加密儲存，需透過 vgmstream-cli 解碼為 `.wav`，再由 ffmpeg 轉碼為 `.m4a`（AAC 格式），才能在瀏覽器中播放。

**最高優先警告**：執行此 Skill 時**必須指定 `--prefix` 參數**進行局部轉換。若不指定，腳本會嘗試重新解碼 `downloaded_sounds/` 下的全部歷史封包（超過一萬個），耗時數小時且毫無必要。

## Dependencies

- `tools/vgmstream-cli.exe`：語音解碼工具（已預置於 `tools/` 目錄）
- `tools/ffmpeg.exe`：音訊轉碼工具（已預置於 `tools/` 目錄）
- 若上述 exe 遺失，`convert_voices.py` 會自動嘗試下載，但速度較慢

## Quick Start

```
# 主線第三部第16章（story_id 前綴 2216）的語音
python tools/convert_voices.py --prefix v_t_vo_adv_2216

# 活動語音封包
python tools/convert_voices.py --prefix v_t_vo_adv_10096

# 確認工具是否就緒
python tools/convert_voices.py --check-tools
```

---

## 語音封包命名規則

| 劇情類型 | 封包前綴格式 | 說明 |
|---|---|---|
| 主線話數 | `v_t_vo_adv_{story_group_id_prefix}` | 如 `v_t_vo_adv_2216`（第三部第16章） |
| 活動話數 | `v_t_vo_adv_{event_story_group_id}` | 如 `v_t_vo_adv_10096` |
| 角色個人劇情 | `v_t_vo_story_{unit_id}` | 如 `v_t_vo_story_138301` |

語音封包通常以 `.acb`（索引檔）+ `.awb`（資料檔）配對存在，儲存於 `downloaded_sounds/` 目錄。

---

## 執行流程說明

```bash
python tools/convert_voices.py --prefix v_t_vo_adv_2216
```

腳本 (`tools/convert_voices.py`) 執行的步驟：

1. 掃描 `downloaded_sounds/` 中所有檔名包含 `{prefix}` 的 `.acb`/`.awb` 封包
2. 對每個配對，呼叫 `vgmstream-cli.exe` 解碼為多個 `.wav` 檔案（每個語音片段一個）
3. 對每個 `.wav`，呼叫 `ffmpeg.exe` 以 AAC 128kbps 轉碼為 `.m4a`
4. 輸出所有 `.m4a` 到 `dashboard/sound/story_vo/`，命名格式為 `vo_adv_{story_id}_{序號三位數}.m4a`
5. 清理中間產物 `.wav`

**輸出位置**：`dashboard/sound/story_vo/`

---

## 確認語音是否已成功生成

轉換完成後，確認對白 JSON 中出現的語音 ID 都有對應的 m4a 檔案：

```python
import json, os, glob

# 以 story_id=2216002 為例
story = json.load(open("dashboard/story/2216002.json", encoding="utf-8"))
voice_ids = [item["voice"] for item in story if isinstance(item, dict) and item.get("voice")]

vo_dir = "dashboard/sound/story_vo"
missing = []
for vid in voice_ids:
    path = os.path.join(vo_dir, f"{vid}.m4a")
    if not os.path.exists(path):
        missing.append(vid)

print(f"總語音數: {len(voice_ids)}, 缺少: {len(missing)}")
if missing:
    print("缺少的語音 ID:", missing[:10])
```

---

## Workflow

### 新主線話數語音的標準流程

1. **確認封包已下載**：
   ```bash
   dir downloaded_sounds\*2216*
   ```
   應看到 `.acb` 和 `.awb` 配對。若不存在，須先從 So-net CDN 下載語音封包（在 `pcrd-fetch-new-data` 中的 `fetch-story-voices` 指令負責此步驟）。

2. **局部轉換**：
   ```bash
   python tools/convert_voices.py --prefix v_t_vo_adv_2216
   ```

3. **驗收語音完整性**（見上方 Python 確認腳本）。

4. 語音轉換完成後，接續執行 `pcrd-rebuild-metadata` 和 `pcrd-deploy-website`。

---

## Common Mistakes

1. **忘記 `--prefix` 導致全量重建**：這是最嚴重的錯誤。全量轉換會佔用 CPU 數小時，產生無意義的 I/O。若已誤觸，在 Task Manager 找到 `vgmstream-cli.exe` 進程並終止。
2. **vgmstream-cli.exe 版本過舊**：較舊版本對某些 ACB 格式支援不完整。若解碼失敗，刪除 `tools/vgmstream-cli.exe` 讓腳本自動重新下載最新版。
3. **轉換後漏同步至 dist**：`dashboard/sound/story_vo/` 是本地目錄，需在 `bundle` 打包時自動同步。確認 `dashboard/scripts/bundle_story_map.py` 的音訊同步邏輯已涵蓋新 story_id 前綴（`.gitignore` 已設定忽略 sound 目錄，所以語音不會被 Git 追蹤，而是在 bundle 時直接複製）。
4. **ACB 無對應 AWB**：部分短語音封包只有 `.acb`（內嵌資料，無分離的 AWB）。vgmstream-cli 可直接解碼單一 `.acb`，不需要 AWB 配對存在。
