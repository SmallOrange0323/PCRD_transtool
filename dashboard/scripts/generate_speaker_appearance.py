"""
PCRD Data Hub - 生成登場角色統計 (speaker_appearance.json)
掃描 dashboard/story/*.json，統計每個 speaker 出現的 story_id 列表

用法：
python dashboard/scripts/generate_speaker_appearance.py

輸出：
dashboard/story/speaker_appearance.json
{ "角色名": [story_id, ...], ... }
"""

import os
import sys
import json
import glob
import re

# 設定編碼，防止 Windows 終端機印出 utf-8 時發生編碼錯誤
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY_DIR = os.path.join(BASE_DIR, "story")
OUTPUT_PATH = os.path.join(STORY_DIR, "speaker_appearance.json")

INVALID_NAMES = {
    "3人", "３人", "4人", "４人", "5人", "５人", "2人", "２人", "三人",
    "大家", "大家的聲音", "全員", "一行人", "一夥", "人們",
    "兩人", "兩個人", "廢物", "日", "3個人",
    "男性", "女性", "男子", "女子", "大人", "男", "女",
    "少年", "少女", "老人", "青年", "小孩", "小孩子", "小孩們", "孩子們",
    "母親", "父親", "主人", "大人",
    "魔物", "魔物群", "魔物們", "殭屍群", "動物群", "鳥群", "蟲群", "魚", "貓", "狗", "馬", "龍", "牛", "狼",
    "群眾", "民眾", "觀眾", "觀眾們", "聽眾", "聽眾們",
    "聲音", "歌聲", "笑聲", "聲", "光之文字", "告示", "指示", "邀請函",
    "{0}",
}

INVALID_PATTERNS = [
    r'^\d+$',
    r'^[男女][１２３４５12]?$',
    r'^[男女]性[１２３４５12]?$',
    r'^(壞人|流氓|小混混|暴徒|無賴|不良|地痞|手下|士兵|騎士|隊長|部下|傭兵|護衛|盜賊|刺客)[１２３４５12]?$',
    r'^(觀眾|觀客|聽眾|路人|顧客|客人|鎮民|市民|村民|居民|島民|參加者|新兵|團員|職員|社員|工作人員|粉絲)[１２３４５12]?[０0]?$',
    r'^(小孩|小孩子|少年|少女|男學生|女學生|學生|男孩|女孩|男孩子|女孩子)[１２３４５12]?$',
    r'^(鎮民|村民|居民|市民|民眾|群眾|觀眾|客人|顧客|粉絲|團員|職員|社員|手下|傭兵|士兵|騎士|流氓|暴徒|不良|無賴|小混混|壞人|地痞|盜賊|新兵|參加者|觀客|路人|聽眾)們?$',
]

ALIASES = {
    "貪吃佩可的聲音": "貪吃佩可", "大食客": "貪吃佩可", "飢餓的公主": "貪吃佩可",
    "尤絲蒂亞娜": "貪吃佩可", "尤絲蒂亞娜·馮·阿斯特賴亞": "貪吃佩可", "佩可": "貪吃佩可",
    "可可蘿的聲音": "可可蘿", "導引者": "可可蘿", "引導者": "可可蘿", "導引少女": "可可蘿",
    "棗可可蘿": "可可蘿", "kokoro": "可可蘿", "可蘿": "可可蘿",
    "凱留的聲音": "凱留", "貓耳魔法少女": "凱留",
    "希留耶": "凱留", "百地希留耶": "凱留",
    "美空的聲音": "美空", "魅空": "美空", "園上魅空": "美空", "流魅空": "美空",
    "日和的聲音": "日和", "日和莉": "日和", "春咲日和莉": "日和",
    "優衣的聲音": "優衣", "草野優衣": "優衣",
    "憐的聲音": "憐", "士織": "憐", "士条怜": "憐",
    "雪菲的聲音": "雪菲", "阿斯特賴亞・雪菲": "雪菲",
    "琪愛兒的聲音": "琪愛兒", "風間千愛爾": "琪愛兒",
    "霸瞳天星的聲音": "霸瞳皇帝", "霸瞳天星": "霸瞳皇帝",
    "拉比林斯達的聲音": "拉比林斯達", "克莉絲提娜的聲音": "克莉絲提娜",
    "露娜的聲音": "露娜", "厄莉絲的聲音": "厄莉絲",
    "雪的聲音": "雪", "流夏的聲音": "流夏", "暮光流星的成員": "流夏",
    "似似花的聲音": "似似花", "亞里莎的聲音": "亞里莎",
    "帆稀的聲音": "帆稀", "嘉夜的聲音": "嘉夜", "祈梨的聲音": "祈梨",
    "矛依未的聲音": "矛依未", "涅雅": "涅婭",
    "安涅默涅": "安涅默涅", "普蕾西亞": "普蕾西亞",
    "莉莉的聲音": "莉莉", "可璃的聲音": "可璃亞",
    "可璃": "可璃亞", "可璃亞的聲音": "可璃亞",
    "八斗金局長": "八斗神", "八斗": "八斗神", "八斗神局長": "八斗神",
    "剎鬼‧八斗神": "八斗神", "傻": "倭",
    "菲絲雷斯": "菲絲", "吉塔的聲音": "吉塔", "深月的聲音": "深月",
    "克蕾琪塔的聲音": "克蕾琪塔", "蘭法的聲音": "蘭法",
    "涅比亞的聲音": "涅比亞", "古蕾婭的聲音": "古蕾婭", "安的聲音": "安",
    "莫妮卡的聲音": "莫妮卡",
}


