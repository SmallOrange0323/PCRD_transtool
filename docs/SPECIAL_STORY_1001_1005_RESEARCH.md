# Special Story 1001–1005 Metadata Research

本文件記錄 1001–1005 的可驗證來源，避免日後以暫定年份或合作名稱覆寫正式 metadata。

## Corpus-level findings

- 五篇 canonical JSON 均存在於 `dashboard/story/1001.json`–`1005.json`。
- `dashboard/redive_tw.db` 的 `story_detail` / `event_story_detail` 沒有 exact `story_id` 1001–1005 rows。
- `dashboard/data/official_story_metadata.json` 提供 StoryData2 bundle provenance；1001、1002 有標題與 synopsis，1003–1005 僅有 bundle provenance。
- 這五篇是獨立 special corpus，不併入 official Extra 432，也不併入 recovered legacy 14。

## 1001

- Language: `zh-TW`
- Display title: `GAME START！`
- Group: `Grand Masters 特別劇情`
- Characters: 日和、可可蘿、怜、貪吃佩可、凱留、優衣、旁白、全員
- Text evidence: 凱留帶遊戲回美食殿堂公會小屋，啟動後眾人被吸入遊戲世界。
- Official metadata: `GAME START！`; synopsis matches the canonical text; bundle `storydata_0001001.unity3d`.
- Classification: Grand Masters / April Fool special, `PROBABLE` as a corpus classification.
- Year: `UNKNOWN` locally. The exact canonical ID is consistent with the 2022 Grand Masters story, but the local text does not encode a year.

## 1002

- Language: `zh-TW`
- Display title: `訂單很多的可麗餅店？`
- Group: `Grand Masters 特別劇情`
- Characters: 優妮、克蘿伊、拉比林斯達、雪菲、琪愛兒、旁白
- Text evidence: Game-world aftermath; a crepe shop and the Good Friends Club search for Labyrista.
- Official metadata: same title and synopsis; bundle `storydata_0001002.unity3d`.
- Classification: Grand Masters continuation / April Fool corpus, `PROBABLE`.
- Year: `UNKNOWN` locally; 2023 is plausible because Cygames announced a 2023 re-release/update with Shefi, but this mapping is not encoded in the canonical file.

## 1003

- Language: `zh-TW`
- Display title: `キャル＆ヤバイバル`
- Group: `キャル＆ヤバイバル`
- Year: `2024` (verified)
- Characters: 凱留、可可蘿、貪吃佩可、魔物
- Text evidence: opening explicitly says `4月1日愚人節`; the plot concerns an advertisement-like game world and a monster holding Karyl captive.
- Classification: April Fool special, `VERIFIED`.
- Official metadata: bundle `storydata_0001003.unity3d`; title fields are absent because the extractor did not obtain command metadata.
- External corroboration: the 2024 `キャル＆ヤバイバル` campaign was an April 1 limited game/story about an advertisement-style puzzle world.

## 1004

- Language: `ja`
- Display title: `オーエド横丁夏祭り・屋台攻略戦`
- Group: `銀だこハイボール酒場 × オーエド横丁夏祭`
- Characters: ユイ、ユカリ、ミサト、ナレーション
- Text evidence: Oedo town alley, yukata, summer festival, food stalls; the ending names `オーエド横丁夏祭り屋台攻略戦`.
- Classification: food/izakaya collaboration, `VERIFIED`.
- Year: not shown in the canonical text; do not display an unverified year.
- External corroboration: the Gin-daco Highball Sakaba collaboration included Yui, Yukari and Misato themed food/drinks and an in-game collaboration story.

## 1005

- Language: `ja`
- Display title: `オーエド横丁夏祭り・シルバーオクトパス商会`
- Group: `銀だこハイボール酒場 × オーエド横丁夏祭`
- Characters: ユイ、ユカリ、ミサト、ナレーション
- Text evidence: continuation at the Oedo summer-festival stalls; ending names the Silver Octopus Association stall.
- Classification: same food/izakaya collaboration series as 1004, `VERIFIED`.
- Year: not shown in the canonical text; do not display an unverified year.

## Corrections to prior provisional labels

The previous labels `2019 愚人節`, `2020 愚人節`, `2021 愚人節`, `碧藍幻想合作前日譚`, and `闇影詩章合作前日譚` are not supported by the local canonical text/metadata. The first three year mappings are therefore removed; the latter two collaboration mappings are contradicted by the Japanese Oedo summer-festival / food-stall text.

Recommended UI policy: keep verified story titles and groups; store year separately and show it only when verified. Keep 1001–1002 yearless, retain 1003 year 2024, and keep 1004–1005 Japanese titles without an inferred year.

External corroboration:

- Cygames 2022 Grand Masters April Fool announcement: https://priconne-redive.jp/news/information/17175/
- Cygames 2023 Grand Masters re-release/update announcement: https://priconne-redive.jp/news/information/22024/
- 2024 Karyl & Yabaival April Fool coverage: https://www.inside-games.jp/article/2024/04/01/154127.html
- Gin-daco Highball Sakaba collaboration coverage: https://www.inside-games.jp/article/2024/08/13/158383.html
