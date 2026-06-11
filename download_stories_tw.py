import os
import sys
import json
import sqlite3
import urllib.request
import urllib.parse
import hashlib
import UnityPy

# 配置 UnityPy 的 Fallback Unity 版本，防止資源解包出錯
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
if hasattr(UnityPy, 'environment') and hasattr(UnityPy.environment, 'Environment'):
    UnityPy.environment.Environment.version_engine = '2021.3.20f1'
elif hasattr(UnityPy.helpers, 'ArchiveStorageManager'):
    # 部分 UnityPy 版本的 fallback 設定
    pass


# 強制使用 UTF-8 輸出，避免 Windows 終端機編碼問題
sys.stdout.reconfigure(encoding='utf-8')

# 使用與專案目錄對齊的相對路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dashboard", "redive_tw.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "dashboard", "story")

HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

# 🎬 故事反序列化工具 (實作自 CyGames 序列化規範)
import base64
from enum import Enum
from struct import unpack

class CommandId(Enum):
    NONE = -1
    TITLE = 0
    OUTLINE = 1
    VISIBLE = 2
    FACE = 3
    FOCUS = 4
    BACKGROUND = 5
    PRINT = 6
    TAG = 7
    GOTO = 8
    BGM = 9
    TOUCH = 10
    CHOICE = 11
    VO = 12
    WAIT = 13
    IN_L = 14
    IN_R = 15
    OUT_L = 16
    OUT_R = 17
    FADEIN = 18
    FADEOUT = 19
    IN_FLOAT = 20
    OUT_FLOAT = 21
    JUMP = 22
    SHAKE = 23
    POP = 24
    NOD = 25
    SE = 26
    BLACK_OUT = 27
    BLACK_IN = 28
    WHITE_OUT = 29
    WHITE_IN = 30
    TRANSITION = 31
    SITUATION = 32
    COLOR_FADEIN = 33
    FLASH = 34
    SHAKE_TEXT = 35
    TEXT_SIZE = 36
    SHAKE_SCREEN = 37
    DOUBLE = 38
    SCALE = 39
    TITLE_TELOP = 40
    WINDOW_VISIBLE = 41
    LOG = 42
    NOVOICE = 43
    CHANGE = 44
    FADEOUT_ALL = 45
    MOVIE = 46
    MOVIE_STAY = 47
    BATTLE = 48
    STILL = 49
    BUSTUP = 50
    ENV = 51
    TUTORIAL_REWARD = 52
    NAME_EDIT = 53
    EFFECT = 54
    EFFECT_DELETE = 55
    EYE_OPEN = 56
    MOUTH_OPEN = 57
    AUTO_END = 58
    EMOTION = 59
    EMOTION_END = 60
    ENV_STOP = 61
    BGM_PAUSE = 62
    BGM_RESUME = 63
    BGM_VOLUME_CHANGE = 64
    ENV_RESUME = 65
    ENV_VOLUME = 66
    SE_PAUSE = 67
    CHARA_FULL = 68
    SWAY = 69
    BACKGROUND_COLOR = 70
    PAN = 71
    STILL_UNIT = 72
    SLIDE_CHARA = 73
    SHAKE_SCREEN_ONCE = 74
    TRANSITION_RESUME = 75
    SHAKE_LOOP = 76
    SHAKE_DELETE = 77
    UNFACE = 78
    WAIT_TOKEN = 79
    EFFECT_ENV = 80
    BRIGHT_CHANGE = 81
    CHARA_SHADOW = 82
    UI_VISIBLE = 83
    FADEIN_ALL = 84
    CHANGE_WINDOW = 85
    BG_PAN = 86
    STILL_MOVE = 87
    STILL_NORMALIZE = 88
    VOICE_EFFECT = 89
    TRIAL_END = 90
    SE_EFFECT = 91
    CHARACTER_UP_DOWN = 92
    BG_CAMERA_ZOOM = 93
    BACKGROUND_SPLIT = 94
    CAMERA_ZOOM = 95
    SPLIT_SLIDE = 96
    BGM_TRANSITION = 97
    SHAKE_ANIME = 98
    INSERT_STORY = 99
    PLACE = 100
    IGNORE_BGM = 101
    MULTI_LIPSYNC = 102
    JINGLE = 103
    TOUCH_TO_START = 104
    EVENT_ADV_MOVE_HORIZONTAL = 105
    BG_PAN_X = 106
    BACKGROUND_BLUR = 107
    SEASONAL_REWARD = 108
    MINI_GAME = 109
    MAX = 110
    UNKNOWN = 112

