@echo off
chcp 65001 >nul
echo ==========================================
echo  PCRD Data Hub - 本地伺服器啟動器
echo ==========================================
echo.
echo 正在啟動 HTTP 伺服器 (port 8080)...
echo 請在瀏覽器開啟: http://localhost:8080/dashboard/
echo.
echo 按 Ctrl+C 可停止伺服器
echo ==========================================
echo.
python -m http.server 8080
pause