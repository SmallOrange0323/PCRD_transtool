# -*- coding: utf-8 -*-
import sqlite3
import os
import sys
import json
import urllib.request
import urllib.parse
import base64
from struct import unpack
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

# 配置 UnityPy
import UnityPy
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "dashboard", "redive_tw.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "dashboard", "story")
SOUND_DIR = os.path.join(BASE_DIR, "dashboard", "sound", "story_vo")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SOUND_DIR, exist_ok=True)

HEADER = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ==========================================
# 步驟一：台服劇情解密還原算法
# ==========================================
def deserialize_command(data):
    index = data[0]
    args = []
    if len(data) > 1:
        args = data[1:]
    array = []
    for arg in args:
        array2 = []
        for byte in arg:
            if byte > 127:
                array2.append(255 - byte)
            else:
                array2.append(byte)
        try:
            str_ = base64.b64decode(bytearray(array2))
            array.append(str_.decode('cp950', errors='ignore'))
        except Exception:
            array.append("")
    return index, array

def deserialize_story_raw(bytes_):
    commands = []
    fs = 0
    raw_commands = []
    i = 2
    while i < len(bytes_):
        args = []
        if fs + 2 > len(bytes_):
            break
        index = int(unpack(">H", bytes_[fs : fs + 2])[0])
        fs += 2
        args.append(index)
        num = i
        while True:
            if fs + 4 > len(bytes_):
                break
            length = int(unpack(">l", bytes_[fs : fs + 4])[0])
            fs += 4
            if length == 0:
                break
            if fs + length > len(bytes_):
                break
            array = bytes_[fs : fs + length]
            fs += length
            args.append(array)
            num += 4 + length
        i = num + 4
        raw_commands.append(args)
        i += 2
    for raw_command in raw_commands:
        if len(raw_command) > 1:
            commands.append(deserialize_command(raw_command))
    return commands

def get_hash_for_story(ver, target_id):
    url = f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/AssetBundles/Android/manifest/storydata2_assetmanifest"
    req = urllib.request.Request(url, headers=HEADER)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            lines = response.read().decode('utf-8').splitlines()
            for line in lines:
                parts = line.strip().split(",")
                if len(parts) >= 3:
                    path, _, new_hash = parts[0], parts[1], parts[2]
                    if f"storydata_{target_id}.unity3d" in path:
                        return new_hash
    except Exception as e:
        print(f"[ERROR] 無法獲取故事清單: {e}")
    return None

def download_and_parse_story_tw(ver, story_id):
    output_path = os.path.join(OUTPUT_DIR, f"{story_id}.json")
    print(f"\n[台版 CDN 下載解密] 正在獲取故事 {story_id}...")
    
    new_hash = get_hash_for_story(ver, story_id)
    if not new_hash:
        print(f"  ❌ 未能在台版清單中找到故事 {story_id} 的 Hash")
        return None
        
    url = f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{new_hash[:2]}/{new_hash}"
    req = urllib.request.Request(url, headers=HEADER)
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            bundle_data = response.read()
            
        bundle = UnityPy.load(bundle_data)
        dialogues = []
        
        for obj in bundle.objects:
            if obj.type == obj.type.TextAsset:
                data = obj.read()
                if hasattr(data, "script") and data.script:
                    script = data.script
                elif hasattr(data, "m_Script") and data.m_Script:
                    script = data.m_Script
                else:
                    continue
                if isinstance(script, str):
                    script = bytes(script, "utf-8", "surrogateescape")
                
                commands = deserialize_story_raw(script)
                
                current_voice = None
                for idx, args in commands:
                    if idx == 12 and len(args) >= 1:
                        # 語音指令
                        current_voice = args[0]
                    elif idx == 6 and len(args) >= 2:
                        # 對話指令
                        speaker = args[0]
                        words = args[1]
                        
                        # 繁中化微調：可可蘿習慣稱呼主公大人
                        if speaker == "コッコロ" or speaker == "可可蘿":
                            speaker = "可可蘿"
                            words = words.replace("主人", "主公大人")
                        elif speaker == "ペコリーヌ":
                            speaker = "佩可莉姆"
                        elif speaker == "キャル":
                            speaker = "凱留"
                        elif speaker == "ユウキ":
                            speaker = "祐樹"
                            
                        dialogues.append({
                            "name": speaker,
                            "words": words,
                            "voice": current_voice
                        })
                        current_voice = None # 消耗掉該語音
                        
        if dialogues:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(dialogues, f, ensure_ascii=False, indent=4)
            print(f"  - 🎉 成功下載並解密原生繁中台詞，共 {len(dialogues)} 句！")
            return dialogues
    except Exception as e:
        print(f"  - ❌ 解密失敗: {e}")
    return None

