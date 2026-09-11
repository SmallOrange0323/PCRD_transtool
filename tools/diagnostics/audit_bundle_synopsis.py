import os
import sys
import json
import sqlite3
import urllib.request
from pathlib import Path

# 確保 UTF-8 輸出
sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from pcrd_fetch import (
    SONET_CDN,
    WEB_HEADER,
    _get_sonet_ver,
    load_story_manifest_hash_map,
    _deserialize_story_raw
)

import UnityPy
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'

def inspect_bundle(bundle_data):
    bundle = UnityPy.load(bundle_data)
    commands_found = []
    metadata = {0: None, 1: None, 32: None}
    all_cmd_indices = set()
    for obj in bundle.objects:
        if obj.type.name == "TextAsset":
            data = obj.read()
            script = getattr(data, 'script', None) or getattr(data, 'm_Script', None)
            if not script:
                continue
            if isinstance(script, str):
                script = bytes(script, 'utf-8', 'surrogateescape')
            commands = _deserialize_story_raw(script)
            for idx, args in commands:
                all_cmd_indices.add(idx)
                if idx in (0, 1, 32) and args and metadata[idx] is None:
                    metadata[idx] = str(args[0]).strip()
    return metadata, sorted(list(all_cmd_indices))

def main():
    print("=== Story AssetBundle Metadata Audit ===")
    tv = _get_sonet_ver()
    print(f"Current So-net TruthVersion: {tv}")
    manifest_map = load_story_manifest_hash_map(tv)
    print(f"Loaded story manifest entries: {len(manifest_map)}")

    db_path = PROJECT_ROOT / "dashboard" / "redive_tw.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    sample_targets = [
        # 主線
        (2001001, "Main"), (2001002, "Main"), (2001003, "Main"), (2001004, "Main"), (2001005, "Main"),
        # 角色
        (1001001, "Chara"), (1001002, "Chara"), (1001003, "Chara"), (1002001, "Chara"), (1003001, "Chara"),
        # 公會
        (3001001, "Guild"), (3001002, "Guild"), (3001003, "Guild"), (3002001, "Guild"), (3002002, "Guild"),
        # 活動
        (5001001, "Event"), (5001002, "Event"), (5001003, "Event"), (5002001, "Event"), (5002002, "Event"),
        # 露娜塔/系統
        (4001001, "Tower/Sys"), (4001002, "Tower/Sys"), (4001003, "Tower/Sys"), (4001004, "Tower/Sys"), (4001005, "Tower/Sys"),
    ]

    results = []

    for sid, stype in sample_targets:
        # 1. 查詢 DB
        db_title, db_sub = None, None
        if stype == "Event":
            c.execute("SELECT title, sub_title FROM event_story_detail WHERE story_id = ?", (sid,))
        else:
            c.execute("SELECT title, sub_title FROM story_detail WHERE story_id = ?", (sid,))
        row = c.fetchone()
        if row:
            db_title, db_sub = row[0], row[1]

        # 2. 查詢 Bundle
        h = manifest_map.get(sid)
        if not h:
            print(f"⚠️ [story_id={sid}] Hash not found in manifest")
            continue

        bundle_url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
        req = urllib.request.Request(bundle_url, headers=WEB_HEADER)
        with urllib.request.urlopen(req, timeout=15) as resp:
            b_data = resp.read()

        meta, indices = inspect_bundle(b_data)

        res_item = {
            "story_id": sid,
            "type": stype,
            "db_title": db_title,
            "db_sub_title": db_sub,
            "cmd0": meta.get(0),
            "cmd1": meta.get(1),
            "cmd32": meta.get(32),
            "all_indices": indices
        }
        results.append(res_item)
        print(f"\n[ID: {sid} | {stype}]")
        print(f"  DB title:     {repr(db_title)}")
        print(f"  DB sub_title: {repr(db_sub)}")
        print(f"  Bundle cmd0:  {repr(meta.get(0))}")
        print(f"  Bundle cmd1:  {repr(meta.get(1))}")
        print(f"  Bundle cmd32: {repr(meta.get(32))}")
        print(f"  Indices:      {indices}")

    # 輸出統計
    print("\n================== SUMMARY ==================")
    matches_sub_cmd32 = sum(1 for r in results if r["db_sub_title"] == r["cmd32"])
    cmd1_nonempty = sum(1 for r in results if r["cmd1"] is not None and len(r["cmd1"]) > 0)
    print(f"Total sampled: {len(results)}")
    print(f"DB sub_title == Bundle cmd32: {matches_sub_cmd32} / {len(results)}")
    print(f"Bundle cmd1 non-empty:        {cmd1_nonempty} / {len(results)}")

    out_file = PROJECT_ROOT / "scratch" / "bundle_audit_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Saved full json to {out_file}")

if __name__ == "__main__":
    main()
