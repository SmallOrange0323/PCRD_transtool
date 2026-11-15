#!/usr/bin/env python3
"""
從既有劇情登場索引、身分規則與頭像資產清冊，決定性建置 NPC 頭像圖鑑索引 (`dashboard/data/npc_catalog.json`)。

遵循階段二規範：
1. 僅收錄具備實際對話登場紀錄、非可操作角（entity）、無日文假名、非次要別名，且在
   `dashboard/data/avatar_assets.json` (active PNG) 與磁碟 `dashboard/icon/unit/*.png` 皆存在的具名／固定 NPC。
2. 故事分類 (`main_count`, `event_count`, `other_count`) 嚴格鏡像 `dashboard/map.js` 的
   `resolveAppearanceStoryMeta` 與 `getExtraMembership` 邏輯，並保證三者加總等於 `appearance_count`。
3. 特殊獨立 NPC「秘書（秘書子）」額外輸出 `is_special: true` 與 `常服(6111)`、`泳裝(6112)` 雙版本資訊。
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

# 確保以 script 方式直接執行或作為模組匯入時皆能正確載入專案根目錄
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.scripts.generate_speaker_appearance import (
    BASE_DIR,
    DB_PATH,
    OUTPUT_PATH as APPEARANCE_PATH,
    RULES_PATH,
    has_japanese_kana,
)

AVATAR_ASSETS_PATH = BASE_DIR / "data" / "avatar_assets.json"
EXTRA_STORY_INDEX_PATH = BASE_DIR / "data" / "extra_story_index.json"
EXTRA_EVENTS_PATH = BASE_DIR / "data" / "extra_events.json"
NPC_CATALOG_PATH = BASE_DIR / "data" / "npc_catalog.json"
UNIT_ICON_DIR = BASE_DIR / "icon" / "unit"

# map.js 主線第 16 章幕間與第 17 章／第 3 部終幕兜底話數
PENDING_MAIN_FALLBACK_IDS: frozenset[int] = frozenset(
    {
        2216097,
        2216098,
        2216099,
        2217004,
        2217005,
        2217006,
        2217007,
        2217008,
        2217009,
        2218001,
        2218002,
        2218003,
    }
)

# 經審核確認之具名／固定專屬圖 NPC 與代表性 unit_id 映射
# 包含經審核過濾後的 npc_review_candidates 與額外確認之固定具名角色
CURATED_NPC_UNIT_IDS: dict[str, int] = {
    # 特殊獨立 NPC（雙立繪）
    "秘書": 6111,
    # 額外確認具專屬實圖之重要固定角色（含高登場數與固定稱號）
    "女性教員": 3211,
    "魔物的公主": 7011,
    "神燈精靈": 5313,
    "鬼魂教父": 14011,  # 強制使用專屬頭像 014011.png，避免誤用泛用 001411.png
    "惡代官": 11411,
    "聖誕老人": 3911,
    "山神大人": 12711,
    "黑之王": 13411,
    "長老": 107212,
    "嚮導老君": 107211,
    "哥布林女士": 19411,
    "輔佐": 8711,
    "老虎族族長": 8611,
    "鬼族族長": 7412,
    # 共用 18911 紫蛇系但劇情上各自獨立（梅杜莎個人角寵物蛇 vs 華音召喚大蛇）
    "梅杜希亞娜": 18912,  # 專屬張口頭像 018912.png（僅梅杜希亞娜使用）
    "大蛇": 18911,
    # 審核清單確認保留之具名 NPC
    "噗吉": 2111,
    "骷髏老爸": 2411,
    "卡里莎": 191611,
    "尾狗刀": 106211,
    "媞雅": 193211,
    "摩拉": 4211,
    "拉基拉基": 107331,
    "黎薩": 140412,
    "芙蕾雅": 193711,
    "反逆獸": 15311,
    "小樂": 9512,
    "真軌": 191011,
    "阿澤爾德": 191911,
    "贊恩": 191711,
    "彌勒": 192613,
    "米亞": 51611,
    "大吾": 190711,
    "和正": 6411,
    "小飯糰": 9611,
    "波波爺爺": 9212,
    "拉菲": 5511,
    "帕克": 2611,
    "阿爾莎特": 195611,
    "幻境龍后": 107411,
    "愛麗絲": 4611,
    "八斗神": 193611,
    "沃爾加諾": 193511,
    "米奈娃": 191112,
    "羅蘭": 194211,
    "瑪麗亞": 7112,
    "輝美": 16712,
    "拉格": 50211,
    "格魯尼": 194312,
    "豪紳": 191411,
    "昴": 2713,
    "杜蘭": 52612,
    "哈尼哈尼": 20111,
    "宙": 107231,
    "弗洛艾": 52412,
    "賭場王": 16011,
    "冬麥斯": 9712,
    "小小格里芬": 2211,
    "艾米": 8912,
    "喵特": 2312,
    "好朋友X": 13211,
    "梅莉莎": 20011,
    "樂園守護者": 17111,
    "好朋友號": 7211,
    "小棉花糖": 7611,
    "旭": 5011,
    "玩具王": 14911,
    "小繆": 8411,
    "貝斯": 8311,
    "奧洛克伯爵": 2516,
    "薔薇假面": 6211,
    "馬修": 5712,
    "半藏": 13311,
    "啾二": 15911,
    "大地": 5112,
    "富美惠": 18211,
    "庫西": 52211,
    "植物羊": 16612,
    "莫夫": 17511,
    "亞斯來": 17211,
    "雨吉": 11611,
    "休茲": 5912,
    "傑克": 10511,
    "冥": 53011,
    "啾三": 15912,
    "無敵好朋友號": 7311,
    "瑪莉絲黛菈": 53111,
    "TYPE-R": 192711,
    "島鯨": 10412,
    "布拉德": 9811,
    "幻影男爵": 12111,
    "怪奇怪靈": 192013,
    "未菈": 9011,
    "皮喵太": 4411,
    "維多": 5812,
    "艾迪": 6012,
    "花": 3411,
    "茉莉的母親": 8511,
    "音寵之精靈": 19211,
    "黑灰色的龍": 19512,
    "可可亞烏拉": 10911,
    "哀嘆之女神": 11111,
    "招財貓": 17312,
    "晴吉": 11711,
    "終炎巨神": 16111,
    "貝特魯吉烏斯": 2811,
    "龍次": 6312,
    "TYPE-P": 192911,
    "TYPE-Q": 192811,
    "似龍": 12311,
    "南希": 419,
    "安布拉": 1731,
    "巴西利斯克‧阿洛斯": 18011,
    "布羅肯": 52511,
    "弗萊迪": 711,
    "時間管理員": 14611,
    "森神": 5413,
    "澄花": 52711,
    "瑪莎": 1514,
    "瘋狂喬": 18711,
    "織女": 4811,
    "美衣子": 3011,
    "賈斯頓": 2513,
    "飯綱": 193914,
    "喬": 711,
    "威爾": 313,
    "席茲": 10111,
    "改造蓋登": 50512,
    "特務Q": 51011,
    "特務V": 51111,
    "管理員老婆婆": 9111,
    "索菲": 711,
    "荷姆荷姆": 19311,
    "路克": 711,
    "醜陋可愛": 11011,
    "高登": 2511,
    "鮫肌牙之丞": 13711,
    "小宇": 1112,
    "小律": 50912,
    "牛郎": 4711,
    "索爾龍": 20411,
    "羅伊德": 2511,
    "舔刀子氏": 816,
    "覺醒‧花心星": 13511,
    "路易斯": 1012,
    "靈界之王": 7711,
    "佐賀牛頭怪": 19611,
    "席茲爺爺": 511,
    "法莉達": 1214,
    "甜心": 1212,
    "白鯨": 18511,
    "蓋登": 50511,
    "薩依德": 1012,
    "達令": 312,
    "邪餅神鏡餅": 10811,
    "金幣怪": 191914,
    "鏡華的母親": 53211,
    "阿爾珈提": 20511,
    "七冠融合體": 19011,
    "佐藤": 6511,
    "傑克南瓜布丁": 10512,
    "加爾格": 10311,
    "啾": 15915,
    "啾太": 15913,
    "溫泉之神": 17011,
    "花心星": 13611,
    "阿爾杰什": 17711,
    "阿爾瑪": 10211,
    "雙冠龍雷克斯": 50411,
    "霧奇": 10711,
    "卡巴邦": 50111,
    "哈立德": 17811,
    "啾也": 15914,
    "奧拉姆": 19111,
    "岡薩雷茲": 1711,
    "愛德華‧迪德": 8211,
    "玩具王二世": 14913,
    "神荒尾": 18411,
    "艾爾格雅": 192711,
    "草莓": 6111,
    "蕾忒": 192811,
    "薰子": 231,
    "馬克": 1111,
}

# 明確排除項目保護網（泛型、複數、編號路人、純顏色、非人物系統裝置、重複別名等）
EXCLUDED_NPC_NAMES: frozenset[str] = frozenset(
    {
        "兩隻",
        "農場的動物",
        "招攬客人的學生",
        "擔任司儀的學生",
        "廚師",
        "巨人族青年",
        "狼男",
        "負責洗衣的女性",
        "身陷沼澤的殭屍",
        "金魚會成員",
        "下忍",
        "馴鹿",
        "無名士兵",
        "無頭騎士的隊長",
        "小貓",
        "流浪貓",
        "狗頭人老婆婆",
        "秘書一號",
        "紅的",
        "藍",
        "主廚",
        "雪菲‧小樂",
        "時間儀",
        "玩具好朋友",
        "巨大巴西利斯克",
        "幻影貓",
        "羅塞塔",
    }
)

# 經視覺頭像與劇本台詞雙重核對後的確認女角白名單
FEMALE_NPC_NAMES: frozenset[str] = frozenset(
    {
        "秘書",
        "女性教員",
        "魔物的公主",
        "神燈精靈",
        "哥布林女士",
        "愛麗絲",
        "TYPE-R",
        "TYPE-P",
        "TYPE-Q",
        "艾爾格雅",
        "蕾忒",
        "哀嘆之女神",
        "森神",
        "佐藤",
        "草莓",
        "法莉達",
        "甜心",
        "薰子",
        "美衣子",
        "南希",
        "瑪莎",
        "未菈",
        "輝美",
        "瑪麗亞",
        "富美惠",
        "梅莉莎",
        "艾米",
        "拉菲",
        "冥",
        "瑪莉絲黛菈",
        "花",
        "茉莉的母親",
        "鏡華的母親",
        "澄花",
        "織女",
        "媞雅",
        "黎薩",
        "芙蕾雅",
        "米亞",
        "阿爾莎特",
        "幻境龍后",
        "米奈娃",
        "管理員老婆婆",
    }
)

# 非人類／動物／魔物／機械／無性別靈體等，標記為 "other"；其餘預設為 "male"
OTHER_GENDER_NPC_NAMES: frozenset[str] = frozenset(
    {
        "噗吉",
        "小樂",
        "小飯糰",
        "小小格里芬",
        "喵特",
        "好朋友X",
        "好朋友號",
        "無敵好朋友號",
        "小棉花糖",
        "玩具王",
        "玩具王二世",
        "植物羊",
        "島鯨",
        "怪奇怪靈",
        "皮喵太",
        "音寵之精靈",
        "黑灰色的龍",
        "可可亞烏拉",
        "招財貓",
        "終炎巨神",
        "似龍",
        "安布拉",
        "巴西利斯克‧阿洛斯",
        "大蛇",
        "梅杜希亞娜",
        "醜陋可愛",
        "索爾龍",
        "佐賀牛頭怪",
        "白鯨",
        "邪餅神鏡餅",
        "金幣怪",
        "阿爾珈提",
        "七冠融合體",
        "傑克南瓜布丁",
        "加爾格",
        "阿爾杰什",
        "阿爾瑪",
        "雙冠龍雷克斯",
        "卡巴邦",
        "哈立德",
        "奧拉姆",
        "岡薩雷茲",
        "神荒尾",
        "荷姆荷姆",
        "庫西",
        "莫夫",
        "反逆獸",
        "哈尼哈尼",
        "雨吉",
        "晴吉",
        "魔物的公主",
    }
)

# 特殊獨立呈現 NPC 定義
SPECIAL_NPCS: dict[str, dict[str, Any]] = {
    "秘書": {
        "special_label": "秘書子",
        "extra_aliases": ["秘書子"],
        "variants": [
            {"unit_id": 6111, "label": "常服"},
            {"unit_id": 6112, "label": "泳裝"},
        ],
    }
}


def load_active_avatar_unit_ids(avatar_assets_path: Path = AVATAR_ASSETS_PATH) -> set[int]:
    """讀取 `avatar_assets.json` 中 status=='active' 且為 PNG 的 unit_id 集合。"""
    data = json.loads(avatar_assets_path.read_text(encoding="utf-8"))
    active_ids: set[int] = set()
    for asset in data.get("assets", []):
        if asset.get("status") == "active" and asset.get("format") == "png":
            active_ids.add(int(asset["unit_id"]))
    return active_ids


def build_story_scope_classifier(
    db_path: Path = DB_PATH,
    extra_index_path: Path = EXTRA_STORY_INDEX_PATH,
    extra_events_path: Path = EXTRA_EVENTS_PATH,
):
    """
    建立故事範圍分類函式 `classify_story_scope(story_id) -> 'main' | 'event' | 'other'`。

    嚴格鏡像 `dashboard/map.js` 的 `resolveAppearanceStoryMeta` 與 `getExtraMembership` 優先序：
    1. extra_story_index.json（含 anniversary_countdown 之 groupId = story_id // 1000）→ other
    2. event_story_detail / extra_events.json / 5000000 <= sid < 6000000 → event
    3. story_detail 之 2000000 <= sid < 3000000 / map.js 兜底話數 / 2xxxxxx 主線分支 → main
    4. 其餘（個人、公會、其他特殊劇情）→ other
    """
    extra_data = json.loads(extra_index_path.read_text(encoding="utf-8"))
    explicit_extra_ids: set[int] = set()
    anniversary_group_ids: set[int] = set()

    for section_key in ("official_categories", "legacy_categories", "special_categories"):
        for category in extra_data.get(section_key, []):
            cat_id = category.get("id")
            for story_item in category.get("stories", []):
                sid = int(story_item["id"])
                explicit_extra_ids.add(sid)
                if cat_id == "anniversary_countdown":
                    anniversary_group_ids.add(sid // 1000)

    extra_event_ids: set[int] = set()
    if extra_events_path.exists():
        extra_events = json.loads(extra_events_path.read_text(encoding="utf-8"))
        for story_item in extra_events.get("stories", []):
            if "id" in story_item:
                extra_event_ids.add(int(story_item["id"]))

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        event_detail_ids = {
            int(row[0])
            for row in cur.execute("SELECT DISTINCT CAST(story_id AS INTEGER) FROM event_story_detail")
        }
        story_group_map = {
            int(row[0]): int(row[1])
            for row in cur.execute(
                "SELECT CAST(story_id AS INTEGER), CAST(story_group_id AS INTEGER) FROM story_detail"
            )
        }
        main_detail_ids = {
            int(row[0])
            for row in cur.execute(
                "SELECT DISTINCT CAST(story_id AS INTEGER) FROM story_detail "
                "WHERE CAST(story_id AS INTEGER) >= 2000000 AND CAST(story_id AS INTEGER) < 3000000"
            )
        }
    finally:
        conn.close()

    def classify_story_scope(story_id: int) -> str:
        sid = int(story_id)
        group_id = story_group_map.get(sid, sid // 1000)

        if sid in explicit_extra_ids or group_id in anniversary_group_ids:
            return "other"
        if sid in event_detail_ids or sid in extra_event_ids or (5000000 <= sid < 6000000):
            return "event"
        if sid in main_detail_ids or sid in PENDING_MAIN_FALLBACK_IDS or (2000000 <= sid < 3000000):
            return "main"
        return "other"

    return classify_story_scope


def collect_npc_aliases_from_rules(rules_data: dict[str, Any]) -> dict[str, list[str]]:
    """從 `speaker_identity_rules.json` 的 `npc_rules` 彙整每個 canonical NPC 的次要別名。"""
    alias_map: dict[str, list[str]] = {}
    for alias, entries in rules_data.get("npc_rules", {}).items():
        if has_japanese_kana(alias):
            continue
        for entry in entries:
            canon = entry.get("npc_group")
            if not canon or alias == canon:
                continue
            alias_map.setdefault(canon, [])
            if alias not in alias_map[canon]:
                alias_map[canon].append(alias)
    for canon in alias_map:
        alias_map[canon].sort()
    return alias_map


def validate_unit_png(unit_id: int, active_unit_ids: set[int], unit_icon_dir: Path = UNIT_ICON_DIR) -> None:
    """確保 unit_id 同時存在於 avatar_assets.json active PNG 清單與磁碟檔案。"""
    if unit_id not in active_unit_ids:
        raise ValueError(f"unit_id {unit_id} 不在 avatar_assets.json 的 active PNG 清單中")
    icon_path = unit_icon_dir / f"{unit_id:06d}.png"
    if not icon_path.is_file():
        raise FileNotFoundError(f"磁碟找不到頭像檔案: {icon_path}")


def resolve_npc_gender(name: str) -> str:
    """依核對後白名單與非人分類決定 NPC 性別欄位。"""
    if name in FEMALE_NPC_NAMES:
        return "female"
    if name in OTHER_GENDER_NPC_NAMES:
        return "other"
    return "male"


def build_npc_catalog(
    appearance_path: Path = APPEARANCE_PATH,
    rules_path: Path = RULES_PATH,
    avatar_assets_path: Path = AVATAR_ASSETS_PATH,
    db_path: Path = DB_PATH,
    extra_index_path: Path = EXTRA_STORY_INDEX_PATH,
    extra_events_path: Path = EXTRA_EVENTS_PATH,
    unit_icon_dir: Path = UNIT_ICON_DIR,
) -> dict[str, Any]:
    """建置並回傳符合鎖定 Schema 的 NPC 圖鑑字典結構。"""
    appearance = json.loads(appearance_path.read_text(encoding="utf-8"))
    rules_data = json.loads(rules_path.read_text(encoding="utf-8"))
    active_unit_ids = load_active_avatar_unit_ids(avatar_assets_path)
    classify_story_scope = build_story_scope_classifier(
        db_path=db_path,
        extra_index_path=extra_index_path,
        extra_events_path=extra_events_path,
    )

    entities = set(rules_data.get("entities", {}).keys())
    entity_speaker_rules = set(rules_data.get("speaker_rules", {}).keys())
    npc_rules = rules_data.get("npc_rules", {})
    npc_aliases_by_canon = collect_npc_aliases_from_rules(rules_data)

    npcs: list[dict[str, Any]] = []
    for name, unit_id in CURATED_NPC_UNIT_IDS.items():
        if name in EXCLUDED_NPC_NAMES:
            raise ValueError(f"收錄名單衝突：'{name}' 同時位於排除保護名單")
        if has_japanese_kana(name):
            raise ValueError(f"NPC 名稱不可含日文假名: {name}")
        if name in entities or name in entity_speaker_rules:
            raise ValueError(f"NPC 名稱衝突 entity / speaker_rules: {name}")
        if name in npc_rules and all(e.get("npc_group") != name for e in npc_rules[name]):
            raise ValueError(f"NPC 名稱屬於次要別名，不可獨立收錄: {name}")

        story_ids = appearance.get(name)
        if not story_ids:
            raise ValueError(f"speaker_appearance.json 找不到登場紀錄: {name}")

        validate_unit_png(unit_id, active_unit_ids, unit_icon_dir)

        main_count = 0
        event_count = 0
        other_count = 0
        for sid in story_ids:
            scope = classify_story_scope(int(sid))
            if scope == "main":
                main_count += 1
            elif scope == "event":
                event_count += 1
            else:
                other_count += 1

        appearance_count = len(story_ids)
        if main_count + event_count + other_count != appearance_count:
            raise AssertionError(f"{name} 分類話數加總異常")

        story_scopes = [
            scope_name
            for scope_name, count in (("main", main_count), ("event", event_count), ("other", other_count))
            if count > 0
        ]

        aliases = list(npc_aliases_by_canon.get(name, []))
        special_cfg = SPECIAL_NPCS.get(name)
        is_special = special_cfg is not None
        special_label: str | None = None
        variants: list[dict[str, Any]] = []

        if special_cfg:
            special_label = special_cfg["special_label"]
            for extra_alias in special_cfg.get("extra_aliases", []):
                if extra_alias not in aliases:
                    aliases.append(extra_alias)
            for variant in special_cfg.get("variants", []):
                v_uid = int(variant["unit_id"])
                validate_unit_png(v_uid, active_unit_ids, unit_icon_dir)
                variants.append({"unit_id": v_uid, "label": variant["label"]})

        npcs.append(
            {
                "name": name,
                "unit_id": unit_id,
                "gender": resolve_npc_gender(name),
                "appearance_count": appearance_count,
                "main_count": main_count,
                "event_count": event_count,
                "other_count": other_count,
                "story_scopes": story_scopes,
                "is_special": is_special,
                "special_label": special_label,
                "aliases": aliases,
                "variants": variants,
            }
        )

    npcs.sort(key=lambda item: (-item["appearance_count"], item["name"]))

    metadata = {
        "total_npcs": len(npcs),
        "female_count": sum(1 for item in npcs if item["gender"] == "female"),
        "main_count": sum(1 for item in npcs if item["main_count"] > 0),
        "event_count": sum(1 for item in npcs if item["event_count"] > 0),
        "special_count": sum(1 for item in npcs if item["is_special"]),
    }

    return {
        "version": 1,
        "metadata": metadata,
        "npcs": npcs,
    }


def main() -> None:
    catalog = build_npc_catalog()
    NPC_CATALOG_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    meta = catalog["metadata"]
    print(
        f"已產生 {NPC_CATALOG_PATH}："
        f"total_npcs={meta['total_npcs']}, "
        f"female_count={meta['female_count']}, "
        f"main_count={meta['main_count']}, "
        f"event_count={meta['event_count']}, "
        f"special_count={meta['special_count']}"
    )


if __name__ == "__main__":
    main()
