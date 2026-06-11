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

def clean_event_title(sub_title):
    # 先清理回車
    t = sub_title.replace("\r", "").strip()
    # 使用正則去掉尾部話數/章節標識
    t = re.sub(r'\s+(序幕|終幕|結局|預告|開場動畫|新年演出|活動PV|第\d+話[a-z]?|特別篇\s*\d+|第\d+道)$', '', t)
    # 將可能殘留的多餘換行換成空格以確保美觀
    return t.replace("\n", " ").strip()

def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] 找不到資料庫: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 混淆表名定義
    tbl_event = "v1_477dfa8856318c23867a29f4207a55e10a549d5fdfa3ef01e82b47fcdac6cb78"
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

    # 欄位對應
    col_ev_id = cols_event[4]
    col_ev_thumb = cols_event[-1] # 最後一個欄位是頭像

    col_dt_ev_id = cols_detail[8]
    col_dt_story_id = cols_detail[14]
    col_dt_title = cols_detail[7]
    col_dt_sub_title = cols_detail[18]

    # 1. 查詢所有新活動總表 (只取 ID 和頭像，不取亂碼的標題)
    c.execute(f'SELECT "{col_ev_id}", "{col_ev_thumb}" FROM "{tbl_event}" WHERE "{col_ev_id}" >= 10000 ORDER BY "{col_ev_id}" ASC')
    db_events = c.fetchall()

    # 2. 查詢所有新活動話數明細 (包含明文無亂碼的 sub_title)
    c.execute(f'SELECT "{col_dt_ev_id}", "{col_dt_story_id}", "{col_dt_title}", "{col_dt_sub_title}" FROM "{tbl_detail}" ORDER BY "{col_dt_ev_id}" ASC, "{col_dt_story_id}" ASC')
    db_details = c.fetchall()

    conn.close()

    # 建立 event_id -> 詳情對照
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

    # 本地已下載的所有 JSON 檔
    local_files = set(os.listdir(STORY_DIR))

    events_list = []
    stories_list = []

    # 遍歷活動，僅在本地確實有下載到該活動任何話數 JSON 時才加入
    for ev in db_events:
        ev_id, ev_thumb = ev
        
        details = event_details_map.get(ev_id, [])
        if not details:
            continue

        # 檢查本地是否有任何一話的 JSON
        has_local_data = False
        valid_stories_for_event = []
        
        # 收集用於清洗出活動標題的候選 sub_title (通常取「序幕」或第一話)
        candidate_title = None

        for d in details:
            story_id = d["story_id"]
            filename = f"{story_id}.json"
            if filename in local_files:
                has_local_data = True
                
                # 如果還沒有候選標題，且該話有 sub_title，就當作候選
                if not candidate_title and d["sub_title"]:
                    candidate_title = clean_event_title(d["sub_title"])
                
                # 解析話數名稱 (例如：序幕、第 1 話)
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

                valid_stories_for_event.append({
                    "id": story_id,
                    "chapter": chapter_name,
                    "title": d["title"].strip(),
                    "groupId": ev_id,
                    "isEvent": True
                })

        if has_local_data:
            # 如果還是沒有成功清洗出標題，給予一個防禦性名稱
            if not candidate_title:
                candidate_title = f"新活動 {ev_id}"
                
            # 加入活動列表
            events_list.append({
                "story_group_id": ev_id,
                "title": candidate_title,
                "start_time": "新形式活動", 
                "thumbnail_id": ev_thumb if ev_thumb else 100131,
                "value": ev_id
            })
            stories_list.extend(valid_stories_for_event)

    # 輸出 json 檔案
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

if __name__ == '__main__':
    main()
