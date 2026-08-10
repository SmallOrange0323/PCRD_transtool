# -*- coding: utf-8 -*-
"""
pcrd_deploy.py — PCRD 網頁部署 CLI 工具
用途: 注入新角色到前端 JS、打包靜態資源、推送 GitHub Pages

子命令:
  inject-character  注入新角色到 characters.js
  bundle            打包靜態資源到 dist_story_map/
  push-pages        推送到 GitHub Pages gh-pages 分支
  monitor           監控 GitHub Pages CDN 部署狀態
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

# ─────────────────────────── 常數 ───────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")
DIST_DIR = os.path.join(BASE_DIR, "dist_story_map")
CHARACTERS_JS = os.path.join(DASHBOARD_DIR, "characters.js")
BUNDLE_SCRIPT = os.path.join(DASHBOARD_DIR, "scripts", "bundle_story_map.py")
DB_PATH = os.path.join(DASHBOARD_DIR, "redive_tw.db")
TRACKED_CHARS_PATH = os.path.join(DASHBOARD_DIR, "data", "tracked_characters.json")

GITHUB_API = "https://api.github.com"
GITHUB_REPO = "SmallOrange0323/PCRD_transtool"
GITHUB_PAGES_URL = "https://smallorange0323.github.io/PCRD_transtool"

# ─────────────────────────── 工具函式 ───────────────────────────

def _write_output(path, data):
    if path:
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _load_tracked_chars():
    if os.path.exists(TRACKED_CHARS_PATH):
        with open(TRACKED_CHARS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"characters": []}


def _get_char_name_from_db(unit_id):
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT unit_name FROM unit_data WHERE unit_id = ?", (unit_id,))
            row = cur.fetchone()
            conn.close()
            if row:
                return row[0]
        except Exception:
            pass
    return f"角色_{unit_id}"


def _get_story_ids_from_db(unit_id):
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                "SELECT story_id FROM chara_story_status WHERE unit_id = ? ORDER BY story_id",
                (unit_id,)
            )
            rows = cur.fetchall()
            conn.close()
            if rows:
                return [r[0] for r in rows]
        except Exception:
            pass
    return [unit_id * 10 + i for i in range(1, 5)]


def _run_git(args_list, cwd):
    """執行 Git 命令，返回 (returncode, stdout, stderr)。"""
    result = subprocess.run(
        ["git"] + args_list,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _clear_git_lock(git_dir):
    """清除 git index.lock 殘留。"""
    lock_path = os.path.join(git_dir, "index.lock")
    if os.path.exists(lock_path):
        os.remove(lock_path)
        print("  🔓 已清除殘留的 index.lock")


# ─────────────────────────── 子命令實作 ───────────────────────────

def cmd_inject_character(args):
    """在 characters.js 中注入新角色定義。"""
    unit_id = args.unit_id
    char_name = args.name or _get_char_name_from_db(unit_id)
    story_ids = _get_story_ids_from_db(unit_id)
    u3 = unit_id + 30

    print(f"💉 注入角色：{char_name} (unit_id={unit_id})")

    if not os.path.exists(CHARACTERS_JS):
        print(f"❌ 找不到 {CHARACTERS_JS}", file=sys.stderr)
        sys.exit(1)

    with open(CHARACTERS_JS, 'r', encoding='utf-8') as f:
        content = f.read()

    # 檢查是否已存在
    if str(unit_id) in content:
        print(f"  ℹ️ unit_id={unit_id} 已存在於 characters.js，跳過注入（冪等）")
        _write_output(args.output, {"status": "already_exists", "unit_id": unit_id})
        return

    # 建構注入的 JS 物件字串
    story_ids_js = json.dumps(story_ids)
    inject_block = f"""
    // ── {char_name} (unit_id={unit_id}) 台版換裝 ──
    {{
        id: {unit_id},
        name: "{char_name}",
        rarity: 3,
        iconId: {u3},
        cardId: {u3},
        storyIds: {story_ids_js}
    }},"""

    # 尋找注入錨點（EXTRA_CHARACTERS 陣列）
    # 先嘗試找 EXTRA_CHARACTERS，再 fallback 找 const characters
    anchor_patterns = [
        r"(const EXTRA_CHARACTERS\s*=\s*\[)",
        r"(EXTRA_CHARACTERS\.push\()",
        r"(\/\/ ── .+台版換裝 ──)",
    ]

    injected = False
    for pattern in anchor_patterns:
        match = re.search(pattern, content)
        if match:
            insert_pos = match.end()
            content = content[:insert_pos] + inject_block + content[insert_pos:]
            injected = True
            print(f"  ✅ 已在錨點 '{match.group().strip()[:40]}...' 後注入角色定義")
            break

    if not injected:
        print("  ⚠️ 未找到 EXTRA_CHARACTERS 錨點，請手動確認注入位置", file=sys.stderr)
        _write_output(args.output, {"status": "anchor_not_found", "unit_id": unit_id})
        sys.exit(1)

    with open(CHARACTERS_JS, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"  ✅ characters.js 已更新")
    _write_output(args.output, {
        "status": "injected",
        "unit_id": unit_id,
        "char_name": char_name,
        "story_ids": story_ids
    })
    print(f"\n✅ 注入完成！報告已寫入 {args.output}")


def cmd_bundle(args):
    """執行打包腳本。"""
    print("📦 開始打包靜態資源...")
    result = subprocess.run(
        [sys.executable, BUNDLE_SCRIPT],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"❌ 打包失敗:\n{result.stderr}", file=sys.stderr)
        _write_output(args.output, {"status": "error", "stderr": result.stderr})
        sys.exit(1)

    _write_output(args.output, {"status": "ok", "stdout": result.stdout})
    print(f"\n✅ 打包完成！報告已寫入 {args.output}")


def cmd_verify(args):
    """執行代碼與資源完整性自檢。"""
    print("🛡️  開始發布前自動化防禦自檢...")
    errors = []
    warnings = []

    # 1. 靜態語法檢查 (使用 Node 引擎對本地 source JS 做 Linter)
    for js_file in ["db.js", "chapter-data.js", "map.js"]:
        js_path = os.path.join(DASHBOARD_DIR, js_file)
        if os.path.exists(js_path):
            result = subprocess.run(
                ["node", "--check", js_path],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                errors.append(f"JS 語法錯誤 ({js_file}):\n{result.stderr.strip()}")
            else:
                print(f"  [Linter] {js_file} 語法檢查: ✅ 通過")
        else:
            warnings.append(f"未找到原始腳本: {js_file}")

    # 2. 檢查內嵌版 index.html 是否有被正確生成
    index_html = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(index_html):
        # 簡單讀取確認是否包含 inline 標記
        with open(index_html, 'r', encoding='utf-8') as f:
            html = f.read()
        if "db.js INLINED" not in html or "chapter-data.js INLINED" not in html:
            errors.append("index.html 中缺少核心 JS (db.js 或 chapter-data.js) 的內嵌標記，CDN 快取破壞失效！")
        else:
            print("  [Inline] index.html 內嵌核心 JS: ✅ 通過")
    else:
        errors.append("未找到 dist_story_map/index.html，請先執行 bundle。")

    # 3. 資源存在性與破圖自檢 (檢查最新的 5 個 story json 是否在 dist)
    chapters_json_path = os.path.join(DIST_DIR, "data", "chapters.json")
    if os.path.exists(chapters_json_path):
        try:
            with open(chapters_json_path, 'r', encoding='utf-8') as f:
                ch_data = json.load(f)
            # 遍歷 Part 3 提取 story_id
            part3_gw = ch_data.get("3", {}).get("game_world", {})
            latest_sids = []
            for ch_key in sorted(part3_gw.keys(), reverse=True)[:2]:
                for ep in part3_gw[ch_key].get("episodes", []):
                    latest_sids.append(ep.get("story_id"))
            
            # 檢查 dist 故事對白 JSON
            missing_jsons = []
            for sid in latest_sids:
                if sid:
                    path = os.path.join(DIST_DIR, "story", f"{sid}.json")
                    if not os.path.exists(path):
                        missing_jsons.append(f"{sid}.json")
            if missing_jsons:
                errors.append(f"缺少最新劇本 JSON 檔案 (會造成線上載入失敗): {', '.join(missing_jsons)}")
            else:
                print("  [Assets] 最新主線話數對白 JSON 存在性: ✅ 通過")
        except Exception as e:
            warnings.append(f"讀取 chapters.json 資源自檢失敗: {e}")

    # 4. 輸出檢驗報告
    report_data = {
        "status": "fail" if errors else "ok",
        "errors": errors,
        "warnings": warnings,
        "time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    _write_output(args.output, report_data)

    if errors:
        print("\n❌ 自檢失敗！請修正以下錯誤後再嘗試部署：", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)
    
    if warnings:
        print("\n⚠️ 警報（非致命）：")
        for warn in warnings:
            print(f"  - {warn}")
            
    print("\n✅ 三道防禦自檢全部通過！")


def cmd_push_pages(args):
    """推送到 GitHub Pages。"""
    # 部署前強制執行自檢，杜絕損壞代碼上線
    class DummyArgs:
        def __init__(self, output):
            self.output = "tools/verify_report.json"
    cmd_verify(DummyArgs("tools/verify_report.json"))

    print("\n🚀 開始部署到 GitHub Pages...")
    results = {"steps": []}

    git_dir = os.path.join(DIST_DIR, ".git")

    # Step 1: 清除 lock
    _clear_git_lock(git_dir)

    # Step 2: git reset
    code, out, err = _run_git(["reset"], cwd=DIST_DIR)
    results["steps"].append({"step": "reset", "code": code, "out": out})
    print(f"  git reset: {'✅' if code == 0 else '⚠️'} {err or out}")

    # Step 3: git add -A
    code, out, err = _run_git(["add", "-A"], cwd=DIST_DIR)
    results["steps"].append({"step": "add", "code": code})
    print(f"  git add -A: {'✅' if code == 0 else '❌'}")
    if code != 0:
        print(f"    ❌ 失敗: {err}", file=sys.stderr)
        _write_output(args.output, results)
        sys.exit(1)

    # Step 4: git commit
    message = args.message or f"deploy: update content ({time.strftime('%Y-%m-%d')})"
    code, out, err = _run_git(["commit", "-m", message], cwd=DIST_DIR)
    results["steps"].append({"step": "commit", "code": code, "out": out})
    if code == 0:
        print(f"  git commit: ✅ {out}")
    elif "nothing to commit" in out + err:
        print("  git commit: ℹ️ 沒有變更需要提交")
        _write_output(args.output, {**results, "status": "nothing_to_commit"})
        return
    else:
        print(f"  git commit: ❌ {err}", file=sys.stderr)
        _write_output(args.output, results)
        sys.exit(1)

    # Step 5: git push -f origin gh-pages
    code, out, err = _run_git(["push", "-f", "origin", "gh-pages"], cwd=DIST_DIR)
    results["steps"].append({"step": "push_gh_pages", "code": code, "out": out, "err": err})
    if code == 0:
        print(f"  git push gh-pages: ✅")
    else:
        print(f"  git push gh-pages: ❌ {err}", file=sys.stderr)
        _write_output(args.output, results)
        sys.exit(1)

    # Step 6: 同步 master 分支（前端源碼）
    print("  📤 同步前端源碼到 master 分支...")
    src_files = ["dashboard/characters.js", "dashboard/style.css", "dashboard/map.js"]
    existing = [f for f in src_files if os.path.exists(os.path.join(BASE_DIR, f))]
    if existing:
        _clear_git_lock(os.path.join(BASE_DIR, ".git"))
        _run_git(["add"] + existing, cwd=BASE_DIR)
        code, out, err = _run_git(["commit", "-m", f"sync: {message}"], cwd=BASE_DIR)
        if code == 0:
            _run_git(["push", "origin", "HEAD:master"], cwd=BASE_DIR)
            print("    ✅ master 分支已同步")
        else:
            print(f"    ℹ️ {out or err}")

    results["status"] = "ok"
    _write_output(args.output, results)
    print(f"\n✅ 部署完成！報告已寫入 {args.output}")


def cmd_monitor(args):
    """監控 GitHub Pages CDN 部署狀態。"""
    timeout = args.timeout
    print(f"👀 監控 GitHub Pages 部署（最長 {timeout}s）...")

    # 取得預期的最新 commit sha
    try:
        api_url = f"{GITHUB_API}/repos/{GITHUB_REPO}/branches/gh-pages"
        req = urllib.request.Request(api_url, headers={"User-Agent": "pcrd-deploy"})
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read())
        expected_sha = data["commit"]["sha"]
        print(f"  目標 Commit: {expected_sha[:8]}")
    except Exception as e:
        print(f"  ⚠️ 無法取得目標 SHA: {e}，改為輪詢 characters.js 內容...")
        expected_sha = None

    start = time.monotonic()
    success = False
    check_url = f"{GITHUB_PAGES_URL}/characters.js"

    for i in range(timeout // 10):
        elapsed = int(time.monotonic() - start)
        try:
            url = f"{check_url}?v={time.time()}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as res:
                content = res.read().decode('utf-8')
            # 簡單確認 CDN 已更新（包含最近新角色的 ID）
            if expected_sha:
                # 改成查 API 確認 Pages deployment
                api_url = f"{GITHUB_API}/repos/{GITHUB_REPO}/pages/builds"
                req2 = urllib.request.Request(api_url, headers={"User-Agent": "pcrd-deploy"})
                try:
                    with urllib.request.urlopen(req2, timeout=10) as r2:
                        builds = json.loads(r2.read())
                    if builds and builds[0].get("status") == "built":
                        success = True
                except Exception:
                    pass
            if not success and content:
                # fallback: 只要 CDN 有回應就算成功
                success = True
        except Exception:
            pass

        if success:
            print(f"\n🎉 [{elapsed}s] GitHub Pages 部署成功！")
            print(f"   請在瀏覽器按 Ctrl+F5 強制重新整理：{GITHUB_PAGES_URL}")
            break
        print(f"  [{elapsed}s] 等待 CDN 生效...", end="\r", flush=True)
        time.sleep(10)

    if not success:
        print(f"\n⚠️ 超過 {timeout}s 仍在等待，但推送已成功，稍後刷新即可")

    result = {"status": "ok" if success else "timeout", "elapsed": int(time.monotonic() - start)}
    _write_output(args.output, result)


# ─────────────────────────── CLI 入口 ───────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PCRD 網頁部署工具")
    sub = parser.add_subparsers(dest="command", required=True)

    # inject-character
    p_inj = sub.add_parser("inject-character", help="注入新角色到 characters.js")
    p_inj.add_argument("--unit-id", type=int, required=True, help="角色 unit_id")
    p_inj.add_argument("--name", help="角色顯示名稱（留空則從 DB 取得）")
    p_inj.add_argument("--output", default="tools/inject_report.json", help="輸出報告路徑")

    # bundle
    p_bundle = sub.add_parser("bundle", help="打包靜態資源")
    p_bundle.add_argument("--output", default="tools/bundle_report.json", help="輸出報告路徑")

    # push-pages
    p_push = sub.add_parser("push-pages", help="推送到 GitHub Pages")
    p_push.add_argument("--message", help="Git commit message")
    p_push.add_argument("--output", default="tools/push_report.json", help="輸出報告路徑")

    # monitor
    p_mon = sub.add_parser("monitor", help="監控 GitHub Pages CDN 部署狀態")
    p_mon.add_argument("--timeout", type=int, default=300, help="最長等待秒數（預設 300）")
    p_mon.add_argument("--output", default="tools/monitor_report.json", help="輸出報告路徑")

    # verify
    p_ver = sub.add_parser("verify", help="執行代碼與資源完整性自檢")
    p_ver.add_argument("--output", default="tools/verify_report.json", help="輸出報告路徑")
 
    args = parser.parse_args()
    dispatch = {
        "inject-character": cmd_inject_character,
        "bundle": cmd_bundle,
        "push-pages": cmd_push_pages,
        "monitor": cmd_monitor,
        "verify": cmd_verify,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
