# -*- coding: utf-8 -*-
import os
import shutil
import sys

# 確保輸出編碼為 utf-8 以免 Windows 終端崩潰
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
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
    
    # 清理舊的輸出目錄
    if os.path.exists(dist_dir):
        print("[Info] 清理舊的 dist_story_map/ 目錄...")
        try:
            shutil.rmtree(dist_dir)
        except PermissionError:
            print("[Warning] 無法完全刪除舊目錄（可能檔案被佔用），將直接進行覆寫覆蓋...")
        
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
        (os.path.join(dashboard_dir, "data", "chapters.json"), "data/chapters.json"),
        (os.path.join(dashboard_dir, "data", "extra_events.json"), "data/extra_events.json"),
        (os.path.join(dashboard_dir, "data", "npc_avatars.json"), "data/npc_avatars.json"),
        (os.path.join(dashboard_dir, "data", "real_name_mapping.json"), "data/real_name_mapping.json"),
    ]
    
    # 複製核心文件
    for src, dst_rel in core_files:
        dst = os.path.join(dist_dir, dst_rel)
        if os.path.exists(src):
            print(f"[Copy] {os.path.basename(src)} -> {dst_rel}")
            shutil.copy2(src, dst)
        else:
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
        
    # 複製 icon/ 目錄下的所有本地素材 (包括已轉換的 png/webp)
    icon_src_dir = os.path.join(project_root, "dashboard", "icon")
    icon_dst_dir = os.path.join(dist_dir, "icon")
    if os.path.exists(icon_src_dir):
        print("[Copy] 開始複製本地 icon 目錄...")
        try:
            if os.path.exists(icon_dst_dir):
                shutil.rmtree(icon_dst_dir)
            shutil.copytree(icon_src_dir, icon_dst_dir)
            print("[Copy] 本地 icon 目錄複製成功！")
        except Exception as e:
            print(f"[Warning] 複製本地 icon 目錄失敗: {e}")
            
    print("[Success] 打包部署封裝完成！")
    print(f"[Info] 您現在可以直接將 {dist_dir} 資料夾內容部署到 GitHub Pages、Vercel 或您的任何 Web 伺服器上。")

if __name__ == "__main__":
    main()
