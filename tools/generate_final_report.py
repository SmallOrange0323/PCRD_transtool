# -*- coding: utf-8 -*-
import os
import json
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "dashboard", "redive_tw.db")
STORY_DIR = os.path.join(BASE_DIR, "dashboard", "story")
REPORT_PATH = os.path.join(BASE_DIR, "peco_astraea_report.md")
ARTIFACT_REPORT_PATH = r"C:\Users\user\.gemini\antigravity\brain\74ca5ccd-fa30-418d-be8c-9b96f5ad843c\peco_astraea_report.md"

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # 1. 角色基本資料
    peco_profile = {}
    cur.execute("SELECT * FROM unit_profile WHERE unit_id = 138301")
    row = cur.fetchone()
    if row:
        peco_profile = {
            "聲優": row["voice"],
            "年齡": row["age"],
            "名字": row["unit_name"],
            "種族": row["race"],
            "身高": row["height"],
            "體重": row["weight"],
            "公會": row["guild"],
            "興趣": row["favorite"],
            "介紹": row["self_text"],
            "生日月": row["birth_month"],
            "自我介紹": row["catch_copy"],
            "血型": row["blood_type"],
            "生日日": row["birth_day"],
            "角色ID": row["unit_id"]
        }
        
    # 2. 技能說明
    skills_data = {}
    for sk_id, sk_name in [("UB", 1383001), ("Skill 1", 1383002), ("Skill 2", 1383003)]:
        cur.execute("SELECT * FROM skill_data WHERE skill_id = ?", (sk_name,))
        row = cur.fetchone()
        if row:
            skills_data[sk_id] = {
                "ID": sk_name,
                "名稱": row["name"],
                "說明": row["description"].replace("\\n", "\n")
            }
            
    # 3. 劇情大綱
    chara_stories = []
    cur.execute("SELECT * FROM story_detail WHERE story_id >= 1383001 AND story_id <= 1383004 ORDER BY story_id ASC")
    rows = cur.fetchall()
    for row in rows:
        chara_stories.append({
            "故事ID": row["story_id"],
            "標題": row["title"],
            "副標題": row["sub_title"]
        })
        
    conn.close()
    
    # 4. 寫入 Markdown 報告
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        write_report_content(f, peco_profile, skills_data, chara_stories)
        
    # 同時同步覆蓋 Artifacts 的報告
    if os.path.exists(os.path.dirname(ARTIFACT_REPORT_PATH)):
        with open(ARTIFACT_REPORT_PATH, "w", encoding="utf-8") as f:
            write_report_content(f, peco_profile, skills_data, chara_stories)
            
    print(f"🎉 完美的官方繁中劇情報告已重新生成！")
    print(f"  - 報告路徑 1: {REPORT_PATH}")
    print(f"  - 報告路徑 2: {ARTIFACT_REPORT_PATH}")

def write_report_content(f, peco_profile, skills_data, chara_stories):
    f.write("# 貪吃佩可（阿斯特萊亞）原生繁中數據與劇情報告\n\n")
    f.write("## 🎨 角色平面美術素材 (已下載)\n")
    f.write("- 👤 **3星角色頭像**：[unit_icon_138331.webp](file:///E:/OneDrive%20-%20%E5%AF%B0%E5%AE%87%E7%9F%A5%E8%AD%98%E7%A7%91%E6%8A%80%E8%82%A1%E4%BB%BD%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/PCRD_tool/dashboard/icon/unit/unit_icon_138331.webp)\n")
    f.write("- 🖼️ **3星卡面立繪大圖**：[card_full_138331.webp](file:///E:/OneDrive%20-%20%E5%AF%B0%E5%AE%87%E7%9F%A5%E8%AD%98%E7%A7%91%E6%8A%80%E8%82%A1%E4%BB%BD%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/PCRD_tool/dashboard/card/full/card_full_138331.webp)\n")
    f.write("*(註：阿斯特萊亞佩可為初始 3 星實裝角色，且個人劇情中無獨立的靜態 CG 插畫)*\n\n")
    
    f.write("## 👤 角色基本資料\n\n")
    if peco_profile:
        f.write("| 屬性 | 資料 |\n| --- | --- |\n")
        for k, v in peco_profile.items():
            f.write(f"| {k} | {v} |\n")
    else:
        f.write("*未獲取到個人資料*\n")
        
    f.write("\n## ⚔️ 角色技能數據 (原生繁中)\n\n")
    for sk_id, data in skills_data.items():
        f.write(f"### {sk_id}：{data['名稱']} (ID: `{data['ID']}`)\n")
        f.write(f"```text\n{data['說明']}\n```\n\n")
        
    f.write("## 🎬 個人劇情大綱 (So-net 官方標題)\n\n")
    for story in chara_stories:
        f.write(f"- **故事 ID `{story['故事ID']}`**: {story['標題']} — *{story['副標題']}*\n")
        
    f.write("\n## 💬 個人劇情對話文本擷取 (台版 CDN 解密原生繁中)\n\n")
    for story in chara_stories:
        sid = story["故事ID"]
        f.write(f"### 📖 第 {sid - 1383000} 話：{story['標題']}\n\n")
        
        json_path = os.path.join(STORY_DIR, f"{sid}.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as jf:
                dialogues = json.load(jf)
            f.write("| 說話者 | 台版官方原汁原味對白 | 語音檔 |\n| --- | --- | --- |\n")
            for d in dialogues[:15]: # 列出前 15 句
                voice_str = f"`{d['voice']}.m4a`" if d.get("voice") else "*無語音*"
                words_clean = d["words"].replace("\n", "<br>")
                f.write(f"| **{d['name']}** | {words_clean} | {voice_str} |\n")
            if len(dialogues) > 15:
                f.write(f"| ... | *(後續還有 {len(dialogues) - 15} 句對白)* | |\n")
        else:
            f.write("*未成功獲取對白。*\n")
        f.write("\n")

if __name__ == "__main__":
    main()
