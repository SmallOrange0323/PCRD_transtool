# -*- coding: utf-8 -*-
import json
import os
import shutil
import sys

# 確保輸出編碼為 utf-8 以免 Windows 終端崩潰
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

def safe_copy_tree(src, dst):
    if not os.path.exists(dst):
        os.makedirs(dst, exist_ok=True)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            safe_copy_tree(s, d)
        else:
            try:
                if os.path.exists(d) and os.path.getsize(s) == os.path.getsize(d):
                    continue
                shutil.copy2(s, d)
            except Exception:
                pass

def main():
    # 定位根目錄與路徑
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    dashboard_dir = os.path.join(project_root, "dashboard")
    dist_dir = os.path.join(project_root, "dist_story_map")
    
    print(f"[Info] 開始封裝獨立部署的劇情地圖...")
    print(f"[Info] 專案根目錄: {project_root}")
    print(f"[Info] 輸出目標目錄: {dist_dir}")
    
    # 清理舊的輸出目錄 (非必要，由 safe_copy_tree 與覆寫完成)
    os.makedirs(dist_dir, exist_ok=True)
    os.makedirs(os.path.join(dist_dir, "data"), exist_ok=True)
    os.makedirs(os.path.join(dist_dir, "story"), exist_ok=True)
    
    # 核心靜態文件映射
    # (來源路徑, 目標相對路徑)
    core_files = [
        (os.path.join(dashboard_dir, "story_map.html"), "index.html"),
        (os.path.join(dashboard_dir, "style.css"), "style.css"),
        (os.path.join(dashboard_dir, "db.js"), "db.js"),
        (os.path.join(dashboard_dir, "avatar-service.js"), "avatar-service.js"),
        (os.path.join(dashboard_dir, "story-asset-service.js"), "story-asset-service.js"),
        (os.path.join(dashboard_dir, "chapter-data.js"), "chapter-data.js"),
        (os.path.join(dashboard_dir, "characters.js"), "characters.js"),
        (os.path.join(dashboard_dir, "map.js"), "map.js"),
        (os.path.join(dashboard_dir, "redive_tw.db"), "redive_tw.db"),
        (os.path.join(dashboard_dir, "sql-wasm.js"), "sql-wasm.js"),
        (os.path.join(dashboard_dir, "sql-wasm.wasm"), "sql-wasm.wasm"),
        (os.path.join(dashboard_dir, "data", "chapters.json"), "data/chapters.json"),
        (os.path.join(dashboard_dir, "data", "extra_events.json"), "data/extra_events.json"),
        (os.path.join(dashboard_dir, "data", "npc_avatars.json"), "data/npc_avatars.json"),
        (os.path.join(dashboard_dir, "data", "real_name_mapping.json"), "data/real_name_mapping.json"),
        (os.path.join(dashboard_dir, "data", "story_thumbnails.json"), "data/story_thumbnails.json"),
        (os.path.join(dashboard_dir, "data", "event_summaries.json"), "data/event_summaries.json"),
    ]
    
    # 複製核心文件
    for src, dst_rel in core_files:
        dst = os.path.join(dist_dir, dst_rel)
        if os.path.exists(src):
            print(f"[Copy] {os.path.basename(src)} -> {dst_rel}")
            shutil.copy2(src, dst)
        else:
            if "event_summaries.json" in src:
                print(f"[Warn] 可選的活動摘要文件 {os.path.basename(src)} 未找到，跳過拷貝。")
                continue
            print(f"[Error] 找不到核心文件: {src}", file=sys.stderr)
            sys.exit(1)
            
    # 複製 story/ 目錄下的所有對白 JSON
    story_src_dir = os.path.join(dashboard_dir, "story")
    story_dst_dir = os.path.join(dist_dir, "story")
    
    if os.path.exists(story_src_dir):
        json_count = 0
        for item in os.listdir(story_src_dir):
            if item.endswith(".json"):
                shutil.copy2(os.path.join(story_src_dir, item), os.path.join(story_dst_dir, item))
                json_count += 1
        print(f"[Copy] 成功複製了 {json_count} 個對白 JSON 檔案")
    else:
        print("[Warning] 找不到對白 JSON 資料夾 (story/)")
        
    # 從 tracked_characters.json 動態讀取已追蹤角色，複製其頭像與立繪
    tracked_path = os.path.join(dashboard_dir, "data", "tracked_characters.json")
    if os.path.exists(tracked_path):
        with open(tracked_path, 'r', encoding='utf-8') as f:
            tracked = json.load(f)
        for char in tracked.get("characters", []):
            char_name = char.get("name", f"unit_{char['unit_id']}")
            # 複製頭像
            for icon_id in char.get("icon_ids", []):
                src = os.path.join(dashboard_dir, "icon", "unit", f"unit_icon_{icon_id}.webp")
                dst = os.path.join(dist_dir, "icon", "unit", f"unit_icon_{icon_id}.webp")
                if os.path.exists(src):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    print(f"[Copy] 複製 {char_name} 頭像 unit_icon_{icon_id}.webp 成功")
            # 複製立繪大圖
            for card_id in char.get("card_ids", []):
                src = os.path.join(dashboard_dir, "card", "full", f"card_full_{card_id}.webp")
                dst = os.path.join(dist_dir, "card", "full", f"card_full_{card_id}.webp")
                if os.path.exists(src):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    print(f"[Copy] 複製 {char_name} 立繪大圖 card_full_{card_id}.webp 成功")
    else:
        print("[Warn] 找不到 tracked_characters.json，跳過角色素材複製")
            
    print("[Success] 打包部署封裝完成！")
    print(f"[Info] 您現在可以直接將 {dist_dir} 資料夾內容部署到 GitHub Pages、Vercel 或您的任何 Web 伺服器上。")

if __name__ == "__main__":
    main()
