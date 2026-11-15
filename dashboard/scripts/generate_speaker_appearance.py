import json
import os
import re
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORY_DIR = BASE_DIR / "story"
OUTPUT_PATH = STORY_DIR / "speaker_appearance.json"
DB_PATH = BASE_DIR / "redive_tw.db"
RULES_PATH = BASE_DIR / "data" / "speaker_identity_rules.json"
VERSION_HISTORY_PATH = BASE_DIR / "versions" / "version_history.json"

# 複合說話者分隔符：頓號、全半形＆、非「日和/和正/和服」的「和」、「與」
COMPOUND_SPLIT_RE = re.compile(r"[、＆&]|(?<!日)和(?!正|服)|與")

# 日文平假名／片假名偵測（刻意排除 U+30FB 全形中點「・」，避免誤傷 伊莉亞・奧恩斯坦 等繁中譯名）
KANA_RE = re.compile(r"[\u3040-\u309f\u30a1-\u30fa\u30fc-\u30ff]")

# 非實體泛稱、群眾、環境音與無效佔位符
INVALID_NAMES = {
    "2人", "3人", "3個人", "4人", "5人", "{0}", "一夥", "一行人", "三人", "主人",
    "人們", "光之文字", "全員", "兩人", "兩個人", "動物群", "告示", "大人", "大家",
    "大家的聲音", "女", "女子", "女性", "孩子們", "小孩", "小孩們", "小孩子",
    "少女", "少年", "廢物", "指示", "日", "歌聲", "殭屍群", "母親", "民眾",
    "父親", "牛", "狗", "狼", "男", "男子", "男性", "笑聲", "群眾", "老人",
    "聲", "聲音", "聽眾", "聽眾們", "蟲群", "觀眾", "觀眾們", "貓", "邀請函",
    "青年", "馬", "魔物", "魔物們", "魔物群", "魚", "鳥群", "龍",
    "２人", "３人", "４人", "５人", "旁白", "【系統】", "？？？",
}

INVALID_PATTERNS = [
    r"^\d+$",
    r"^[男女][１２３４５12]?$",
    r"^[男女]性[１２３４５12]?$",
    r"^(壞人|流氓|小混混|暴徒|無賴|不良|地痞|手下|士兵|騎士|隊長|部下|傭兵|護衛|盜賊|刺客)[１２３４５12]?$",
    r"^(觀眾|觀客|聽眾|路人|顧客|客人|鎮民|市民|村民|居民|島民|參加者|新兵|團員|職員|社員|工作人員|粉絲)[１２３４５12]?[０0]?$",
    r"^(小孩|小孩子|少年|少女|男學生|女學生|學生|男孩|女孩|男孩子|女孩子)[１２３４５12]?$",
    r"^(鎮民|村民|居民|市民|民眾|群眾|觀眾|客人|顧客|粉絲|團員|職員|社員|手下|傭兵|士兵|騎士|流氓|暴徒|不良|無賴|小混混|壞人|地痞|盜賊|新兵|參加者|觀客|路人|聽眾)們?$",
]
INVALID_REGEXES = [re.compile(pat) for pat in INVALID_PATTERNS]

# 明確禁止納入歸戶規則的名稱（包含 艾爾 與 NPC 大神 等）
EXCLUDED_GIVEN_NAMES = {"艾爾", "大神"}

# 經 9,420 話全語料驗證之 31 位純現實名（允許 unit_id=null 歸戶至本尊）
CONFIRMED_PURE_REAL_NAMES = {
    "晶": "拉比林斯達",
    "真那": "霸瞳皇帝",
    "紫布菜": "雪菲",
    "克蕾雅": "克蕾琪塔",
    "真璃": "露易絲瑪莉",
    "由仁": "優妮",
    "佳凜": "花凜",
    "寢亞": "涅婭",
    "璃亞": "可璃亞",
    "花子": "克蘿依",
    "蘭": "蘭法",
    "愛莉": "厄莉絲",
    "禰羅": "涅妃‧涅羅",
    "飛白": "格蕾斯",
    "千惠": "克蘿茜",
    "牡丹": "安涅默涅",
    "樞": "庫露露",
    "鳳子": "鳳凰",
    "伽音": "華音",
    "愛來": "埃拉",
    "志名都": "志那都",
    "幸乃": "雪野",
    "夜雲": "阿剌克涅",
    "斜": "拿娜",
    "璐璐": "璐璐伊",
    "希留耶": "凱留",
    "可蘿": "可可蘿",
    "魅空": "美空",
    "菫": "薇歐莉特",
    "撫瑠無": "烏爾姆",
    "燐人": "琳德",
}