# ==========================================
# 步驟二：多線程語音下載器
# ==========================================
def download_single_voice(args):
    story_id, voice_id = args
    if not voice_id:
        return False
        
    local_path = os.path.join(SOUND_DIR, f"{voice_id}.m4a")
    if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
        # 已存在則跳過
        return "skip"
        
    url = f"https://prcn-sound.estertion.win/story_vo/{story_id}/{voice_id}.m4a"
    req = urllib.request.Request(url, headers=HEADER)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            with open(local_path, "wb") as f:
                f.write(response.read())
        return "downloaded"
    except Exception as e:
        return f"fail: {e}"

def download_voices_for_stories(story_voices_map):
    tasks = []
    for story_id, voices in story_voices_map.items():
        for voice_id in voices:
            tasks.append((story_id, voice_id))
            
    total_tasks = len(tasks)
    print(f"\n[語音下載] 準備為 4 話故事下載總共 {total_tasks} 條語音檔案...")
    
    downloaded = 0
    skipped = 0
    failed = 0
    
    # 使用 16 個線程進行極速併行下載
    with ThreadPoolExecutor(max_workers=16) as executor:
        results = executor.map(download_single_voice, tasks)
        
        for idx, res in enumerate(results, 1):
            if res == "downloaded":
                downloaded += 1
            elif res == "skip":
                skipped += 1
            else:
                failed += 1
                
            if idx % 50 == 0 or idx == total_tasks:
                print(f"  - 下載進度: {idx}/{total_tasks} (下載: {downloaded}, 跳過: {skipped}, 失敗: {failed})", end="\r", flush=True)
                
    print(f"\n[SUCCESS] 語音下載任務結束！下載: {downloaded} 筆, 已存在跳過: {skipped} 筆, 失敗: {failed} 筆")

