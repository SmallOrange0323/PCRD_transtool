# -*- coding: utf-8 -*-
import os
import sys
import json
import sqlite3
import urllib.request
import re
import time

sys.stdout.reconfigure(encoding='utf-8')

# 配置資訊
STORY_DIR = "dashboard/story"
CHAPTERS_JSON = "dashboard/data/chapters.json"
DB_PATH = "dashboard/redive_tw.db"
OLLAMA_API_URL = "http://127.0.0.1:11434/v1/chat/completions"
LOG_FILE = "scratch/generation_progress.log"

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

def get_chapter_dialogue_stream(story_ids):
    chapter_lines = []
    for story_id in story_ids:
        filepath = os.path.join(STORY_DIR, f"{story_id}.json")
        if not os.path.exists(filepath):
            continue
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            dialogues = []
            if isinstance(data, dict) and "dialogue" in data:
                dialogues = data["dialogue"]
            elif isinstance(data, list):
                dialogues = data
                
            count = 0
            for item in dialogues:
                words = clean_text(item.get("words", ""))
                if not words:
                    continue
                speaker = item.get("name", item.get("speaker", "旁白")).strip()
                if speaker in ["旁白", "店員", "店長", "街坊鄰居", "眾人"] and len(words) < 5:
                    continue
                chapter_lines.append(f"{speaker}: {words}")
                count += 1
                if count >= 25:
                    break
        except Exception as e:
            write_log(f"  ❌ 讀取 {story_id} 對話失敗: {e}")
            
    return "\n".join(chapter_lines[:180])