# 明確的換裝形態、代號、稱號與有效歷史別名白名單（全部綁定本尊 allowed_base_ids）
CURATED_ENTITY_ALIASES = {
    # 換裝與特別形態
    "黑暗伊緒": "伊緒",
    "黑暗空花": "空花",
    "黑暗靜流": "靜流",
    "Misty★霞": "霞",
    "Purely★栞": "栞",
    "Lovely★莫妮卡": "莫妮卡",
    "Shiny★智": "智",
    "凱留（變裝）": "凱留",
    "可可蘿（變裝）": "可可蘿",
    "貪吃佩可（變裝）": "貪吃佩可",
    "雪菲（厄莉絲）": "雪菲",
    "格蕾斯（上）": "格蕾斯",
    "格蕾斯（下）": "格蕾斯",
    "格蕾斯（上下）": "格蕾斯",
    # 代號與稱號
    "諾維姆": "矛依未",
    "修特帕魯": "杏奈",
    "阿剌克涅女士": "阿剌克涅",
    "誓約女君": "克莉絲提娜",
    "變貌大妃": "似似花",
    "変貌大妃": "似似花",
    "迷宮女王": "拉比林斯達",
    "拉比林θ": "拉比林斯達",
    "鮮紅的立方體": "拉比林斯達",
    "拜拉潔耶爾": "萊拉耶爾",
    "耶兒": "萊拉耶爾",
    "碧奇": "碧卡拉",
    "小霧": "霞",
    # 經語料驗證的官方真名書寫變體與歷史別名
    "尤絲蒂亞娜·馮·阿斯特賴亞": "貪吃佩可",
    "大食客": "貪吃佩可",
    "飢餓的公主": "貪吃佩可",
    "佩可": "貪吃佩可",
    "導引者": "可可蘿",
    "引導者": "可可蘿",
    "導引少女": "可可蘿",
    "kokoro": "可可蘿",
    "貓耳魔法少女": "凱留",
    "日和莉": "日和",
    "春咲日和莉": "日和",
    "士條 怜": "怜",
    "士條怜": "怜",
    "士条 怜": "怜",
    "士条怜": "怜",
    "綾瀨 優花梨": "優花梨",
    "綾瀨優花梨": "優花梨",
    "風間 千愛爾": "琪愛兒",
    "風間千愛爾": "琪愛兒",
    "阿斯特賴亞・雪菲": "雪菲",
    "霸瞳天星": "霸瞳皇帝",
    "霸瞳天星的聲音": "霸瞳皇帝",
    "暮光流星的成員": "流夏",
    "涅雅": "涅婭",
    "可璃": "可璃亞",
    "可璃的聲音": "可璃亞",
    # 第二大點：可操作角特殊稱呼（狀態/位置/過去修飾與特定無衝突稱呼）
    "小孩彩羽": "彩羽",
    "成人苑": "苑",
    "成人苑？": "苑",
    "菲歐？": "愛梅斯",
    "治療中的貪吃佩可": "貪吃佩可",
    "觀眾席的可可蘿": "可可蘿",
    "觀眾席的凱留": "凱留",
    "觀眾席的莉莉": "莉莉",
    "觀眾席的可璃亞": "可璃亞",
    "觀眾席的普蕾西亞": "普蕾西亞",
    "觀眾席的鳳凰": "鳳凰",
    "通訊魔法的帆稀": "帆稀",
    "過去祈梨": "祈梨",
    "過去嘉夜": "嘉夜",
    "過去的矛依未": "矛依未",
    "過去的阿剌克涅": "阿剌克涅",
    "過去的可璃亞": "可璃亞",
    "戀愛中的流夏": "流夏",
    "銅鑼台的拿娜": "拿娜",
    "結婚派深月": "深月",
    "研究派深月": "深月",
}