def main():
    if not os.path.exists(DB_PATH):
        print(f"錯誤：找不到台服資料庫 {DB_PATH}")
        return

    # 從歷史紀錄中獲取最新的 TruthVersion
    history_file = os.path.join(BASE_DIR, "dashboard", "versions", "version_history.json")
    ver = "00500024" # Fallback
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                ver = json.load(f).get("last_version", "00500024")
        except:
            pass

    print(f"[INFO] 當前台版 TruthVersion: {ver}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # 啟用 Row Factory
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cur.fetchall()]

    peco_profile = {}
    skills_data = {}
    chara_stories = []

    print("[INFO] 正在解析台版資料庫以獲取佩可（阿斯特萊亞）相關數據...")

    # 1. 角色個人資料
    profile_table = "unit_profile" if "unit_profile" in tables else "v1_407dd5506ad0eed60a88211bc753716b511e8a4d02af4a00a84bad0073ab8aab"
    id_col = "unit_id" if "unit_profile" in tables else "8a410e2431500fa6ba8143ce5a092bb39fcaacbd0d4b64396caf7d1960a83970"
    if profile_table in tables:
        cur.execute(f"PRAGMA table_info(\"{profile_table}\")")
        profile_cols = [c[1] for c in cur.fetchall()]
        
        def get_profile_val(row_obj, col_name, physical_idx):
            c_name = col_name if col_name in profile_cols else profile_cols[physical_idx]
            return row_obj[c_name]
            
        cur.execute(f"SELECT * FROM \"{profile_table}\" WHERE \"{id_col}\" = 138301")
        row = cur.fetchone()
        if row:
            peco_profile = {
                "聲優": get_profile_val(row, "voice_actor", 0),
                "年齡": get_profile_val(row, "age", 1),
                "名字": get_profile_val(row, "unit_name", 2),
                "種族": get_profile_val(row, "race", 3),
                "身高": get_profile_val(row, "height", 4),
                "體重": get_profile_val(row, "weight", 5),
                "公會": get_profile_val(row, "guild", 6),
                "興趣": get_profile_val(row, "favorite", 7),
                "介紹": get_profile_val(row, "comment", 8),
                "生日月": get_profile_val(row, "birth_month", 9),
                "自我介紹": get_profile_val(row, "catch_copy", 10),
                "血型": get_profile_val(row, "blood_type", 11),
                "生日日": get_profile_val(row, "birth_day", 13),
                "角色ID": get_profile_val(row, "unit_id", 14)
            }

    # 2. 技能說明
    skill_table = None
    skill_id_col = None
    for table in tables:
        try:
            cur.execute(f"PRAGMA table_info(\"{table}\")")
            cols = [col[1] for col in cur.fetchall()]
            for col in cols:
                cur.execute(f"SELECT COUNT(*) FROM \"{table}\" WHERE \"{col}\" = 1383001")
                if cur.fetchone()[0] > 0:
                    skill_table = table
                    skill_id_col = col
                    break
            if skill_table:
                break
        except Exception:
            pass

    if skill_table and skill_id_col:
        for sk_id, sk_name in [("UB", 1383001), ("Skill 1", 1383002), ("Skill 2", 1383003)]:
            cur.execute(f"SELECT * FROM \"{skill_table}\" WHERE \"{skill_id_col}\" = ?", (sk_name,))
            row = cur.fetchone()
            if row:
                texts = [val for val in row if isinstance(val, str)]
                skills_data[sk_id] = {
                    "ID": sk_name,
                    "名稱": texts[0] if len(texts) > 0 else "未知",
                    "說明": texts[1].replace("\\n", "\n") if len(texts) > 1 else "無說明"
                }

    # 3. 獲取個人劇情清單
    story_table = "story_detail" if "story_detail" in tables else "v1_a565dbd80f5784a9aa6cd9c9b2c449c14071474fa92cfe934d17cd8f906e7b12"
    story_id_col = "story_id" if "story_detail" in tables else "b06875a2a55de26ca5848c357427726c0671224623c9bfc3030706f14c95cb34"
    if story_table in tables:
        cur.execute(f"PRAGMA table_info(\"{story_table}\")")
        story_cols = [c[1] for c in cur.fetchall()]
        
        title_col = "title" if "title" in story_cols else story_cols[19]
        sub_title_col = "sub_title" if "sub_title" in story_cols else story_cols[5]
        
        cur.execute(f"SELECT * FROM \"{story_table}\" WHERE \"{story_id_col}\" >= 1383000 AND \"{story_id_col}\" < 1383100 ORDER BY \"{story_id_col}\" ASC")
        rows = cur.fetchall()
        for row in rows:
            chara_stories.append({
                "故事ID": row[story_id_col],
                "標題": row[title_col],
                "副標題": row[sub_title_col]
            })

    conn.close()

    # 下載劇情文字 JSON
    story_dialogues_map = {}
    story_voices_map = {}
    for story in chara_stories:
        story_id = story["故事ID"]
        dialogues = download_and_parse_story_tw(ver, story_id)
        if dialogues:
            story_dialogues_map[story_id] = dialogues
            # 收集該話所有包含語音的 ID
            story_voices_map[story_id] = [d["voice"] for d in dialogues if d.get("voice")]

    # 4. 下載個人劇情語音
    download_voices_for_stories(story_voices_map)

    # 5. 寫入報告
    report_path = os.path.join(BASE_DIR, "peco_astraea_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 貪吃佩可（阿斯特萊亞）原生繁中數據與劇情報告\n\n")
        f.write("## 👤 角色基本資料\n\n")
        if peco_profile:
            f.write("| 屬性 | 資料 |\n| --- | --- |\n")
            for k, v in peco_profile.items():
                f.write(f"| {k} | {v} |\n")
        
        f.write("\n## ⚔️ 角色技能數據 (原生繁中)\n\n")
        for sk_id, data in skills_data.items():
            f.write(f"### {sk_id}：{data['名稱']} (ID: `{data['ID']}`)\n")
            f.write(f"```text\n{data['說明']}\n```\n\n")

        f.write("## 🎬 個人劇情大綱\n\n")
        for story in chara_stories:
            f.write(f"- **故事 ID `{story['故事ID']}`**: {story['標題']} — *{story['副標題']}*\n")
            
        f.write("\n## 💬 個人劇情對話文本擷取 (台版 CDN 解密原生繁中)\n\n")
        for story in chara_stories:
            story_id = story["故事ID"]
            f.write(f"### 📖 第 {story_id - 1383000} 話：{story['標題']}\n\n")
            dialogues = story_dialogues_map.get(story_id)
            if dialogues:
                f.write("| 說話者 | 台版官方原汁原味對白 | 語音檔 |\n| --- | --- | --- |\n")
                for d in dialogues[:20]: # 展示前 20 句
                    voice_str = f"`{d['voice']}.m4a`" if d.get("voice") else "*無語音*"
                    f.write(f"| **{d['name']}** | {d['words']} | {voice_str} |\n")
                if len(dialogues) > 20:
                    f.write(f"| ... | *(後續還有 {len(dialogues) - 20} 句對白)* | |\n")
            else:
                f.write("*未成功獲取或無對白。*\n")
            f.write("\n")

    print(f"\n🎉 原生繁中數據與語音報告生成成功！已儲存至: {report_path}")

if __name__ == "__main__":
    main()
