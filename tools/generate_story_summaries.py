# -*- coding: utf-8 -*-
import os
import sys
import json
import urllib.request
import re

sys.stdout.reconfigure(encoding='utf-8')

# 配置資訊
STORY_DIR = "dashboard/story"
CHAPTERS_JSON = "dashboard/data/chapters.json"
OPENCODE_API_URL = "http://localhost:4096/api/chat"  # OpenCode 本地伺服器的 Chat 端點

def clean_text(text):
    if not text:
        return ""
    text = text.replace("{player}", "佑樹")
    text = re.sub(r'\[.*?\]', '', text)  # 清除遊戲控制碼
    return text.strip()

def get_dialogue_text(story_id):
    filepath = os.path.join(STORY_DIR, f"{story_id}.json")
    if not os.path.exists(filepath):
        return None
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        dialogues = []
        if isinstance(data, dict) and "dialogue" in data:
            dialogues = data["dialogue"]
        elif isinstance(data, list):
            dialogues = data
            
        lines = []
        for item in dialogues:
            words = clean_text(item.get("words", ""))
            if not words:
                continue
            speaker = item.get("name", item.get("speaker", "旁白")).strip()
            lines.append(f"{speaker}: {words}")
            
        # 限制字數以防超出 token 限制，取前 150 句對白即可概括大意
        return "\n".join(lines[:150])
    except Exception as e:
        print(f"  ❌ 讀取 {story_id} 失敗: {e}")
        return None

def query_opencode_llm(prompt_text):
    # 使用 OpenCode 預設的 LLM 進行單發對話
    # 這裡採用 OpenCode 標準的 API 結構，若需要，也可以透過呼叫本地 OpenCode 伺服器
    payload = {
        "model": "opencode/nemotron-3-ultra-free", # 使用 OpenCode 免費的超大模型
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一位熟知《公主連結 Re:Dive》繁中版劇情的資深史官。\n"
                    "請閱讀以下劇情對白，並以「繁體中文」寫下一句簡短（不超過 50 字）的核心事件摘要。\n"
                    "注意事項：\n"
                    "1. 必須嚴格基於提供的對白總結，不要有任何幻覺。\n"
                    "2. 不要加上『本話講述了...』或『這段劇情...』等贅字，直接說明事件。\n"
                    "3. 角色名字以台版 So-net 官方翻譯為準（如：貪吃佩可、可可蘿、凱留、佑樹）。"
                )
            },
            {
                "role": "user",
                "content": f"以下是該話的對白文本：\n\n{prompt_text}"
            }
        ],
        "temperature": 0.3
    }
    
    req = urllib.request.Request(
        OPENCODE_API_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            res_data = json.loads(res.read().decode('utf-8'))
            summary = res_data["choices"][0]["message"]["content"].strip()
            # 清理可能的引號
            summary = summary.replace('"', '').replace('「', '').replace('」', '')
            return summary
    except Exception as e:
        print(f"  ❌ 連接 OpenCode API 失敗: {e}")
        return None

def main():
    print("====================================================")
    print("      🚀 公主連結劇情 JSON 自動化摘要生成工具")
    print("====================================================")
    
    if not os.path.exists(CHAPTERS_JSON):
        print(f"❌ 找不到 chapters.json: {CHAPTERS_JSON}")
        return
        
    with open(CHAPTERS_JSON, 'r', encoding='utf-8') as f:
        chapters = json.load(f)
        
    # 我們以 Part 3 主線 (2201 ~ 2215) 作為範例或批次更新的目標
    # 您也可以視需要擴展到其他 Part
    gw_part3 = chapters.get("3", {}).get("game_world", {})
    if not gw_part3:
        print("未在 chapters.json 中找到 Part 3 的主線資料！")
        return
        
    print(f"開始為 Part 3 主線章節 (共 {len(gw_part3)} 章) 提取並生成真實摘要...")
    
    modified = False
    for group_id, chapter_info in sorted(gw_part3.items()):
        chapter_name = chapter_info.get("name", f"第 {group_id} 章")
        print(f"\n📖 正在處理: {chapter_name}")
        
        stories = chapter_info.get("stories", [])
        for story in stories:
            story_id = story.get("story_id")
            title = story.get("title", "")
            current_summary = story.get("summary", "")
            
            # 若摘要已經是寫死的或空的，就呼叫 LLM 進行提取
            if not current_summary or "本話" in current_summary or len(current_summary) > 100:
                print(f"  📥 正在讀取話數: {title} (ID: {story_id})...")
                dialogue_text = get_dialogue_text(story_id)
                if not dialogue_text:
                    print("    ⚠️ 無法取得該話對話 JSON 檔案，跳過。")
                    continue
                    
                print("    🤖 呼叫 OpenCode LLM 進行實時劇情摘要...")
                summary = query_opencode_llm(dialogue_text)
                if summary:
                    print(f"    🎯 生成摘要: {summary}")
                    story["summary"] = summary
                    modified = True
                else:
                    print("    ❌ 摘要生成失敗。")
                    
    if modified:
        with open(CHAPTERS_JSON, 'w', encoding='utf-8') as f:
            json.dump(chapters, f, ensure_ascii=False, indent=2)
        print("\n💾 [SUCCESS] 已成功將最新生成的劇情摘要寫入 chapters.json！")
    else:
        print("\n無任何變更或所有話數均已有精確摘要。")

if __name__ == "__main__":
    main()