def deserialize_command(data) -> tuple[CommandId, list[str]]:
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
            array.append(str_.decode('utf-8', errors='ignore'))
        except Exception:
            # 容錯處理，避免非字串解碼報錯
            array.append("")
    
    # 避免 CommandId 溢出報錯
    try:
        cmd_id = CommandId(index)
    except ValueError:
        cmd_id = CommandId.NONE
    return (cmd_id, array)

def deserialize_story_raw(bytes_: bytes) -> list[tuple[CommandId, list[str]]]:
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

def clean_text(text: str) -> str:
    replace_pairs = (
        ("\\n", "\n"),
        ("{0}", "{player}"),
        ('\\"', '"'),
    )
    for pair in replace_pairs:
        text = text.replace(*pair)
    return text

def extract_story_dialogues(bytes_data):
    commands = deserialize_story_raw(bytes_data)
    dialogues = []
    current_unit_id = None
    current_voice = None
    
    for command_id, args in commands:
        if command_id in (CommandId.FOCUS, CommandId.FACE, CommandId.BUSTUP, CommandId.CHARA_FULL) and len(args) >= 1:
            val = args[0]
            if val.isdigit():
                current_unit_id = int(val)
        elif command_id == CommandId.VO and len(args) >= 1:
            current_voice = args[0]
        elif command_id == CommandId.BACKGROUND and len(args) >= 1:
            dialogues.append({
                "type": "background",
                "background": args[0]
            })
        elif command_id == CommandId.STILL and len(args) >= 1:
            dialogues.append({
                "type": "still",
                "still": args[0]
            })
        elif command_id == CommandId.PRINT and len(args) >= 2:
            speaker = args[0]
            words = clean_text(args[1])
            diag = {
                "type": "dialogue",
                "name": speaker,
                "words": words
            }
            if current_unit_id:
                diag["unit_id"] = current_unit_id
            if current_voice:
                diag["voice"] = current_voice
                current_voice = None # 一次性消費
            dialogues.append(diag)
            
    return dialogues