# 必須嚴格依 unit_id 檢核且禁止 unit_id=null 歸戶的特殊分流/限定稱呼
STRICT_UNIT_ID_ALIASES = [
    ("尤絲蒂亞娜", "霸瞳皇帝", [1069], False),
    ("尤絲蒂亞娜", "貪吃佩可", [1058, 1075, 1118, 1210, 1279, 1383, 1804], False),
    ("１號", "櫻", [1361], False),
    ("宮子（剎鬼）", "剎鬼", [1359], False),
    ("黑暗姐姐", "靜流", [1200], False),
    ("可麗餅姐姐", "靜流", [1200], False),
    ("普通姐姐", "靜流", [1200], False),
    ("性感姐姐", "靜流", [1200], False),
    ("巧克力姐姐", "靜流", [1200], False),
    # 第二大點：羅塞塔通話中的優妮 & 個人劇情匿名代稱（嚴格 allow_null_unit_id=False）
    ("羅塞塔通話中的優妮", "優妮", [1110, 1164, 1293], False),
    ("陌生的女性", "埃拉", [1355], False),
    ("陌生的女性", "志那都", [1356], False),
    ("和服的女性", "雪野", [1358], False),
    ("陰沉的少女", "碧卡拉", [1256], False),
    ("銀髮少女", "梅杜莎", [1336], False),
    ("活潑的小女孩", "彩羽", [1324], False),
    ("黑髮少女", "莉莉", [1258], False),
    ("金髮少女", "可璃亞", [1260], False),
    ("藍髮少女", "普蕾西亞", [1261], False),
    ("神秘女性", "花凜", [1185], False),
    ("Ｈ先生", "初音", [1134], False),
    ("反派千金", "鏡華", [1390], False),
    ("蠍獅少女", "華音", [1349], False),
    ("少女", "雪菲", [1064], False),
    ("姊姊", "似似花", [1070], False),
    ("姊姊", "埃拉", [1355], False),
]

