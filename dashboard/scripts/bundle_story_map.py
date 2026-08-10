# -*- coding: utf-8 -*-
import json
import os
import shutil
import sys

# 確保輸出編碼為 utf-8 以免 Windows 終端崩潰
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
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
        (os.path.join(dashboard_dir, "data", "main_story_chapter_summaries.json"), "data/main_story_chapter_summaries.json"),
    ]
    
    # 複製核心文件
    for src, dst_rel in core_files:
        dst = os.path.join(dist_dir, dst_rel)
        if os.path.exists(src):
            if os.path.exists(dst) and os.path.getsize(src) == os.path.getsize(dst):
                print(f"[Skip] {os.path.basename(src)} -> {dst_rel} (大小相同)")
            else:
                print(f"[Copy] {os.path.basename(src)} -> {dst_rel}")
                try:
                    shutil.copy2(src, dst)
                except Exception as e:
                    print(f"[Warn] Copy {src} failed: {e}", file=sys.stderr)
        else:
            if "event_summaries.json" in src:
                print(f"[Warn] 可選的活動摘要文件 {os.path.basename(src)} 未找到，跳過拷貝。")
                continue
            print(f"[Error] 找不到核心文件: {src}", file=sys.stderr)
            sys.exit(1)

    # 自動生成資料庫大小快取資訊檔，防止 GitHub Pages 不支援 HEAD 請求導致的本地 Cache 不更新 Bug
    # 同時注入以時間為準的 db_version 戳記以實現全自動的 IndexedDB 緩存清空
    import datetime
    db_info = {
        "db_version": datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    }
    for region in ['tw', 'jp']:
        db_file = os.path.join(dashboard_dir, f"redive_{region}.db")
        if os.path.exists(db_file):
            db_info[f"{region}_size"] = os.path.getsize(db_file)
        else:
            db_info[f"{region}_size"] = 0
            
    db_info_dst = os.path.join(dist_dir, "data", "db_info.json")
    with open(db_info_dst, 'w', encoding='utf-8') as f:
        json.dump(db_info, f, ensure_ascii=False, indent=2)
    print(f"[Info] 自動寫入資料庫大小資訊檔: {db_info_dst} -> {db_info}")

            
    # 複製 story/ 目錄下的所有對白 JSON
    story_src_dir = os.path.join(dashboard_dir, "story")
    story_dst_dir = os.path.join(dist_dir, "story")
    
    if os.path.exists(story_src_dir):
        os.makedirs(story_dst_dir, exist_ok=True)
        json_count = 0
        for item in os.listdir(story_src_dir):
            if item.endswith(".json"):
                try:
                    s_path = os.path.join(story_src_dir, item)
                    d_path = os.path.join(story_dst_dir, item)
                    if os.path.exists(d_path) and os.path.getsize(s_path) == os.path.getsize(d_path):
                        continue
                    shutil.copy2(s_path, d_path)
                    json_count += 1
                except Exception:
                    pass
        print(f"[Copy] 成功複製了 {json_count} 個新對白 JSON 檔案")
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
                    try:
                        if os.path.exists(dst) and os.path.getsize(src) == os.path.getsize(dst):
                            continue
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)
                        print(f"[Copy] 複製 {char_name} 頭像 unit_icon_{icon_id}.webp 成功")
                    except Exception:
                        pass
            # 複製立繪大圖
            for card_id in char.get("card_ids", []):
                src = os.path.join(dashboard_dir, "card", "full", f"card_full_{card_id}.webp")
                dst = os.path.join(dist_dir, "card", "full", f"card_full_{card_id}.webp")
                if os.path.exists(src):
                    try:
                        if os.path.exists(dst) and os.path.getsize(src) == os.path.getsize(dst):
                            continue
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)
                        print(f"[Copy] 複製 {char_name} 立繪大圖 card_full_{card_id}.webp 成功")
                    except Exception:
                        pass
            # 複製劇情劇照 (Still)
            char_prefix = str(char["unit_id"])[:4]
            still_src_dir = os.path.join(dashboard_dir, "still", "story")
            still_dst_dir = os.path.join(dist_dir, "still", "story")
            if os.path.exists(still_src_dir):
                for item in os.listdir(still_src_dir):
                    if item.startswith(char_prefix) and item.endswith(".webp"):
                        s_p = os.path.join(still_src_dir, item)
                        d_p = os.path.join(still_dst_dir, item)
                        try:
                            if os.path.exists(d_p) and os.path.getsize(s_p) == os.path.getsize(d_p):
                                continue
                            os.makedirs(still_dst_dir, exist_ok=True)
                            shutil.copy2(s_p, d_p)
                            print(f"[Copy] 複製 {char_name} 劇情劇照 {item} 成功")
                        except Exception:
                            pass
    else:
        print("[Warn] 找不到 tracked_characters.json，跳過角色素材複製")

    # ── 動態複製所有 NPC 頭像 ──
    icon_src_dir = os.path.join(dashboard_dir, "icon", "unit")
    icon_dst_dir = os.path.join(dist_dir, "icon", "unit")
    if os.path.exists(icon_src_dir):
        os.makedirs(icon_dst_dir, exist_ok=True)
        npc_icon_count = 0
        for item in os.listdir(icon_src_dir):
            name_part, ext = os.path.splitext(item)
            if ext not in [".png", ".webp"]:
                continue
            clean_id_str = name_part.replace("unit_icon_", "")
            if clean_id_str.isdigit():
                val = int(clean_id_str)
                is_npc = (190000 <= val <= 199999) or (val in [107411, 107412, 107431])
                if is_npc:
                    s_p = os.path.join(icon_src_dir, item)
                    d_p = os.path.join(icon_dst_dir, item)
                    try:
                        if not (os.path.exists(d_p) and os.path.getsize(s_p) == os.path.getsize(d_p)):
                            shutil.copy2(s_p, d_p)
                            npc_icon_count += 1
                        
                        if val < 190000:
                            base_id = (val // 100) * 100
                            norm_name = f"{base_id + 31}{ext}"
                            norm_dst = os.path.join(icon_dst_dir, norm_name)
                            if not (os.path.exists(norm_dst) and os.path.getsize(s_p) == os.path.getsize(norm_dst)):
                                shutil.copy2(s_p, norm_dst)
                                npc_icon_count += 1
                    except Exception:
                        pass
        print(f"[Copy] 成功複製與規整了 {npc_icon_count} 個新/更新 NPC 頭像檔案")

    # 動態複製所有對白語音 M4A 檔案（只要本地有就一併同步，不設限制）
    sound_src_dir = os.path.join(dashboard_dir, "sound", "story_vo")
    sound_dst_dir = os.path.join(dist_dir, "sound", "story_vo")
    
    if os.path.exists(sound_src_dir):
        os.makedirs(sound_dst_dir, exist_ok=True)
        copied_voices = 0
        for item in os.listdir(sound_src_dir):
            if item.endswith(".m4a"):
                try:
                    src_file = os.path.join(sound_src_dir, item)
                    dst_file = os.path.join(sound_dst_dir, item)
                    if os.path.exists(dst_file) and os.path.getsize(src_file) == os.path.getsize(dst_file):
                        continue
                    shutil.copy2(src_file, dst_file)
                    copied_voices += 1
                except Exception:
                    pass
        print(f"[Copy] 成功複製了 {copied_voices} 個新劇情對白語音 M4A 檔案")

    # 動態複製所有劇情劇照 (still/story)
    still_story_src = os.path.join(dashboard_dir, "still", "story")
    still_story_dst = os.path.join(dist_dir, "still", "story")
    if os.path.exists(still_story_src):
        os.makedirs(still_story_dst, exist_ok=True)
        copied_stills = 0
        for item in os.listdir(still_story_src):
            if item.endswith(".webp"):
                try:
                    src_file = os.path.join(still_story_src, item)
                    dst_file = os.path.join(still_story_dst, item)
                    if os.path.exists(dst_file) and os.path.getsize(src_file) == os.path.getsize(dst_file):
                        continue
                    shutil.copy2(src_file, dst_file)
                    copied_stills += 1
                except Exception:
                    pass
        print(f"[Copy] 成功複製了 {copied_stills} 個新劇情故事劇照 WebP 檔案")

    # 複製所有背景圖 (still/bg) 與劇情 CG (still/scenario)
    for sub in ["bg", "scenario"]:
        src_sub = os.path.join(dashboard_dir, "still", sub)
        dst_sub = os.path.join(dist_dir, "still", sub)
        if os.path.exists(src_sub):
            os.makedirs(dst_sub, exist_ok=True)
            img_count = 0
            for item in os.listdir(src_sub):
                if item.endswith(".webp"):
                    try:
                        src_file = os.path.join(src_sub, item)
                        dst_file = os.path.join(dst_sub, item)
                        if os.path.exists(dst_file) and os.path.getsize(src_file) == os.path.getsize(dst_file):
                            continue
                        shutil.copy2(src_file, dst_file)
                        img_count += 1
                    except Exception:
                        pass
            print(f"[Copy] 成功複製了 {img_count} 個新 still/{sub} WebP 圖片")

    # --- [自動內嵌快取破壞機制] ---
    # 將 db.js 與 chapter-data.js 直接 inline 嵌入到 dist_story_map/index.html 中
    index_html_path = os.path.join(dist_dir, "index.html")
    db_js_path = os.path.join(dashboard_dir, "db.js")
    chapter_data_js_path = os.path.join(dashboard_dir, "chapter-data.js")

    if os.path.exists(index_html_path) and os.path.exists(db_js_path) and os.path.exists(chapter_data_js_path):
        import re
        print("[Info] 正在將 db.js 與 chapter-data.js 內嵌至 index.html 以避免 CDN 快取遺留...")
        
        with open(db_js_path, 'r', encoding='utf-8') as f:
            db_js_code = f.read()
        with open(chapter_data_js_path, 'r', encoding='utf-8') as f:
            chapter_data_js_code = f.read()
        with open(index_html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # 替換 db.js script tag
        html_content = re.sub(
            r'<script src="db\.js(?:\?v=[^"]*)?"></script>',
            lambda m: f'<script>\n// === db.js INLINED ===\n{db_js_code}\n// === END db.js ===\n</script>',
            html_content
        )
        # 替換 chapter-data.js script tag
        html_content = re.sub(
            r'<script src="chapter-data\.js(?:\?v=[^"]*)?"></script>',
            lambda m: f'<script>\n// === chapter-data.js INLINED ===\n{chapter_data_js_code}\n// === END chapter-data.js ===\n</script>',
            html_content
        )

        with open(index_html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"[Success] 內嵌完成！最終 index.html 大小: {os.path.getsize(index_html_path)} bytes")
    else:
        print("[Error] 內嵌失敗，找不到必要的 HTML 或 JS 檔案", file=sys.stderr)
        sys.exit(1)
            
    print("[Success] 打包部署封裝完成！")
    print(f"[Info] 您現在可以直接將 {dist_dir} 資料夾內容部署到 GitHub Pages、Vercel 或您的任何 Web 伺服器上。")

if __name__ == "__main__":
    main()
