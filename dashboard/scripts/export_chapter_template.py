"""
PCRD Data Hub - 匯出章節維護模板
從 story_detail 讀取所有 story_group_id + title
產生 chapters_template.json 供人工填寫標題/摘要
對照已有的 chapterTitles / chapterSummaries 找出缺漏

用法：
    python dashboard/scripts/export_chapter_template.py

輸出：
    dashboard/data/chapters_template.json
"""

import os
import sys
import json
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "redive_tw.db")
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "chapters_template.json")


def get_part_from_group_id(group_id):
    if group_id >= 3000:
        return 3
    if group_id >= 2007:
        return 2
    return 1


def get_default_key(part, group_id):
    if part == 1:
        if group_id == 2000:
            return "序章"
        return f"第{group_id - 2000}章"
    if part == 2:
        if group_id >= 3000:
            return f"幕間 {group_id - 3000}"
        return f"第{group_id - 2006}章"
    if part == 3:
        if group_id >= 4000:
            return f"幕間 {group_id - 4000}"
        return f"第{group_id - 3000}章"
    return f"群組 {group_id}"


def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] 找不到資料庫：{DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 取得主線劇情的所有 story_group_id
    cursor.execute("""
        SELECT DISTINCT story_group_id, MIN(story_id) as first_story
        FROM story_detail
        WHERE story_id >= 2000000 AND story_id < 3000000
        GROUP BY story_group_id
        ORDER BY story_group_id ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    # 載入現有的 chapters.json（如果有）
    existing = {}
    existing_path = os.path.join(BASE_DIR, "data", "chapters.json")
    if os.path.exists(existing_path):
        try:
            with open(existing_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    template = { "1": {}, "2": {}, "3": {} }
    new_count = 0
    existing_count = 0

    for group_id, first_story in rows:
        part = get_part_from_group_id(group_id)
        gid_str = str(group_id)

        # 檢查是否已存在
        part_data = existing.get(str(part), {})
        if gid_str in part_data:
            template[str(part)][gid_str] = part_data[gid_str]
            existing_count += 1
            continue

        # 新增模板
        ch_key = get_default_key(part, group_id)
        template[str(part)][gid_str] = {
            "title": "",
            "summary": "",
            "key": ch_key,
            "order": group_id,
            "_note": f"請填入此章節的官方標題與摘要（story_group_id={group_id}）"
        }
        new_count += 1

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    print(f"[SUCCESS] 匯出完成！")
    print(f"  ▶ 輸出：{OUTPUT_PATH}")
    print(f"  ▶ 既有章節：{existing_count}")
    print(f"  ▶ 新增模板：{new_count}")
    print(f"  ▶ 總計：第一部 {len(template['1'])} / 第二部 {len(template['2'])} / 第三部 {len(template['3'])}")
    print()
    print("請編輯 chapters_template.json，填入 title 與 summary 後更名為 chapters.json")


if __name__ == "__main__":
    main()