# 1A 部分：NPC 合併群組（僅供合併共用登場劇情目錄，無官方設定集與真名欄）
NPC_MERGE_GROUPS = {
    "尾狗刀": {
        "base_ids": [1062],
        "names": ["尾狗刀", "詠斗", "過去的詠斗", "尾狗刀？", "尾狗刀？？", "尾狗刀？？？"],
    },
    "拉基拉基": {
        "base_ids": [1073, 9999],
        "names": ["拉基拉基", "拉基尼卡東", "跳躍王"],
    },
    "贊恩": {
        "base_ids": [1917],
        "names": ["贊恩", "善", "贊恩？", "回憶的贊恩"],
    },
    "宙": {
        "base_ids": [1072],  # 嚴格排除同 base=1072 的 長老 與 嚮導老君
        "names": ["宙", "佐拉"],
    },
    "芙蕾雅": {
        "base_ids": [1937],
        "names": ["芙蕾雅", "黎‧普賽爾", "菲絲雷斯", "通訊魔法的芙蕾雅"],
    },
    "八斗神": {
        "base_ids": [1936],  # 2212004 的 剎鬼‧八斗神 係兩人台詞，不納入單人別名
        "names": ["八斗神", "八斗神局長"],
    },
    "米奈娃": {
        "base_ids": [1911],
        "names": ["米奈娃", "米奈娃β", "過去的米奈娃"],
    },
    # 1B 部分：純中文 NPC 群組（嚴格排除日文假名與撞名泛稱）
    "賭場王": {
        "base_ids": [160],
        "names": ["賭場王", "吉諾", "前賭場王"],
    },
    "豪紳": {
        "base_ids": [1914],
        "names": ["豪紳", "鬼魂豪紳", "貴族議長"],
    },
    "阿澤爾德": {
        "base_ids": [1919],
        "names": ["阿澤爾德", "阿澤爾德的幻影", "阿澤爾德？"],
    },
    "彌勒": {
        "base_ids": [1926],
        "names": ["彌勒", "彌勒的聲音"],
    },
    "格魯尼": {
        "base_ids": [1943],
        "names": ["格魯尼", "分身格魯尼"],
    },
    "冥": {
        "base_ids": [530],
        "names": ["冥", ("神秘女性", False)],  # 神秘女性 1185 為花凜，530 才歸冥
    },
    "瑪莉絲黛菈": {
        "base_ids": [531],
        "names": ["瑪莉絲黛菈", "露易絲瑪莉的祖母"],
    },
    "米亞": {
        "base_ids": [516],
        "names": ["米亞", "梅杜莎‧米亞"],
    },
    "骷髏老爸": {
        "base_ids": [24, 1031],
        "names": ["骷髏老爸", "骷髏老爸？", "骷髏頭"],
    },
    "昴": {
        "base_ids": [27],
        "names": ["昴", "諾斯德拉達姆斯？"],
    },
    "拉格": {
        "base_ids": [502],  # 嚴禁納入共用 50211 的 帆稀？
        "names": ["拉格", "拉格？"],
    },
    "雨吉": {
        "base_ids": [116, 118],
        "names": ["雨吉", "雨神大人"],
    },
    "似龍": {
        "base_ids": [123],
        "names": ["似龍", "似龍生物"],
    },
    "玩具王": {
        "base_ids": [149],  # 玩具王二世 維持獨立
        "names": ["玩具王", "機械玩具王"],
    },
    "好朋友X": {
        "base_ids": [132],
        "names": ["好朋友X", "好朋友Ｘ？"],
    },
    "鮫肌牙之丞": {
        "base_ids": [137],
        "names": ["鮫肌牙之丞", "鯊魚魔物"],
    },
    "瘋狂喬": {
        "base_ids": [187],
        "names": ["瘋狂喬", "超級‧衝刺喬"],
    },
    "音寵之精靈": {
        "base_ids": [192],
        "names": ["音寵之精靈", "扭曲的音寵之精靈"],
    },
    "莫夫": {
        "base_ids": [175],
        "names": ["莫夫", "館主"],
    },
    "小律": {
        "base_ids": [509],
        "names": ["小律", ("小嬰兒", False)],
    },
    "改造蓋登": {
        "base_ids": [505],  # 經核對 5203002/5203005/1346003，蓋登(50511)為已擊敗之獨立個體，改造/宇宙蓋登(50512)為進化形態群體
        "names": ["改造蓋登", "宇宙蓋登"],
    },
}

# A1 擴充表：本尊專屬額外 base_id 放行表（僅限已登錄之對應角色名稱使用，嚴禁反向無條件開放給未登錄 NPC 名稱）
EXTRA_CHARACTER_BASE_IDS = {
    # 高頻早期 NPC / 角色專屬特別編號（12 組）
    "愛梅斯": [1900],
    "美空": [1920],
    "花凜": [1908],
    "涅比亞": [1909],
    "班比": [1402],
    "布武機": [1401],
    "克蘿茜": [1406],
    "烏爾姆": [1405],
    "涅婭": [1916],  # 1916 亦用於卡里莎/少年/史萊姆們，僅允許涅婭/寢亞/涅雅通過
    "吉塔": [1701],
    "志那都": [5000],
    "菲歐": [527],  # 527 亦用於澄花/？？？，僅允許菲歐通過
    # 雙人卡故事單人發言子編號（13 組；9500075 中彩羽係角色扮演成人苑，故 1327 僅歸苑）
    "初音": [1183],
    "栞": [1184],
    "美美": [1204],
    "禊": [1205],
    "鏡華": [1206],
    "秋乃": [1217],
    "咲戀": [1218],
    "安": [1243],
    "古蕾婭": [1244],
    "靜流": [1281],
    "璃乃": [1282],
    "彩羽": [1326],
    "苑": [1327],
}


