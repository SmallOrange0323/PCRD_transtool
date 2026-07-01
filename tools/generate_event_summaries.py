# -*- coding: utf-8 -*-
import os
import sys
import json
import sqlite3
import urllib.request
import re
import time

sys.stdout.reconfigure(encoding='utf-8')

# 動態解析相對於腳本所在目錄的絕對路徑，防範 CWD 偏移與 OneDrive Unicode 路徑問題
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STORY_DIR = os.path.join(SCRIPT_DIR, "dashboard", "story")
EVENT_SUMMARIES_JSON = os.path.join(SCRIPT_DIR, "dashboard", "data", "event_summaries.json")
EXTRA_EVENTS_JSON = os.path.join(SCRIPT_DIR, "dashboard", "data", "extra_events.json")
DB_PATH = os.path.join(SCRIPT_DIR, "dashboard", "redive_tw.db")
OLLAMA_API_URL = "http://127.0.0.1:11434/api/chat"
LOG_FILE = os.path.join(SCRIPT_DIR, "scratch", "event_generation_progress.log")

def write_log(msg):
    print(msg)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(str(msg) + "\n")
    except Exception:
        pass

def clean_text(text):
    if not text:
        return ""
    text = text.replace("{player}", "佑樹")
    text = re.sub(r'\[.*?\]', '', text)
    return text.strip()

def get_event_dialogue_stream(story_ids, limit_lines=150, max_per_story=15):
    event_lines = []
    # 限制每個活動最多抓取前幾個重要話數以防 text 太長
    for story_id in story_ids:
        filepath = os.path.join(STORY_DIR, f"{story_id}.json")
        if not os.path.exists(filepath):
            continue
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            dialogues = data if isinstance(data, list) else data.get("dialogue", [])
            
            valid_dialogues = []
            for item in dialogues:
                words = clean_text(item.get("words", ""))
                if not words:
                    continue
                speaker = item.get("name", item.get("speaker", "旁白")).strip()
                if speaker in ["旁白", "店員", "店長", "街坊鄰居", "眾人"] and len(words) < 5:
                    continue
                valid_dialogues.append(f"{speaker}: {words}")
                
            # 均勻抽取：當話數台詞很多時，抽取前半段與後半段（結尾），避免模型只看前言
            n = len(valid_dialogues)
            if n <= max_per_story:
                event_lines.extend(valid_dialogues)
            else:
                half = max_per_story - 5
                event_lines.extend(valid_dialogues[:half])
                event_lines.extend(valid_dialogues[-5:])
        except Exception as e:
            write_log(f"  ❌ 讀取 {story_id} 對話失敗: {e}")
            
    # 取全部收集到的對白之前 limit_lines 句，確保能覆蓋大型活動的前後篇
    return "\n".join(event_lines[:limit_lines])

def query_ollama_llm(prompt_text, event_title, is_large=False):
    word_limit = "不低於 300 字" if not is_large else "1000 至 1500 字（必須包含故事完整的前因、發展、高潮衝突與大結局）"
    payload = {
        "model": "gemma4:12b",
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一位熟知《公主連結 Re:Dive》繁中版劇情的編輯。\n"
                    f"請用繁體中文撰寫該活動劇情{word_limit}的詳細劇情大綱介紹。\n"
                    "注意事項：\n"
                    "1. 專注於描述該活動的核心故事背景、登場的主要角色、發生的主要事件/危機，以及最終如何解決。\n"
                    "2. 嚴禁使用『起承轉合』、『第一部分：起』、『結構分析』、『編輯短評』等學術生硬字眼，請用自然故事敘述體，在交代完最後一個情節後直接結束，不要有結論或短評。\n"
                    "3. 譯名必須完全對齊台版官方翻譯（主角為「佑樹」；可可蘿、貪吃佩可、凱留、雪菲、愛梅斯等）。"
                )
            },
            {
                "role": "user",
                "content": f"這是活動《{event_title}》的劇情對白節錄：\n\n{prompt_text}\n\n請撰寫其劇情大綱與介紹。"
            }
        ],
        "options": {
            "temperature": 0.2
        },
        "stream": False
    }
    
    req = urllib.request.Request(
        OLLAMA_API_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )
    
    try:
        # 大型活動推理耗時長，將 timeout 調為 180 秒
        with urllib.request.urlopen(req, timeout=180) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data["message"]["content"].strip()
    except Exception as e:
        write_log(f"  ❌ 呼叫 Ollama API 失敗: {e}")
        return None

