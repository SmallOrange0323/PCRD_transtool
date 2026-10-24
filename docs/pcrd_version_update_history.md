# PCRD CDN update history

## 2026-10-24 — So-net CDN 00610024

- 更新實裝角色「可璃亞（女武神）」（`139601`）戰鬥相關數據至角色圖鑑與正式正規化資料庫 `redive_tw.db`。
- 從 So-net CDN 獲取最新 TruthVersion `00610024` 加密 Master DB，經反混淆映射正規化處理為乾淨的 12 表 SQLite 資料庫。
- 驗證包含站位（150）、基本數值與成長率（1星～5星）、必殺技與全套技能（UB: 光輝接戰 -愛棘-、Skill 1: 愛心穿刺、Skill 2: 羽翼庇護、EX: 女武神模式（Q））、動作循環及角色檔案。
- 更新角色追蹤清單 `tracked_characters.json` 及資料庫驗證資訊 `db_info.json`，並同步至 `dist_story_map`。
- 新增主線第 3 部第 17 章第 4～6 話（`2217004`、`2217005`、`2217006`）：
  - 從 So-net CDN 下載並解密劇本對白 JSON 至 `dashboard/story/`。
  - 下載對應之背景圖（`500420`、`500204`、`502255`）與劇照 CG（`221700501`）並更新縮圖映射 `story_thumbnails.json`。
  - 下載語音封包（`v_t_vo_adv_2217004`～`2217006`）並完成 379 條音檔解碼轉製（.m4a）。
  - 確認第 5 話影片（`221700501`、`221700502`）串流 ID 映射與覆蓋門禁。
  - 更新 `map.js` 故事列表、單話摘要 `main_story_chapter_summaries.json` 與角色登場統計 `speaker_appearance.json`。

## 2026-08-10 — So-net CDN 00600011

- Recovered the stable website release and deployed chapter 16 stories `2216004`, `2216005`, `2216006`, and the extra story `2216101`.
- Fixed scenario-event parsing: exported story JSON now retains background changes, movie transitions, and `still_*` CG references instead of retaining dialogue only. Rebuilt chapter 16 stories `2216001`–`2216006` and `2216101`; `221600601.webp` is available as the official static preview for chapter 16 episode 6.
- Confirmed official CDN assets for `139001` (Kyouka Gothic) and `139101` (Karyl Haten Tensei), including icons, cards, and four available character-story episodes each.
- After the Kyouka Gothic banner opened, updated `139001` from the Taiwan plaintext database with its official position, profile, and combat skill descriptions.
- Added Miroku's NPC avatar from `storydata_icon_unit_192611.unity3d`.
- Reparsed all seven available chapter 16 story bundles for still references. Each has background references but no story CG command or still ID in the current Taiwan CDN manifest.
- Confirmed `2216101` is the chapter 16 extra story. It is displayed as `第3部 第16章 幕間`, while its official story title is `新人偶像小志那`.
- Downloaded and indexed the referenced chapter 16 backgrounds for use as story thumbnails.
- The additional four preallocated character-story IDs per costume unit are not yet present in the Taiwan story manifest.
