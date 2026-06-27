# -*- coding: utf-8 -*-
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist_story_map")

def run_cmd_str(cmd):
    print(f"[Git] 執行: {cmd}")
    res = subprocess.run(cmd, cwd=DIST_DIR, shell=True, capture_output=True, text=True)
    if res.stdout:
        print("[Stdout]", res.stdout.strip()[:200])
    if res.stderr:
        print("[Stderr]", res.stderr.strip()[:200])
    return res.returncode == 0

def force_deploy():
    print("=== 開始進行 100% 強制真上傳部署 ===")
    
    # 1. git add
    run_cmd_str("git add -A")
    
    # 2. git commit
    run_cmd_str('git commit -m "deploy: full update with offline voices and TW SQL fixes"')
    
    # 3. git push
    print("[Git] 正在上傳全套語音檔與最新代碼至 GitHub gh-pages (請耐心稍候)...")
    success = run_cmd_str("git push -f origin gh-pages")
    
    if success:
        print("\n🎉 [Success] 100% 強制真部署成功！GitHub Pages 已收到最新版本與全套音檔！")
    else:
        print("\n❌ [Failed] 推送過程遇到問題。")

if __name__ == "__main__":
    force_deploy()
