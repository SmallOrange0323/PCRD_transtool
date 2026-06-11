# -*- coding: utf-8 -*-
import os
import json
import sqlite3
import urllib.request
import concurrent.futures
import sys
import UnityPy

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.stdout.reconfigure(encoding='utf-8')
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 因為在根目錄的子目錄下，將路徑與專案根目錄對齊
ROOT_DIR = os.path.dirname(BASE_DIR)
DB_PATH = os.path.join(ROOT_DIR, "dashboard", "redive_tw.db")
OUTPUT_DIR = os.path.join(ROOT_DIR, "dashboard", "story")

HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

# 🎬 引用 Cygames 序列化規範反序列化
import base64
from enum import Enum
from struct import unpack

class CommandId(Enum):
    NONE = -1
    TITLE = 0
    PRINT = 6
    VO = 12

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
            array.append(str_.decode('utf-8', errors='ignore'))
        except Exception:
            array.append("")
    return CommandId(index) if index in CommandId._value2member_map_ else CommandId.NONE, array

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

def clean_text(text):
    return text.replace("\\n", "\n").replace("{0}", "{player}").replace('\\"', '"')

def extract_story_dialogues(bytes_data):
    commands = deserialize_story_raw(bytes_data)
    dialogues = []
    current_unit_id = None
    current_voice = None
    
    for command_id, args in commands:
        if command_id == CommandId.PRINT and len(args) >= 2:
            speaker = args[0]
            words = clean_text(args[1])
            diag = {"name": speaker, "words": words}
            dialogues.append(diag)
    return dialogues

def main():
    print("[INFO] 開始檢查是否有缺失的劇情 JSON 檔案...")
    
    # 1. 取得最新版本與 Manifest
    import download_stories_tw
    truth_version = download_stories_tw.get_truth_version()
    manifest_lines = download_stories_tw.download_story_manifest(truth_version)
    if not manifest_lines:
        print("[FATAL] 無法獲取 CDN 清單")
        return
        
    mapping = download_stories_tw.parse_manifest(manifest_lines)
    db_story_ids = download_stories_tw.get_all_story_ids()
    
    cdn_story_ids = []
    for path in mapping.keys():
        if "storydata_" in path:
            try:
                id_str = path.split("storydata_")[1].split(".")[0]
                cdn_story_ids.append(int(id_str))
            except:
                pass
                
    all_ids = sorted(list(set(db_story_ids + cdn_story_ids)))
    
    # 2. 比對哪些檔案缺失或大小異常
    missing_ids = []
    for sid in all_ids:
        path = os.path.join(OUTPUT_DIR, f"{sid}.json")
        if not os.path.exists(path) or os.path.getsize(path) < 10:
            missing_ids.append(sid)
            
    print(f"[INFO] 總應有話數: {len(all_ids)} 話")
    print(f"[INFO] 發現缺失/未下載成功的話數: {len(missing_ids)} 話")
    
    if not missing_ids:
        print("[SUCCESS] 恭喜！無任何缺失劇情！")
        return
        
    # 3. 專屬重新下載
    print(f"[START] 開始重新補齊這 {len(missing_ids)} 筆劇情...")
    success = 0
    failed = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {}
        for idx, story_id in enumerate(missing_ids, 1):
            path_name = f"a/storydata_{story_id:07d}.unity3d"
            new_hash = mapping.get(path_name)
            
            future = executor.submit(download_stories_tw.download_and_extract_story, story_id, new_hash, truth_version)
            futures[future] = story_id
            
        for future in concurrent.futures.as_completed(futures):
            story_id = futures[future]
            try:
                res = future.result()
                if res:
                    print(f"話數 {story_id} ... 補齊成功！")
                    success += 1
                else:
                    print(f"話數 {story_id} ... 補齊失敗。")
                    failed += 1
            except Exception as e:
                print(f"話數 {story_id} 異常: {e}")
                failed += 1
                
    print(f"\n[FINISHED] 補齊任務結束！成功: {success} 筆, 失敗: {failed} 筆")

if __name__ == '__main__':
    main()
