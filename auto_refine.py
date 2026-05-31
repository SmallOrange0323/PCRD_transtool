import os
import subprocess
import time
import cv2
import numpy as np

# ==========================================
# 設定區
# ==========================================
# 請設定您的 BlueStacks ADB 連接埠 (常見的有 5555, 5556, 5557 等)
ADB_PORT = "5555"
ADB_HOST = "127.0.0.1"

# 「再次鍊成」按鈕的坐標 (請根據您的解析度調整)
# 您可以開啟模擬器的「顯示指標位置」功能來取得精確坐標
CLICK_X = 700
CLICK_Y = 900

# 比對的門檻值 (0.0 ~ 1.0)，越高越嚴格
THRESHOLD = 0.8

# 目標範本圖片名稱
TEMPLATE_FILE = "target.png"
# ==========================================

def run_adb(cmd):
    """執行 ADB 指令並返回結果"""
    adb_cmd = f"adb -s {ADB_HOST}:{ADB_PORT} {cmd}"
    try:
        result = subprocess.run(adb_cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"指令超時: {adb_cmd}")
        return ""
    except Exception as e:
        print(f"執行出錯: {e}")
        return ""

def connect_device():
    """連接 ADB 裝置"""
    print(f"嘗試連接到 {ADB_HOST}:{ADB_PORT}...")
    os.system(f"adb connect {ADB_HOST}:{ADB_PORT}")
    time.sleep(1)
    devices = subprocess.run("adb devices", shell=True, capture_output=True, text=True).stdout
    if f"{ADB_HOST}:{ADB_PORT}" in devices:
        print("連接成功！")
        return True
    else:
        print("連接失敗，請確認模擬器的 ADB 功能已開啟，且連接埠正確。")
        return False

def capture_screen():
    """透過 ADB 獲取螢幕截圖並轉換為 OpenCV 格式"""
    # 使用 exec-out 可以直接將二進位資料導出，速度較快
    cmd = f"adb -s {ADB_HOST}:{ADB_PORT} exec-out screencap -p"
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    screenshot_data, _ = process.communicate()
    
    # 轉換為 numpy array 再由 cv2 解碼
    nparr = np.frombuffer(screenshot_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img

def check_target(screen, template):
    """檢查螢幕中是否包含範本"""
    res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    
    if max_val >= THRESHOLD:
        print(f"找到目標！相似度: {max_val:.2f}")
        return True, max_loc
    else:
        print(f"未找到目標，最高相似度: {max_val:.2f}")
        return False, None

def main():
    # 1. 檢查 ADB 是否可用
    if os.system("adb version") != 0:
        print("錯誤：找不到 adb 指令。請確保 adb 已加入環境變數，或放在此腳本同目錄下。")
        print("您可以從網路下載 'platform-tools' 並解壓，將 adb.exe 放在這裡。")
        return
        
    # 2. 連接裝置
    if not connect_device():
        return
        
    # 3. 檢查範本圖片
    if not os.path.exists(TEMPLATE_FILE):
        print(f"\n找不到範本圖片 '{TEMPLATE_FILE}'！")
        print("請先手動執行一次鍊成，將出現「魔法防禦貫通 3」的區域截圖，")
        print(f"並儲存為 '{TEMPLATE_FILE}' 放在此腳本同目錄下。")
        
        print("\n現在為您擷取一張當前畫面作為參考 (命名為 current_screen.png)...")
        screen = capture_screen()
        if screen is not None:
            cv2.imwrite("current_screen.png", screen)
            print("已儲存當前畫面。請從中剪下你要辨識的屬性區域，另存為 target.png。")
        return
        
    template = cv2.imread(TEMPLATE_FILE, cv2.IMREAD_COLOR)
    
    print("\n=== 開始自動鍊成腳本 ===")
    print("請確保遊戲畫面停留在「鍊成結果」視窗。")
    print(f"目標：尋找 '{TEMPLATE_FILE}' 的圖案。")
    print("按 Ctrl+C 可以停止腳本。")
    
    count = 0
    try:
        while True:
            count += 1
            print(f"\n--- 第 {count} 次檢查 ---")
            
            # 擷取畫面
            screen = capture_screen()
            if screen is None:
                print("擷取畫面失敗，跳過這回合。")
                time.sleep(1)
                continue
                
            # 檢查是否符合條件
            found, loc = check_target(screen, template)
            
            if found:
                print("恭喜！刷到目標屬性！腳本停止。")
                break
            else:
                # 點擊「再次鍊成」
                print(f"點擊「再次鍊成」按鈕 (坐標: {CLICK_X}, {CLICK_Y})...")
                run_adb(f"shell input tap {CLICK_X} {CLICK_Y}")
                
                # 等待動畫時間與載入
                # 這裡設定等待 3 秒，請根據您的模擬器流暢度調整
                print("等待動畫完成...")
                time.sleep(3)
                
    except KeyboardInterrupt:
        print("\n使用者手動停止腳本。")

if __name__ == "__main__":
    main()
