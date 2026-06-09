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
import json
import glob

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY_DIR = os.path.join(BASE_DIR, "story")
OUTPUT_PATH = os.path.join(STORY_DIR, "speaker_appearance.json")


def main():
    if not os.path.exists(STORY_DIR):
        print(f"[ERROR] 找不到對白目錄：{STORY_DIR}")
        return

    json_files = glob.glob(os.path.join(STORY_DIR, "*.json"))
    speaker_map = {}

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
            if name and name not in ("旁白", "【系統】", "？？？"):
                # 分割複合名稱（如 "貪吃佩可、凱留"）
                parts = [p.strip() for p in name.replace("＆", "、").replace("&", "、").replace("和", "、").replace("與", "、").split("、") if p.strip()]
                for part in parts:
                    if part and part not in ("旁白", "【系統】", "？？？"):
                        speakers_in_this.add(part)

        for speaker in speakers_in_this:
            if speaker not in speaker_map:
                speaker_map[speaker] = []
            speaker_map[speaker].append(story_id_num)

    # 排序
    for speaker in speaker_map:
        speaker_map[speaker].sort()

    # 依登場次數排序輸出
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