def main():
    write_log("🚀 開始執行活動劇情摘要 AI 生成器 ...")
    
    # 載入現有摘要以利斷點續傳
    existing_summaries = {}
    if os.path.exists(EVENT_SUMMARIES_JSON):
        try:
            with open(EVENT_SUMMARIES_JSON, 'r', encoding='utf-8') as f:
                existing_summaries = json.load(f)
            print(f"Loaded {len(existing_summaries)} existing summaries.")
            print(f"[Debug] EVENT_SUMMARIES_JSON path: {os.path.abspath(EVENT_SUMMARIES_JSON)}")
        except Exception as e:
            print(f"Error loading existing summaries: {e}")

    # 一啟動就強制同步寫入，確保檔案在正確的 workspace E 槽與 dist 目錄被建立
    try:
        os.makedirs(os.path.dirname(EVENT_SUMMARIES_JSON), exist_ok=True)
        with open(EVENT_SUMMARIES_JSON, 'w', encoding='utf-8') as f:
            json.dump(existing_summaries, f, ensure_ascii=False, indent=4)
        print(f"[Init] Synchronized local json: {EVENT_SUMMARIES_JSON}")
        
        dist_json = os.path.join(SCRIPT_DIR, "dist_story_map", "data", "event_summaries.json")
        os.makedirs(os.path.dirname(dist_json), exist_ok=True)
        with open(dist_json, 'w', encoding='utf-8') as f:
            json.dump(existing_summaries, f, ensure_ascii=False, indent=4)
        print(f"[Init] Synchronized dist json: {dist_json}")
    except Exception as e:
        print(f"❌ Error initializing JSON files: {e}")

    # 1. 自 SQLite 載入傳統活動
    events = {}
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            
            # 取得活動主檔
            cur.execute("SELECT story_group_id, title FROM event_story_data")
            for gid, title in cur.fetchall():
                events[gid] = {
                    "title": title,
                    "story_ids": []
                }
                
            # 取得活動話數明細
            cur.execute("SELECT story_id, story_group_id FROM event_story_detail ORDER BY story_id ASC")
            for sid, gid in cur.fetchall():
                if gid in events:
                    events[gid]["story_ids"].append(sid)
            conn.close()
        except Exception as e:
            write_log(f"❌ 讀取 SQLite 失敗: {e}")

    # 2. 自 extra_events.json 載入新形式活動
    if os.path.exists(EXTRA_EVENTS_JSON):
        try:
            with open(EXTRA_EVENTS_JSON, 'r', encoding='utf-8') as f:
                extra = json.load(f)
            
            # 合併新形式活動主檔
            for evt in extra.get("events", []):
                gid = evt.get("story_group_id")
                title = evt.get("title", "").replace("\\n", " ").strip()
                if gid not in events:
                    events[gid] = {
                        "title": title,
                        "story_ids": []
                    }
                    
            # 合併新形式活動話數
            for s in extra.get("stories", []):
                gid = s.get("groupId")
                sid = s.get("id")
                if gid in events and sid not in events[gid]["story_ids"]:
                    events[gid]["story_ids"].append(sid)
        except Exception as e:
            write_log(f"❌ 讀取 extra_events.json 失敗: {e}")

    LARGE_EVENT_PAIRS = {
        5035: 5036,
        5058: 5059,
        5084: 5085,
        5110: 5111,
        10201: 10202,
        5136: 5137
    }
    STANDALONE_LARGE_EVENTS = {10213}
    
    # 針對大型活動前後篇，如果已存在的摘要字數過短（少於 800 字），則強制刪除以重新生成
    for front, back in LARGE_EVENT_PAIRS.items():
        sf, sb = str(front), str(back)
        need_regen = False
        if sf in existing_summaries and len(existing_summaries[sf]) < 800:
            need_regen = True
        if sb in existing_summaries and len(existing_summaries[sb]) < 800:
            need_regen = True
            
        if need_regen:
            write_log(f"  🧹 大型活動前後篇 {sf} 或 {sb} 的現有摘要不足 800 字，將強制刪除並重新生成。")
            if sf in existing_summaries:
                del existing_summaries[sf]
            if sb in existing_summaries:
                del existing_summaries[sb]

    # 針對單篇大型活動
    for gid in STANDALONE_LARGE_EVENTS:
        sf = str(gid)
        if sf in existing_summaries and len(existing_summaries[sf]) < 800:
            write_log(f"  🧹 單篇大型活動 {sf} 的現有摘要不足 800 字，將強制刪除並重新生成。")
            del existing_summaries[sf]

    print(f"找到 {len(events)} 個活動。")
    
    # 過濾出「尚未生成」的活動
    todo_gids = [gid for gid in events if str(gid) not in existing_summaries]
    print(f"待生成活動數: {len(todo_gids)}")
    
    if not todo_gids:
        print("🎉 所有活動摘要已生成完畢！")
        return

    # 提供 limit，改為一次跑全部以進行完整批次生成
    limit = 999
    count = 0
    
    # 建立一個集合包含所有的後篇 ID，避免重複處理
    back_ids_set = set(LARGE_EVENT_PAIRS.values())
    
    for gid in todo_gids:
        if count >= limit:
            print(f"\n💡 已達到單次測試上限 {limit} 個活動。如果測試正常，您可以再次執行以繼續生成。")
            break
            
        # 如果是後篇 ID，則跳過，因為會在前篇合併處理時一起寫入
        if gid in back_ids_set:
            continue
            
        evt_info = events[gid]
        title = evt_info["title"]
        sids = evt_info["story_ids"]
        
        is_large = (gid in LARGE_EVENT_PAIRS) or (gid in STANDALONE_LARGE_EVENTS)
        back_gid = LARGE_EVENT_PAIRS.get(gid)
        
        if is_large and back_gid:
            # 合併前篇與後篇的故事對白
            if back_gid in events:
                sids = sids + events[back_gid]["story_ids"]
                title = f"{title} & {events[back_gid]['title']}"
        
        # 尋找本地是否有對白 json，若是完全沒有 json 則略過
        has_dialogue = any(os.path.exists(os.path.join(STORY_DIR, f"{sid}.json")) for sid in sids)
        if not has_dialogue:
            continue
            
        write_log(f"\n🎬 正在為活動 【{title}】 (ID: {gid}{f' + {back_gid}' if back_gid else ''}) 提取對白並呼叫 Gemma 4 12b 生成{'大型' if is_large else '一般'}摘要...")
        
        if is_large:
            dialogue_text = get_event_dialogue_stream(sids, limit_lines=350, max_per_story=25)
        else:
            dialogue_text = get_event_dialogue_stream(sids)
        
        if not dialogue_text.strip():
            write_log("  ⚠️ 對話節錄為空，略過。")
            continue
            
        # 針對 5001 初音活動，特別加強提示與後處理，防範大模型對妹妹名字「小栞」的幻覺
        custom_title = title
        if str(gid) == "5001":
            custom_title = f"{title}（注意：初音的妹妹是小栞，絕對不能寫成小凜）"
            
        summary = query_ollama_llm(dialogue_text, custom_title, is_large=is_large)
        if summary:
            if str(gid) == "5001":
                summary = summary.replace("小凜", "小栞").replace("伊莉絲白牧場", "伊麗莎白牧場")
            
            existing_summaries[str(gid)] = summary
            if is_large and back_gid:
                existing_summaries[str(back_gid)] = summary
                
            write_log(f"  ✅ 生成成功！字數: {len(summary)}")
            count += 1
            
            # 即時寫入 JSON 防止中斷遺失
            try:
                with open(EVENT_SUMMARIES_JSON, 'w', encoding='utf-8') as f:
                    json.dump(existing_summaries, f, ensure_ascii=False, indent=4)
                
                # 順便寫入一份到 dist_story_map/data 中以便發布 (防止打包腳本解譯亂碼路徑失敗)
                dist_json = os.path.join(SCRIPT_DIR, "dist_story_map", "data", "event_summaries.json")
                dist_dir = os.path.dirname(dist_json)
                if os.path.exists(dist_dir):
                    with open(dist_json, 'w', encoding='utf-8') as f:
                        json.dump(existing_summaries, f, ensure_ascii=False, indent=4)
            except Exception as e:
                write_log(f"  ❌ 儲存 JSON 失敗: {e}")
                
            # 稍微間隔以免頻率過快
            time.sleep(1.5)
        else:
            write_log("  ❌ 生成失敗。")
            time.sleep(2)

if __name__ == '__main__':
    main()

