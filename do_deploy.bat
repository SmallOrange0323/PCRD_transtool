@echo off
chcp 65001 >nul
cd /d "%~dp0dist_story_map"
git add -A
git commit -m "deploy_full_update_voices_and_tw_sql_fix"
git push -f origin gh-pages