def query_ollama_llm(prompt_text, part_name, chapter_name):
    payload = {
        "model": "gemma4:12b",
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一位熟知《公主連結 Re:Dive》繁中版主線劇情的編輯。\n"
                    "請用繁體中文撰寫該章不低於 500 字的詳細劇情大綱摘要。\n"
                    "注意事項：\n"
                    "1. 嚴禁使用『起承轉合』、『第一部分：起』、『結構分析』、『史官總結』等教科書式的生硬學術術語與結構標題。\n"
                    "2. 這是『劇情摘要』，請專注於清晰、流暢地敘述本章實際發生的故事經過、登場人物、衝突起因、戰鬥過程與最終結果。\n"
                    "3. 請避免過多無實質劇情內容的文學抒情修辭（例如『命運的齒輪』』、『潮水般的感官』、『風吹過髮梢』等過度渲染的文字），以直白、自然的故事敘事體，將劇情的來龍去脈與關鍵轉折具體地交代清楚。\n"
                    "4. 嚴禁在文章結尾加上任何針對劇情效果的『文學短評』、『大綱總結』或『心得分析』（例如不要出現『這段劇情雖然簡短，卻交代了...』或『本章成功建立了...的開端』等主觀點評文字），請在交代完最後一個情節後直接結束。\n"
                    "5. 名詞譯名必須採用台版官方翻譯（主角為「佑樹」；七冠角色分別為霸瞳皇帝（本名千里真那，持有權能名稱為霸瞳天星）、迷宮女王（拉比林斯達）、誓約女君（克莉絲提娜）、副教授（似似花）等）。請特別注意：角色的稱呼是「霸瞳皇帝」而非「霸瞳天星」，「霸瞳天星」是其權能名稱；且矛依未在劇中的代號是「諾維姆」而非「諾維米」。"
                )
            },
            {
                "role": "user",
                "content": f"這是《公主連結 Re:Dive》{part_name} - {chapter_name} 的對話節錄：\n\n{prompt_text}\n\n請撰寫劇情大綱摘要。"
            }
        ],
        "temperature": 0.2
    }
    
    req = urllib.request.Request(
        OLLAMA_API_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as res:
                res_data = json.loads(res.read().decode('utf-8'))
                choices = res_data.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    summary = message.get("content", "").strip()
                    if len(summary) >= 200:
                        return summary
                    else:
                        write_log(f"  ⚠️ 摘要長度不足 ({len(summary)} 字)，重試...")
                else:
                    write_log("  ⚠️ 回傳 choices 為空，重試...")
        except Exception as e:
            write_log(f"  ⚠️ 嘗試 {attempt + 1} 失敗: {e}")
            time.sleep(2)
            
    return None

def main():
    try:
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
    except Exception:
        pass
        
    write_log("====================================================")
    write_log("      🚀 公主連結章節 500字長摘要離線批量生成工具")
    write_log("====================================================")
    
    if not os.path.exists(CHAPTERS_JSON):
        write_log(f"❌ 找不到 chapters.json: {CHAPTERS_JSON}")
        return
    if not os.path.exists(DB_PATH):
        write_log(f"❌ 找不到資料庫: {DB_PATH}")
        return
        
    with open(CHAPTERS_JSON, 'r', encoding='utf-8') as f:
        chapters = json.load(f)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT story_id, story_group_id 
        FROM story_detail 
        WHERE story_id >= 2000000 AND story_id < 3000000 
        ORDER BY story_id;
    """)
    db_stories = cursor.fetchall()
    conn.close()
    
    group_map = {}
    for story_id, group_id in db_stories:
        if group_id not in group_map:
            group_map[group_id] = []
        group_map[group_id].append(story_id)
        
    part_names = {
        "1": "第一部：王都重置篇 (Part 1)",
        "2": "第二部：厄莉絲與救贖篇 (Part 2)",
        "3": "第三部：全新世界篇 (Part 3)"
    }
    
    modified = False
    chapter_count = 0
    
    for part_key in ["1", "2", "3"]:
        gw = chapters.get(part_key, {}).get("game_world", {})
        part_name = part_names[part_key]
        
        for group_id_str in sorted(gw.keys(), key=int):
            group_id = int(group_id_str)
            chapter_info = gw[group_id_str]
            key_name = chapter_info.get("key", f"第 {group_id_str} 章")
            title = chapter_info.get("title", "")
            current_summary = chapter_info.get("summary", "")
            
            # 強制覆蓋所有章節，以套用最正確的名詞修正與格式
            if False:
                write_log(f"⏭️ {part_name} - {key_name}：{title} 已有長摘要 ({len(current_summary)} 字)，跳過。")
                continue
                
            story_ids = group_map.get(group_id, [])
            if not story_ids:
                write_log(f"⚠️ {part_name} - {key_name}：{title} 無關聯話數，跳過。")
                continue
                
            write_log(f"\n📖 正在提取 {part_name} - {key_name}：{title} 的對話流...")
            stream_text = get_chapter_dialogue_stream(story_ids)
            if not stream_text:
                write_log("  ⚠️ 找不到任何本章的對白 JSON，跳過。")
                continue
                
            write_log(f"🤖 正在呼叫本地 Ollama gemma4:12b 進行長摘要生成 (對話長度 {len(stream_text)} 字)...")
            long_summary = query_ollama_llm(stream_text, part_name, f"{key_name}：{title}")
            
            if long_summary:
                long_summary = long_summary.strip()
                long_summary = long_summary.replace("龍之浮用", "龍之浮島")
                long_summary = long_summary.replace("諾維米", "諾維姆")
                long_summary = long_summary.replace("霸瞳天星", "霸瞳皇帝")
                write_log(f"  🎯 成功生成 {len(long_summary)} 字的長摘要！")
                chapter_info["summary"] = long_summary
                modified = True
                chapter_count += 1
                
                with open(CHAPTERS_JSON, 'w', encoding='utf-8') as f:
                    json.dump(chapters, f, ensure_ascii=False, indent=2)
            else:
                write_log("  ❌ 生成失敗。")
                
    write_log(f"\n✅ 離線長摘要生成完成！共更新 {chapter_count} 個章節的摘要。")

if __name__ == "__main__":
    main()