def is_invalid_name(name):
    if name in INVALID_NAMES:
        return True
    for pat in INVALID_PATTERNS:
        if re.match(pat, name):
            return True
    return False


def resolve_name(part, real_name_map):
    if is_invalid_name(part):
        return None

    part_clean = part.replace("（", "(").replace("）", ")").split("(")[0].strip()

    if part in real_name_map:
        part = real_name_map[part]
    elif part_clean in real_name_map:
        part = real_name_map[part_clean]

    resolved = ALIASES.get(part, part)
    clean = resolved.replace("（", "(").replace("）", ")").split("(")[0].strip()
    resolved = ALIASES.get(clean, resolved)

    if resolved in real_name_map:
        resolved = real_name_map[resolved]
    elif clean in real_name_map:
        resolved = real_name_map[clean]

    if resolved.endswith("的聲音"):
        resolved = resolved.replace("的聲音", "")

    if resolved and not is_invalid_name(resolved):
        return resolved
    return None


def main():
    if not os.path.exists(STORY_DIR):
        print(f"[ERROR] 找不到對白目錄：{STORY_DIR}")
        return

    json_files = glob.glob(os.path.join(STORY_DIR, "*.json"))
    speaker_map = {}

    real_name_map = {}
    map_path = os.path.join(BASE_DIR, "data", "real_name_mapping.json")
    if os.path.exists(map_path):
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                real_name_map = json.load(f)
            print(f"  ▶ 成功載入 {len(real_name_map)} 筆官方真名對照資料")
        except Exception as e:
            print(f"  ⚠️ 載入真名對照表失敗: {e}")

    for filepath in json_files:
        filename = os.path.basename(filepath)
        if filename == "speaker_appearance.json":
            continue

        story_id = filename.replace(".json", "")
        try:
            story_id_num = int(story_id)
        except ValueError:
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                dialogues = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  ⚠️ 跳過 {filename}: {e}")
            continue

        if not isinstance(dialogues, list):
            continue

        speakers_in_this = set()
        for item in dialogues:
            name = item.get("name", "").strip()
            if not name or name in ("旁白", "【系統】", "？？？"):
                continue
            parts = re.split(r'[、＆&]|\s[和與]\s', name)
            parts = [p.strip() for p in parts if p.strip()]
            for part in parts:
                if not part or part in ("旁白", "【系統】", "？？？"):
                    continue
                resolved = resolve_name(part, real_name_map)
                if resolved:
                    speakers_in_this.add(resolved)

        for speaker in speakers_in_this:
            if speaker not in speaker_map:
                speaker_map[speaker] = []
            speaker_map[speaker].append(story_id_num)

    for speaker in speaker_map:
        speaker_map[speaker].sort()

    sorted_map = dict(sorted(speaker_map.items(), key=lambda x: -len(x[1])))

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted_map, f, ensure_ascii=False, indent=2)

    total_speakers = len(sorted_map)
    total_appearances = sum(len(v) for v in sorted_map.values())
    print(f"[SUCCESS] 生成完成！")
    print(f"  ▶ 輸出：{OUTPUT_PATH}")
    print(f"  ▶ 角色數：{total_speakers}")
    print(f"  ▶ 登場總次數：{total_appearances}")


if __name__ == "__main__":
    main()
