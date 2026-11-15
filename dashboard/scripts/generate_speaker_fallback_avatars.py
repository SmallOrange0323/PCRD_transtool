"""產生泛用 NPC 總覽與角色檔案代表頭像對照表 (`dashboard/data/speaker_fallback_avatars.json`)。

設計原則（方案 A — 僅供給總覽卡片與無 explicit unit_id 之檔案封面，不動閱讀器對話氣泡）：
1. 不動 `npc_avatars.json`，因此劇情對話中 `unit_id === null` 的無立繪台詞依然保持原廠無圖呈現。
2. 全量掃描 `dashboard/story/[0-9]*.json` 對白台詞（並合併 `speaker_identity_rules.json` 的 `npc_rules` 群組別名），
   優先採用於 `avatar_assets.json` 登錄為 active PNG 之最高頻出現 `unit_id`。
3. 過濾明顯的多人並列、系統廣播／旁白、與「大量 null 台詞卻極少句意外殘留可用角色 ID」的錯掛雜訊，
   確保每個補上的泛用 NPC 頭像皆與遊戲實圖吻合；官方完全無頭像的路人則保持留白（文字佔位符）。
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = ROOT_DIR / "dashboard"
STORY_DIR = DASHBOARD_DIR / "story"
DATA_DIR = DASHBOARD_DIR / "data"

RULES_PATH = DATA_DIR / "speaker_identity_rules.json"
NPC_CATALOG_PATH = DATA_DIR / "npc_catalog.json"
NPC_AVATARS_PATH = DATA_DIR / "npc_avatars.json"
AVATAR_ASSETS_PATH = DATA_DIR / "avatar_assets.json"
APPEARANCE_PATH = STORY_DIR / "speaker_appearance.json"
UNIT_ICON_DIR = DASHBOARD_DIR / "icon" / "unit"
OUTPUT_PATH = DATA_DIR / "speaker_fallback_avatars.json"

NON_REAL_SUBSTRINGS = ("旁白", "【系統】", "？？？", "店員", "店長", "選擇肢", "選擇")
MULTI_OR_SYSTEM_SKIP = frozenset(
    {
        "兩人",
        "３人",
        "4人",
        "一夥",
        "大家",
        "全員",
        "美食殿堂",
        "阿爾克絲鍊金堂",
        "實況",
        "實況廣播",
        "告示",
        "合成語音",
        "店內電視",
        "館內廣播",
        "廣播",
        "遠處傳來的聲音",
    }
)


def build_speaker_fallback_avatars(
    story_dir: Path = STORY_DIR,
    rules_path: Path = RULES_PATH,
    npc_catalog_path: Path = NPC_CATALOG_PATH,
    npc_avatars_path: Path = NPC_AVATARS_PATH,
    avatar_assets_path: Path = AVATAR_ASSETS_PATH,
    appearance_path: Path = APPEARANCE_PATH,
    unit_icon_dir: Path = UNIT_ICON_DIR,
) -> dict[str, int]:
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    catalog = json.loads(npc_catalog_path.read_text(encoding="utf-8"))
    npc_avatars = json.loads(npc_avatars_path.read_text(encoding="utf-8"))
    avatar_assets = json.loads(avatar_assets_path.read_text(encoding="utf-8"))
    appearance = json.loads(appearance_path.read_text(encoding="utf-8"))

    active_ids = {
        int(a["unit_id"])
        for a in avatar_assets.get("assets", [])
        if a.get("status") == "active"
        and a.get("format") == "png"
        and (unit_icon_dir / f"{int(a['unit_id']):06d}.png").is_file()
    }

    protected_names = set(rules.get("entities", {}).keys()) | set(rules.get("speaker_rules", {}).keys())
    main_npc_names = {n["name"] for n in catalog.get("npcs", []) if n.get("name")}

    # 彙總 npc_rules 中同群組的說話者名稱
    group_members: dict[str, set[str]] = defaultdict(set)
    for alias_name, entries in rules.get("npc_rules", {}).items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            grp = entry.get("npc_group")
            if grp:
                group_members[grp].add(alias_name)

    uid_counts: dict[str, Counter[int]] = defaultdict(Counter)
    null_counts: Counter[str] = Counter()

    for fp in sorted(story_dir.glob("*.json")):
        if not fp.stem.isdigit():
            continue
        lines = json.loads(fp.read_text(encoding="utf-8"))
        if not isinstance(lines, list):
            continue
        for ln in lines:
            if not isinstance(ln, dict) or ln.get("type") != "dialogue":
                continue
            sp = (ln.get("name") or "").strip()
            if not sp:
                continue
            uid = ln.get("unit_id")
            if uid in (None, "", 0, "0"):
                null_counts[sp] += 1
            else:
                uid_int = int(uid)
                if uid_int in active_ids:
                    uid_counts[sp][uid_int] += 1

    fallback_map: dict[str, int] = {}
    for name in sorted(appearance.keys()):
        if not name or any(nr in name for nr in NON_REAL_SUBSTRINGS):
            continue
        if name in protected_names or name in main_npc_names or name in npc_avatars:
            continue
        if any(sep in name for sep in ("、", "＆", "&")) or name in MULTI_OR_SYSTEM_SKIP:
            continue

        keys = {name} | group_members.get(name, set())
        merged_counts: Counter[int] = Counter()
        merged_null = 0
        for k in keys:
            merged_counts.update(uid_counts.get(k, {}))
            merged_null += null_counts.get(k, 0)

        total_nonzero = sum(merged_counts.values())
        if total_nonzero == 0:
            continue

        total_lines = total_nonzero + merged_null
        top_uid, top_cnt = sorted(merged_counts.items(), key=lambda x: (-x[1], x[0]))[0]
        ratio = total_nonzero / total_lines
        is_playable_range = 100000 <= top_uid < 190000

        # 過濾大多無圖台詞中偶發殘留 1~2 句主角/他角 unit_id 的雜訊
        if ratio < 0.25 and (is_playable_range or top_cnt <= 2):
            continue
        if is_playable_range and top_cnt == 1 and merged_null > 0:
            continue

        fallback_map[name] = top_uid

    return fallback_map


def main() -> None:
    fallback_map = build_speaker_fallback_avatars()
    OUTPUT_PATH.write_text(
        json.dumps(fallback_map, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {OUTPUT_PATH}: {len(fallback_map)} fallback avatar entries")


if __name__ == "__main__":
    main()
