# -*- coding: utf-8 -*-
import os
import subprocess
import sys

def run_cmd(cmd, cwd=None):
    try:
        res = subprocess.run(cmd, shell=True, check=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True, res.stdout
    except subprocess.CalledProcessError as e:
        return False, f"Error: {e.stderr}\nOutput: {e.stdout}"

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(script_dir, "dist_story_map")
    git_dir = os.path.join(dist_dir, ".git")
    
    print("[Deploy] 開始執行增量部署程序...")
    
    # 1. 檢查 dist_story_map 是否存在
    if not os.path.exists(dist_dir):
        print("[Error] 找不到發行目錄 dist_story_map，請先執行 bundle_story_map.py 打包！")
        sys.exit(1)
        
    # 2. 如果 .git 不存在，進行初始化
    is_new_repo = False
    if not os.path.exists(git_dir):
        print("[Deploy] 偵測到首次部署，初始化本地 gh-pages Git 緩存倉庫...")
        is_new_repo = True
        run_cmd("git init", cwd=dist_dir)
        run_cmd("git remote add origin https://github.com/SmallOrange0323/PCRD_transtool.git", cwd=dist_dir)
        run_cmd("git checkout -b gh-pages", cwd=dist_dir)
        
    # 3. 增量提交
    print("[Deploy] 正在掃描並追蹤變更檔案 (git add)...")
    run_cmd("git add -A -f", cwd=dist_dir)
    
    print("[Deploy] 正在建立提交 (git commit)...")
    success, msg = run_cmd('git commit -m "deploy: update story map web"', cwd=dist_dir)
    if not success and "nothing to commit" in msg:
        print("[Info] 沒有檢測到任何代碼或對白更新，無需上傳！")
        sys.exit(0)
        
    # 4. 推送至遠端 (如果是第一次，使用 -f 強制覆蓋舊分支以建立起點)
    print("[Deploy] 正在推送變更至 GitHub (gh-pages)...")
    push_cmd = "git push -f origin gh-pages" if is_new_repo else "git push origin gh-pages"
    
    success, output = run_cmd(push_cmd, cwd=dist_dir)
    if success:
        print("[Success] 部署成功！您的劇情地圖網頁已成功推送到 gh-pages。")
        print("[Info] 網址：https://smallorange0323.github.io/PCRD_transtool/")
    else:
        print(f"[Error] 推送失敗：\n{output}")
        sys.exit(1)

if __name__ == "__main__":
    main()