def _read_truth_version(version_history_path=VERSION_HISTORY_PATH):
    """從 version_history.json 讀取目前資料集的 TruthVersion。"""
    path = Path(version_history_path)
    if not path.exists():
        return "00620004"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and data.get("truth_version"):
        return str(data["truth_version"])
    return "00620004"


def _strip_parens_and_normalize(name):
    """移除括號後綴並將半形 '&' 統一為全形 '＆'。"""
    return name.split("（")[0].split("(")[0].strip().replace("&", "＆")


def _iter_real_name_variants(real_name):
    """產生官方真名全稱的常見分隔符與空白變體。"""
    variants = set()
    seeds = {
        real_name,
        real_name.replace("&", "＆"),
        real_name.replace("＆", "&"),
    }
    for seed in seeds:
        variants.add(seed)
        variants.add(seed.replace(" ", ""))
        for dot in ("‧", "・", "·"):
            if "‧" in seed or "・" in seed or "·" in seed:
                replaced = seed.replace("‧", dot).replace("・", dot).replace("·", dot)
                variants.add(replaced)
                variants.add(replaced.replace(" ", ""))
    return sorted(variants)


def build_speaker_identity_rules(db_path=DB_PATH, truth_version=None):
    """從 redive_tw.db 與白名單建置前後端共用的角色歸戶規則（speaker_identity_rules.json）。"""
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"找不到資料庫檔案: {db_file}")

    resolved_truth_version = str(truth_version or _read_truth_version())

    conn = sqlite3.connect(str(db_file))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT CAST(up.unit_id AS INTEGER) AS uid,
                   ud.unit_name,
                   aub.real_name
            FROM unit_profile up
            JOIN unit_data ud
              ON CAST(up.unit_id AS INTEGER) = CAST(ud.unit_id AS INTEGER)
            LEFT JOIN actual_unit_background aub
              ON (CAST(up.unit_id AS INTEGER) / 100) * 100 = (CAST(aub.unit_id AS INTEGER) / 100) * 100
            WHERE CAST(up.unit_id AS INTEGER) > 100000
              AND CAST(up.unit_id AS INTEGER) < 200000
            ORDER BY uid ASC
            """
        )
        profile_rows = cur.fetchall()

        cur.execute(
            """
            SELECT CAST(unit_id AS INTEGER) AS uid, unit_name
            FROM unit_data
            WHERE CAST(unit_id AS INTEGER) > 100000
              AND CAST(unit_id AS INTEGER) < 200000
            ORDER BY uid ASC
            """
        )
        unit_data_rows = cur.fetchall()
    finally:
        conn.close()

    entities_raw = {}
    real_name_to_canon = {}
    for uid, game_name, real_name in profile_rows:
        base_id = uid // 100
        canon = _strip_parens_and_normalize(game_name)
        clean_real = real_name.strip() if real_name else None

        if clean_real and clean_real in real_name_to_canon:
            canon = real_name_to_canon[clean_real]
        elif clean_real:
            real_name_to_canon[clean_real] = canon

        entry = entities_raw.setdefault(
            canon,
            {
                "canonical_game_name": canon,
                "real_name": clean_real,
                "base_ids": set(),
                "profile_unit_ids": [],
            },
        )
        if entry["real_name"] is None and clean_real is not None:
            entry["real_name"] = clean_real
        entry["base_ids"].add(base_id)
        entry["profile_unit_ids"].append(uid)

    entities = {}
    base_id_to_entity = {}
    for canon in sorted(entities_raw):
        item = entities_raw[canon]
        sorted_bases = sorted(item["base_ids"])
        entities[canon] = {
            "canonical_game_name": canon,
            "real_name": item["real_name"],
            "base_ids": sorted_bases,
            "profile_unit_id": min(item["profile_unit_ids"]),
        }
        for b_id in sorted_bases:
            base_id_to_entity[b_id] = canon

    speaker_rules = {}

    def add_rule(speaker_name, entity_name, allowed_base_ids=None, allow_null_unit_id=True):
        if entity_name not in entities:
            raise KeyError(f"歸戶目標實體不存在於 unit_profile: {entity_name!r}")
        if allowed_base_ids is not None:
            target_bases = sorted(allowed_base_ids)
        else:
            target_bases = sorted(
                set(entities[entity_name]["base_ids"])
                | set(EXTRA_CHARACTER_BASE_IDS.get(entity_name, ()))
            )
        rule_obj = {
            "entity": entity_name,
            "allowed_base_ids": target_bases,
            "allow_null_unit_id": bool(allow_null_unit_id),
        }
        existing_list = speaker_rules.setdefault(speaker_name, [])
        if rule_obj not in existing_list:
            existing_list.append(rule_obj)

    # 1. 基礎遊戲名、對應的「〇〇的聲音」與全真名變體
    for canon, ent in entities.items():
        add_rule(canon, canon, allow_null_unit_id=True)
        add_rule(f"{canon}的聲音", canon, allow_null_unit_id=True)
        if "＆" in canon:
            half_name = canon.replace("＆", "&")
            add_rule(half_name, canon, allow_null_unit_id=True)
            add_rule(f"{half_name}的聲音", canon, allow_null_unit_id=True)

        if ent["real_name"]:
            for variant in _iter_real_name_variants(ent["real_name"]):
                add_rule(variant, canon, allow_null_unit_id=True)

    # 2. unit_profile 涵蓋的 unit_data 換裝形態名稱（含半全形）
    for uid, game_name in unit_data_rows:
        base_id = uid // 100
        canon = base_id_to_entity.get(base_id)
        if canon:
            clean_name = game_name.strip()
            add_rule(clean_name, canon, allow_null_unit_id=True)
            if "&" in clean_name:
                add_rule(clean_name.replace("&", "＆"), canon, allow_null_unit_id=True)

    # 3. 由「姓＋空白＋名」自動拆出的純「名」（僅限無撞名且非 EXCLUDED_GIVEN_NAMES）
    auto_given_candidates = {}
    for canon, ent in entities.items():
        rname = ent["real_name"]
        if not rname or " " not in rname or any(sep in rname for sep in ("＆", "・", "‧")):
            continue
        parts = rname.split(" ")
        if len(parts) != 2:
            continue
        given_name = parts[1].strip()
        if not given_name or given_name in EXCLUDED_GIVEN_NAMES:
            continue
        auto_given_candidates.setdefault(given_name, set()).add(canon)

    for given_name, owners in sorted(auto_given_candidates.items()):
        if len(owners) != 1:
            continue
        owner = next(iter(owners))
        if given_name in entities and given_name != owner:
            continue
        add_rule(given_name, owner, allow_null_unit_id=True)

    # 4. 確認白名單內之 31 位純現實名（含單字/無分隔/歐式分隔名，如 菫/克蕾雅/真璃/璃亞/璐璐/撫瑠無/燐人）
    for real_short, owner in sorted(CONFIRMED_PURE_REAL_NAMES.items()):
        if real_short in EXCLUDED_GIVEN_NAMES:
            continue
        add_rule(real_short, owner, allow_null_unit_id=True)

    # 5. 換裝形態、代號、稱號與有效別名白名單
    for alias, owner in sorted(CURATED_ENTITY_ALIASES.items()):
        add_rule(alias, owner, allow_null_unit_id=True)

    # 6. 嚴格 unit_id 分流規則（尤絲蒂亞娜、１號、宮子（剎鬼）、黑暗姐姐等）
    for speaker_name, owner, allowed_bases, allow_null in STRICT_UNIT_ID_ALIASES:
        add_rule(speaker_name, owner, allowed_base_ids=allowed_bases, allow_null_unit_id=allow_null)

    # 7. NPC 合併群組（獨立區塊，不混入 entities / speaker_rules；支援個別設定 allow_null_unit_id）
    npc_groups = {}
    npc_rules = {}
    for group_name in sorted(NPC_MERGE_GROUPS):
        spec = NPC_MERGE_GROUPS[group_name]
        allowed_bases = sorted(spec["base_ids"])
        npc_groups[group_name] = {
            "canonical_npc_name": group_name,
            "base_ids": allowed_bases,
        }
        for item in spec["names"]:
            if isinstance(item, tuple):
                alias, allow_null = item
            else:
                alias, allow_null = item, True
            if KANA_RE.search(alias):
                continue
            rule_entry = {
                "npc_group": group_name,
                "allowed_base_ids": allowed_bases,
                "allow_null_unit_id": bool(allow_null),
            }
            existing_npc_list = npc_rules.setdefault(alias, [])
            if rule_entry not in existing_npc_list:
                existing_npc_list.append(rule_entry)

    ordered_rules = {k: speaker_rules[k] for k in sorted(speaker_rules) if not KANA_RE.search(k)}
    ordered_npc_rules = {k: npc_rules[k] for k in sorted(npc_rules)}
    return {
        "version": "1.0",
        "generated_from_truth_version": resolved_truth_version,
        "entities": entities,
        "speaker_rules": ordered_rules,
        "npc_groups": npc_groups,
        "npc_rules": ordered_npc_rules,
    }


def write_speaker_identity_rules(rules_path=RULES_PATH, db_path=DB_PATH, truth_version=None):
    """建置並寫出 speaker_identity_rules.json。"""
    rules = build_speaker_identity_rules(db_path=db_path, truth_version=truth_version)
    target = Path(rules_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)
    return rules


def has_japanese_kana(name):
    """檢查字串是否包含日文平假名或片假名（排除全形中點 U+30FB）。"""
    return bool(name and KANA_RE.search(name))


def is_invalid_name(name):
    """判斷是否為不應收錄的泛稱、無效佔位符、日文假名或 NPC 群組名。"""
    if not name or name in INVALID_NAMES or has_japanese_kana(name):
        return True
    return any(rx.match(name) for rx in INVALID_REGEXES)


def _normalize_unit_id(unit_id):
    """將 dialogue.unit_id 安全正規化為 int（無效或空值則回傳 None）。"""
    if isinstance(unit_id, bool):
        return None
    if isinstance(unit_id, int):
        return unit_id
    if isinstance(unit_id, str) and unit_id.strip().isdigit():
        return int(unit_id.strip())
    return None


def _match_rule_list(rule_list, unit_id, target_key):
    """共用的 unit_id 白名單規則比對器（適用於 speaker_rules 與 npc_rules）。"""
    uid = _normalize_unit_id(unit_id)
    base_id = (uid // 100) if uid is not None else None
    for rule in rule_list:
        if base_id is not None:
            if base_id in rule["allowed_base_ids"]:
                return rule[target_key]
        elif rule.get("allow_null_unit_id"):
            return rule[target_key]
    return None


def resolve_speaker_identity(part, unit_id, rules):
    """
    依 speaker_identity_rules.speaker_rules 嚴格解析可操作角色實體：
    - 若名稱含日文假名：回傳 None（絕不歸戶至中文實體）。
    - 若名稱在 speaker_rules 中：必須符合 unit_id // 100 in allowed_base_ids（或 unit_id is None 且 allow_null_unit_id），否則回傳 None。
    - 若名稱不在 speaker_rules 中：回傳原名稱。
    """
    if has_japanese_kana(part):
        return None
    speaker_rules = rules.get("speaker_rules", {})
    rule_list = speaker_rules.get(part)
    if rule_list is None:
        return part
    return _match_rule_list(rule_list, unit_id, "entity")


def resolve_npc_group(part, unit_id, rules):
    """依 speaker_identity_rules.npc_rules 解析 NPC 合併群組鍵；未命中則回傳 None。"""
    if has_japanese_kana(part):
        return None
    npc_rules = rules.get("npc_rules", {})
    rule_list = npc_rules.get(part)
    if rule_list is None:
        return None
    return _match_rule_list(rule_list, unit_id, "npc_group")


def resolve_appearance_target(part, unit_id, rules):
    """
    統一解析登場索引（speaker_appearance.json）的目標鍵名：
    1) 含日文假名直接回傳 None（不收錄也不連結）；
    2) 優先比對 speaker_rules（可操作實體）；未命中時繼續比對 npc_rules（支援重名如 神秘女性 1185->花凜 / 530->冥）；
    3) 若名稱有出現在任一規則表卻都未通過 unit_id 檢核，回傳 None 阻止泛稱誤併（如 少女 211 / 神秘女性 6511）；
    4) 通過 is_invalid_name 過濾的其餘名稱維持獨立鍵名。
    """
    if not part or has_japanese_kana(part):
        return None
    has_rule = False
    if part in rules.get("speaker_rules", {}):
        has_rule = True
        resolved_entity = resolve_speaker_identity(part, unit_id, rules)
        if resolved_entity is not None:
            return resolved_entity
    if part in rules.get("npc_rules", {}):
        has_rule = True
        resolved_npc = resolve_npc_group(part, unit_id, rules)
        if resolved_npc is not None:
            return resolved_npc
    if has_rule:
        return None
    if is_invalid_name(part):
        return None
    return part


def generate_speaker_appearance(story_dir=STORY_DIR, output_path=OUTPUT_PATH, rules=None):
    """掃描全部劇情 JSON 並輸出經 unit_id 嚴格驗證的 speaker_appearance.json。"""
    if rules is None:
        rules = write_speaker_identity_rules()

    speaker_rules = rules.get("speaker_rules", {})
    npc_rules = rules.get("npc_rules", {})
    appearances = {}

    story_dir_path = Path(story_dir)
    for filename in sorted(os.listdir(story_dir_path)):
        if not filename.endswith(".json") or filename in ("chapters.json", "speaker_appearance.json"):
            continue
        stem = filename[:-5]
        if not stem.isdigit():
            continue
        story_id = int(stem)

        file_path = story_dir_path / filename
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            continue

        if not isinstance(data, list):
            continue

        story_speakers = set()
        for item in data:
            if not isinstance(item, dict) or item.get("type") != "dialogue":
                continue
            raw_name = item.get("name")
            if not isinstance(raw_name, str):
                continue
            cleaned_name = raw_name.strip()
            if not cleaned_name or has_japanese_kana(cleaned_name):
                continue

            unit_id = item.get("unit_id")
            if cleaned_name in speaker_rules or cleaned_name in npc_rules:
                resolved = resolve_appearance_target(cleaned_name, unit_id, rules)
                if resolved and not is_invalid_name(resolved):
                    story_speakers.add(resolved)
                continue

            if is_invalid_name(cleaned_name):
                continue

            parts = COMPOUND_SPLIT_RE.split(cleaned_name)
            for part in parts:
                p = part.strip()
                if not p or is_invalid_name(p):
                    continue
                resolved = resolve_appearance_target(p, unit_id, rules)
                if resolved and not is_invalid_name(resolved):
                    story_speakers.add(resolved)

        for sp in story_speakers:
            appearances.setdefault(sp, set()).add(story_id)

    sorted_appearances = {}
    for sp, s_ids in sorted(appearances.items(), key=lambda x: (-len(x[1]), x[0])):
        sorted_appearances[sp] = sorted(s_ids)

    target_output = Path(output_path)
    with open(target_output, "w", encoding="utf-8") as f:
        json.dump(sorted_appearances, f, ensure_ascii=False, indent=2)

    print(
        f"Generated speaker_identity_rules.json ({len(rules['entities'])} entities, "
        f"{len(speaker_rules)} speaker_rules, {len(rules['npc_groups'])} npc_groups, {len(npc_rules)} npc_rules)"
    )
    print(f"Generated speaker_appearance.json with {len(sorted_appearances)} speakers.")
    return sorted_appearances


if __name__ == "__main__":
    generate_speaker_appearance()
