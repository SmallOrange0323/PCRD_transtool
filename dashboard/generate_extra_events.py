# -*- coding: utf-8 -*-
import os
import json
import sqlite3
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "redive_tw.db")
STORY_DIR = os.path.join(BASE_DIR, "story")
OUTPUT_JSON = os.path.join(BASE_DIR, "data", "extra_events.json")
THUMBNAILS_JSON = os.path.join(BASE_DIR, "data", "story_thumbnails.json")

def clean_event_title(sub_title):
    t = sub_title.replace("\r", "").strip()
    t = re.sub(r'\s+(序幕|終幕|結局|預告|開場動畫|新年演出|活動PV|第\d+話[a-z]?|特別篇\s*\d+|第\d+道)$', '', t)
    return t.replace("\n", " ").strip()

def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] 找不到資料庫: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    tbl_event = "v1_bcb39dad8fe906d3586223af561e36515101ac44636074abcfa35504ba963222"
    tbl_detail = "v1_12ee700accb4e213404602824efabca5f2349d87cbdee98c8a816f1077e3d485"

    try:
        c.execute(f"PRAGMA table_info({tbl_event})")
        cols_event = [col[1] for col in c.fetchall()]

        c.execute(f"PRAGMA table_info({tbl_detail})")
        cols_detail = [col[1] for col in c.fetchall()]
    except Exception as e:
        print(f"[ERROR] 載入新活動表失敗: {e}")
        conn.close()
        return

    col_ev_id = cols_event[2]
    col_ev_thumb = cols_event[-1]

    col_dt_ev_id = cols_detail[8]
    col_dt_story_id = cols_detail[14]
    col_dt_title = cols_detail[7]
    col_dt_sub_title = cols_detail[18]

    c.execute(f'SELECT "{col_ev_id}", "{col_ev_thumb}" FROM "{tbl_event}" WHERE "{col_ev_id}" >= 10000 ORDER BY "{col_ev_id}" ASC')
    db_events = c.fetchall()

    c.execute(f'SELECT "{col_dt_ev_id}", "{col_dt_story_id}", "{col_dt_title}", "{col_dt_sub_title}" FROM "{tbl_detail}" ORDER BY "{col_dt_ev_id}" ASC, "{col_dt_story_id}" ASC')
    db_details = c.fetchall()

    conn.close()

    event_details_map = {}
    for dt in db_details:
        ev_id, story_id, title, sub_title = dt
        if ev_id not in event_details_map:
            event_details_map[ev_id] = []
        event_details_map[ev_id].append({
            "story_id": story_id,
            "title": title,
            "sub_title": sub_title
        })

    local_files = set(os.listdir(STORY_DIR))

    events_list = []
    stories_list = []

    seen_ev_ids = set()
    for ev in db_events:
        ev_id, ev_thumb = ev

        if ev_id in seen_ev_ids:
            continue
        seen_ev_ids.add(ev_id)

        details = event_details_map.get(ev_id, [])
        if not details:
            continue

        has_local_data = False
        valid_stories_for_event = []
        candidate_title = None

        for d in details:
            story_id = d["story_id"]
            filename = f"{story_id}.json"
            if filename not in local_files:
                continue

            has_local_data = True

            if not candidate_title and d["sub_title"]:
                candidate_title = clean_event_title(d["sub_title"])

            still_id = None
            bg_id = None
            story_json_path = os.path.join(STORY_DIR, filename)
            if os.path.isfile(story_json_path):
                try:
                    with open(story_json_path, "r", encoding="utf-8") as sj:
                        elements = json.load(sj)
                        for elem in elements:
                            if elem.get("type") == "still" and not still_id:
                                val = elem.get("still") or elem.get("still_id")
                                if val and val != "end":
                                    still_id = val
                            if elem.get("type") == "background" and not bg_id:
                                bg_id = elem.get("background") or elem.get("bg_id")
                except Exception:
                    pass

            sub_id = story_id % 1000
            if sub_id == 0:
                chapter_name = "序幕"
            elif sub_id == 7:
                chapter_name = "終幕"
            elif sub_id >= 600:
                chapter_name = f"特別篇 {sub_id - 600}"
            elif sub_id >= 500:
                chapter_name = f"預告/特別演出"
            else:
                chapter_name = f"第 {sub_id} 話"

            story_obj = {
                "id": story_id,
                "chapter": chapter_name,
                "title": d["title"].strip(),
                "groupId": ev_id,
                "isEvent": True
            }
            if still_id is not None:
                story_obj["still_id"] = str(still_id)
            if bg_id is not None:
                story_obj["bg_id"] = str(bg_id)

            valid_stories_for_event.append(story_obj)

        if has_local_data:
            if not candidate_title:
                candidate_title = f"新活動 {ev_id}"

            events_list.append({
                "story_group_id": ev_id,
                "title": candidate_title,
                "start_time": "新形式活動",
                "thumbnail_id": ev_thumb if ev_thumb else 100131,
                "value": ev_id
            })
            stories_list.extend(valid_stories_for_event)

    output_data = {
        "events": events_list,
        "stories": stories_list
    }

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)

    print(f"[SUCCESS] 成功從資料庫動態生成防亂碼活動對照檔：{OUTPUT_JSON}")
    print(f"  ▶ 新活動總數: {len(events_list)}")
    print(f"  ▶ 話數總數: {len(stories_list)}")

    existing_thumbs = {}
    if os.path.isfile(THUMBNAILS_JSON):
        try:
            with open(THUMBNAILS_JSON, "r", encoding="utf-8") as tf:
                existing_thumbs = json.load(tf)
        except Exception:
            pass

    for s in stories_list:
        sid = str(s["id"])
        entry = {
            "still_id": s.get("still_id"),
            "bg_id": s.get("bg_id")
        }
        existing_thumbs[sid] = entry

    with open(THUMBNAILS_JSON, "w", encoding="utf-8") as tf:
        json.dump(existing_thumbs, tf, ensure_ascii=False, indent=4)

    print(f"  ▶ story_thumbnails.json 已更新，共 {len(existing_thumbs)} 筆")

if __name__ == '__main__':
    main()