# 📡 CDN 下載與解析邏輯
def get_truth_version():
    print("[INFO] 正在連線 wthee.xyz 獲取台服最新資料庫版本 (TruthVersion)...")
    url = "https://wthee.xyz/pcr/api/v1/db/info/v2"
    payload = json.dumps({"regionCode": "tw"}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            if res_data.get("status") == 0 and "data" in res_data:
                ver = res_data["data"]["truthVersion"]
                print(f"[SUCCESS] 取得台服最新 TruthVersion: {ver}")
                return ver
    except Exception as e:
        print(f"[ERROR] 連線 wthee.xyz 失敗 ({e})，使用預設備份版本")
    return "00500012"  # 備份防禦性版本

def download_story_manifest(truth_version):
    print(f"[INFO] 正在獲取 So-net CDN 劇情資源清單 (manifest)...")
    url = f"https://img-pc.so-net.tw/dl/Resources/{truth_version}/Jpn/AssetBundles/Android/manifest/storydata2_assetmanifest"
    req = urllib.request.Request(url, headers=HEADER)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            lines = response.read().decode('utf-8').splitlines()
            print(f"[SUCCESS] 成功載入 {len(lines)} 筆劇情資源雜湊！")
            return lines
    except Exception as e:
        print(f"[ERROR] 無法獲取資源清單 ({e})")
        return []

def parse_manifest(lines):
    # 格式: path, old_hash, new_hash, group, size, ...
    # 建立 a/storydata_XXXXXXX.unity3d -> new_hash 映射表
    mapping = {}
    for line in lines:
        parts = line.strip().split(",")
        if len(parts) >= 3:
            path, _, new_hash = parts[0], parts[1], parts[2]
            mapping[path] = new_hash
    return mapping

def download_and_extract_story(story_id, new_hash, truth_version):
    # 1. 組裝資源下載網址
    url = f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{new_hash[:2]}/{new_hash}"
    req = urllib.request.Request(url, headers=HEADER)
    
    try:
        # 2. 下載 Unity3D 資源檔
        with urllib.request.urlopen(req, timeout=15) as response:
            bundle_data = response.read()
            
        # 3. 使用 UnityPy 解包取出 TextAsset
        bundle = UnityPy.load(bundle_data)
        text_asset_data = None
        for obj in bundle.objects:
            if obj.type == obj.type.TextAsset:
                data = obj.read()
                # 兼容不同的 UnityPy 版本欄位名稱
                if hasattr(data, "script") and data.script:
                    text_asset_data = data.script
                elif hasattr(data, "m_Script") and data.m_Script:
                    text_asset_data = data.m_Script
                
                # 如果是字串格式，轉換回 bytes
                if isinstance(text_asset_data, str):
                    text_asset_data = bytes(text_asset_data, "utf-8", "surrogateescape")
                break

                
        if not text_asset_data:
            print(" ⚠️ 資源包中未包含 TextAsset。")
            return False
            
        # 4. 反序列化成我們需要的結構
        dialogues = extract_story_dialogues(text_asset_data)
        
        # 5. 輸出至目標目錄
        output_path = os.path.join(OUTPUT_DIR, f"{story_id}.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(dialogues, f, ensure_ascii=False, indent=4)
            
        return True
    except Exception as e:
        print(f" ⚠️ 下載或解析失敗 ({e})")
        return False

def get_all_story_ids():
    if not os.path.exists(DB_PATH):
        print(f"[WARNING] 找不到 SQLite 資料庫：{DB_PATH}。")
        return []
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. 角色個人劇情 (1000000 ~ 1999999)
    cursor.execute("SELECT story_id FROM story_detail WHERE story_id >= 1000000 AND story_id < 2000000 ORDER BY story_id ASC")
    chara_story_ids = [row[0] for row in cursor.fetchall()]

    # 2. 主線與幕間 (2000000 ~ 4999999，已包含 3xxxxxx 公會與 4xxxxxx 系統劇情)
    cursor.execute("SELECT story_id FROM story_detail WHERE story_id >= 2000000 AND story_id < 5000000 ORDER BY story_id ASC")
    main_story_ids = [row[0] for row in cursor.fetchall()]

    # 3. 露娜塔劇情 (7xxxxxx) - 來自 tower_schedule 的 opening_story_id
    cursor.execute("SELECT DISTINCT opening_story_id FROM tower_schedule WHERE opening_story_id > 0 ORDER BY opening_story_id ASC")
    tower_story_ids = [row[0] for row in cursor.fetchall()]
    
    # 4. 活動劇情 ID (5000000 ~ 5999999)
    cursor.execute("SELECT story_id FROM event_story_detail ORDER BY story_id ASC")
    event_story_ids = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    # 合併去重並排序
    all_ids = sorted(list(set(chara_story_ids + main_story_ids + tower_story_ids + event_story_ids)))
    
    print(f"[INFO] 自資料庫讀取完畢：")
    print(f"  ▶ 個人劇情: {len(chara_story_ids)} 筆")
    print(f"  ▶ 主線/公會/系統劇情: {len(main_story_ids)} 筆")
    print(f"  ▶ 露娜塔劇情: {len(tower_story_ids)} 筆")
    print(f"  ▶ 活動劇情: {len(event_story_ids)} 筆")
    print(f"  ▶ 合併去重總數: {len(all_ids)} 筆")
    
    return all_ids

import concurrent.futures

def process_story(story_id, new_hash, truth_version, idx, total):
    output_path = os.path.join(OUTPUT_DIR, f"{story_id}.json")
    
    # 智慧檢測是否為不帶 unit_id 的舊版檔案，或者是不包含 type 節點的檔案
    is_legacy = True
    if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    has_unit_id = any("unit_id" in item for item in data)
                    has_no_voice = any("無語音對白" in item.get("words", "") for item in data)
                    has_type = any("type" in item for item in data)
                    # 必須同時擁有 unit_id/無語音對白 且擁有 type 屬性，才判定為不需要更新的最新版
                    if (has_unit_id or has_no_voice) and has_type:
                        is_legacy = False
        except Exception:
            pass
            
    if not is_legacy:
        return "skip"
        
    if not new_hash:
        return "failed_no_hash"
        
    success = download_and_extract_story(story_id, new_hash, truth_version)
    return "success" if success else "failed"

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"[INFO] 建立輸出目錄：{OUTPUT_DIR}")

    # 1. 取得最新版本與 Manifest
    truth_version = get_truth_version()
    manifest_lines = download_story_manifest(truth_version)
    if not manifest_lines:
        print("[FATAL] 無法繼續，請檢查網路連線")
        return

    mapping = parse_manifest(manifest_lines)

    # 2. 獲取本地資料庫全部劇情列表 (主線 + 活動)
    db_story_ids = get_all_story_ids()
    
    # 3. 從 CDN Manifest 中補全所有在 CDN 上但資料庫中沒記載的新劇情 (例如 202504 之後的新活動劇情 9xxxxxx、旅行劇情 52xxxxx 等)
    cdn_story_ids = []
    for path in mapping.keys():
        if "storydata_" in path:
            try:
                id_str = path.split("storydata_")[1].split(".")[0]
                cdn_story_ids.append(int(id_str))
            except:
                pass
                
    # 合併去重
    story_ids = sorted(list(set(db_story_ids + cdn_story_ids)))
    print(f"[INFO] 經過 CDN Manifest 比對補全後，總下載話數：{len(story_ids)} 話（補齊了 {len(story_ids) - len(db_story_ids)} 話 CDN 獨佔劇情，包含 202504 後之新活動、旅行與回憶劇情）")

    if not story_ids:
        print("[ERROR] 無法取得任何劇情 ID，請確認連線與資料庫")
        story_ids = [2001001, 2001002, 2001003, 2001004, 2001005]
        print(f"[FALLBACK] 將預設下載 5 話測試劇情: {story_ids}")

    # 為了測試與更新，我們只針對前幾話，或者全部跑 (異步併發)
    # 本地只跑 2001001~2001005 以展示效果，也可以全部更新
    to_download = story_ids

    print("\n[START] 開始從 So-net 官方 CDN 高速下載與還原 100% 繁中對白 (支援背景與 CG)...")
    print("====================================================")
    
    success = 0
    skip = 0
    failed = 0
    
    total = len(to_download)
    
    # 使用 ThreadPoolExecutor 併發下載
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for idx, story_id in enumerate(to_download, 1):
            path_name = f"a/storydata_{story_id:07d}.unity3d"
            new_hash = mapping.get(path_name)
            
            future = executor.submit(process_story, story_id, new_hash, truth_version, idx, total)
            futures[future] = story_id
            
        for future in concurrent.futures.as_completed(futures):
            story_id = futures[future]
            try:
                res = future.result()
                if res == "success":
                    print(f"話數 {story_id} ... ✅ 下載並成功還原 100% 繁中對白 (含 Unit ID, 背景, CG)！")
                    success += 1
                elif res == "skip":
                    skip += 1
                else:
                    print(f"話數 {story_id} ... ❌ 下載或還原失敗！")
                    failed += 1
            except Exception as e:
                print(f"話數 {story_id} ... 💥 發生異常: {e}")
                failed += 1
            
    print("====================================================")
    print(f"[FINISHED] 台服官方劇情下載任務結束！")
    print(f"▶ 儲存路徑：{OUTPUT_DIR}")
    print(f"▶ 總處理：{len(to_download)} 話 (成功更新: {success} 筆, 跳過已是最新版: {skip} 筆, 失敗: {failed} 筆)")
    print("====================================================\n")

if __name__ == "__main__":
    main()
