@echo off
echo [LEGACY ARCHIVE] This historical deploy script is disabled.
echo Use update_story_map.py / pipeline.deploy instead.
exit /b 1

REM ==============================================================================
REM Historical implementation retained below for reference (Unreachable)
REM ==============================================================================
REM chcp 65001 >nul
REM cd /d "%~dp0..\..\dist_story_map"
REM git add -A
REM git commit -m "deploy_full_update_voices_and_tw_sql_fix"
REM git push -f origin gh-pages
