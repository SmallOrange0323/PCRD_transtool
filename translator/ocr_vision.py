# -*- coding: utf-8 -*-
"""
PCRD 即時 AI 翻譯系統 - 影像監控與 OCR 辨識模組
"""

import os
import cv2
import numpy as np
import logging

# 設定日誌記錄
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PCRD_OCR_Vision")

# 嘗試加載本地 PaddleOCR，提供優雅的降級機制
try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
    logger.info("成功導入本地 PaddleOCR 模組。")
except ImportError:
    PaddleOCR = None
    PADDLE_AVAILABLE = False
    logger.warning("未偵測到本地 PaddleOCR 模組，將使用 Fallback 機制（直接推薦 Gemini Vision API 翻譯）。")

# 導入配置設定
try:
    import config
except ImportError:
    # 支援作為獨立指令碼或在父目錄下執行時的導入
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import config

class PCRDVisionDetector:
    """
    PCRD 遊戲畫面視覺偵測器
    負責對話框定位、文字變更比對 (Throttling) 與粉紅箭頭 ▼ 閃爍監控，並封裝本地 PaddleOCR
    """
    def __init__(self):
        # 儲存上一幀的對話框文字區域（灰階影像），用於變化比對
        self.last_dialog_text_area_gray = None
        
        # 初始化 PaddleOCR (如果可用)
        self.ocr_engine = None
        if PADDLE_AVAILABLE:
            try:
                # 初始化日文辨識引擎，關閉 cls 以提升速度
                self.ocr_engine = PaddleOCR(use_angle_cls=False, lang='japan', show_log=False)
                logger.info("PaddleOCR (日文) 引擎初始化完成。")
            except Exception as e:
                logger.error(f"PaddleOCR 引擎初始化失敗: {e}")
                self.ocr_engine = None

    def crop_dialog_box(self, frame: np.ndarray) -> np.ndarray:
        """
        高精度裁剪對話框區域，相對於遊戲視窗比例進行裁剪以適應視窗縮放
        """
        if frame is None:
            logger.error("傳入的影像幀為 None，無法裁剪對話框。")
            return None

        h, w = frame.shape[:2]
        ratio = config.DIALOG_BOX_RATIO

        # 計算像素座標
        left = int(w * ratio["left"])
        top = int(h * ratio["top"])
        width = int(w * ratio["width"])
        height = int(h * ratio["height"])

        # 邊界安全檢查
        right = min(left + width, w)
        bottom = min(top + height, h)
        left = max(0, left)
        top = max(0, top)

        dialog_img = frame[top:bottom, left:right]
        logger.debug(f"已裁剪對話框區域：座標 ({left}, {top}) 到 ({right}, {bottom})，大小: {dialog_img.shape}")
        return dialog_img

    def crop_speaker(self, frame: np.ndarray) -> np.ndarray:
        """
        高精度裁剪說話者名字區域，相對於遊戲視窗比例進行裁剪
        """
        if frame is None:
            logger.error("傳入的影像幀為 None，無法裁剪說話者。")
            return None

        h, w = frame.shape[:2]
        ratio = config.SPEAKER_RATIO

        # 計算像素座標
        left = int(w * ratio["left"])
        top = int(h * ratio["top"])
        width = int(w * ratio["width"])
        height = int(h * ratio["height"])

        # 邊界安全檢查
        right = min(left + width, w)
        bottom = min(top + height, h)
        left = max(0, left)
        top = max(0, top)

        speaker_img = frame[top:bottom, left:right]
        logger.debug(f"已裁剪說話者區域：座標 ({left}, {top}) 到 ({right}, {bottom})，大小: {speaker_img.shape}")
        return speaker_img

    def has_text_changed(self, current_dialog: np.ndarray) -> bool:
        """
        文字變更檢測演算法 (Throttling)
        計算前後兩幀對話框局部文字區域的相似度。
        為防止右下角 ▼ 閃爍箭頭干擾比對，直接切除右側 18% 區域，只比對左側與中央的文字主體區域。
        """
        if current_dialog is None:
            return False

        h, w = current_dialog.shape[:2]
        
        # 排除右側 18% 的箭頭常現區域，只截取左側 82% 進行文字比對
        text_area_w = int(w * 0.82)
        text_area = current_dialog[:, 0:text_area_w]

        # 灰階化與高斯模糊去噪，減少細微鋸齒或壓縮噪點的干擾
        gray_text_area = cv2.cvtColor(text_area, cv2.COLOR_BGR2GRAY)
        gray_text_area = cv2.GaussianBlur(gray_text_area, (3, 3), 0)

        if self.last_dialog_text_area_gray is None:
            self.last_dialog_text_area_gray = gray_text_area
            logger.info("首幀畫面登錄，判定為文字已變更。")
            return True

        # 若影像大小不同（例如視窗被拉伸），重置上一幀並視為變更
        if gray_text_area.shape != self.last_dialog_text_area_gray.shape:
            logger.info("偵測到視窗尺寸改變，重置基準幀並視為文字變更。")
            self.last_dialog_text_area_gray = gray_text_area
            return True

        # 計算平均絕對誤差 MAE
        diff = cv2.absdiff(gray_text_area, self.last_dialog_text_area_gray)
        mae = np.mean(diff) / 255.0

        # 比對閾值
        threshold = getattr(config, 'PIXEL_CHANGE_THRESHOLD', 0.015)
        changed = mae > threshold

        if changed:
            logger.info(f"偵測到對話框文字發生實質改變，MAE 變動量: {mae:.5f} (閥值: {threshold})")
            self.last_dialog_text_area_gray = gray_text_area
        else:
            logger.debug(f"對話框文字靜止或微幅動畫，MAE 變動量: {mae:.5f} (低於閥值 {threshold})，略過翻譯。")

        return changed

    def detect_pink_arrow(self, dialog_img: np.ndarray) -> bool:
        """
        粉紅箭頭 ▼ 閃爍與出現監控
        精準監控對話框右下角區域中代表文字播放完畢的粉紅箭頭。
        使用 HSV 色彩分割與輪廓幾何特徵，不依賴外部範本，實現自適應縮放的穩健檢測。
        """
        if dialog_img is None:
            return False

        h, w = dialog_img.shape[:2]

        # 定位右下角局部監控區 (X: 85% ~ 98%, Y: 55% ~ 95%)
        y_start, y_end = int(h * 0.55), int(h * 0.95)
        x_start, x_end = int(w * 0.85), int(w * 0.98)
        arrow_zone = dialog_img[y_start:y_end, x_start:x_end]

        # 轉換為 HSV 色彩空間
        hsv_zone = cv2.cvtColor(arrow_zone, cv2.COLOR_BGR2HSV)

        # PCRD 經典粉紅色在 HSV 中的範圍
        # H (色調): 130 - 175 (涵蓋偏品紅與亮粉紅)
        # S (飽和度): 50 - 255 (櫻花粉與桃紅飽和度通常較高)
        # V (亮度): 100 - 255 (亮粉紅色)
        lower_pink = np.array([130, 50, 100], dtype=np.uint8)
        upper_pink = np.array([175, 255, 255], dtype=np.uint8)

        # 取得粉紅色像素二值遮罩
        pink_mask = cv2.inRange(hsv_zone, lower_pink, upper_pink)

        # 計算粉紅像素佔比
        total_pixels = pink_mask.shape[0] * pink_mask.shape[1]
        pink_pixels = cv2.countNonZero(pink_mask)
        pink_ratio = pink_pixels / total_pixels

        # 尋找輪廓以進行幾何特徵分析
        contours, _ = cv2.findContours(pink_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        arrow_detected = False
        
        # 設定自適應輪廓面積限制 (基於監控區總面積的 0.3% 到 20% 之間)
        min_area = max(8, int(total_pixels * 0.003))
        max_area = int(total_pixels * 0.20)

        for contour in contours:
            area = cv2.contourArea(contour)
            if min_area <= area <= max_area:
                # 取得外接矩形
                x, y, cw, ch = cv2.boundingRect(contour)
                aspect_ratio = float(cw) / ch

                # 倒三角形的寬高比通常在 0.7 到 1.6 之間
                if 0.7 <= aspect_ratio <= 1.6:
                    # 計算凸包與輪廓面積比 (倒三角形通常是凸多邊形，凸包比例極高，接近 1.0)
                    hull = cv2.convexHull(contour)
                    hull_area = cv2.contourArea(hull)
                    solidity = float(area) / hull_area if hull_area > 0 else 0

                    # 進行多邊形近似，三角形近似頂點數偏低 (一般在 3 ~ 6 個點)
                    peri = cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, 0.08 * peri, True)

                    # 只要凸包實心度高，且形狀接近三角形/倒三角，即判定為 ▼ 箭頭
                    if solidity > 0.80 and len(approx) in [3, 4, 5]:
                        arrow_detected = True
                        logger.debug(f"找到符合特徵的粉紅箭頭：面積={area}, 寬高比={aspect_ratio:.2f}, 實心度={solidity:.2f}, 頂點數={len(approx)}")
                        break

        # 容錯降級機制：如果輪廓沒有完美通過形狀分析，但該區塊內亮粉紅色像素比例顯著 (例如 0.8% ~ 10% 之間)
        # 這有助於在低解析度或文字剛好重疊時，也能偵測到箭頭
        if not arrow_detected and 0.008 <= pink_ratio <= 0.10:
            arrow_detected = True
            logger.debug(f"觸發粉紅像素比例降級偵測機制，粉紅像素比={pink_ratio:.4f}")

        if arrow_detected:
            logger.info("偵測到 PCRD 粉紅箭頭 ▼ 顯示完成，系統標記為【可以翻譯狀態】！")
        
        return arrow_detected

    def preprocess_for_ocr(self, img: np.ndarray) -> np.ndarray:
        """
        OCR 專用影像預處理流水線
        進行灰階化、對比度增強與自適應二值化，有效提升日文字元提取率
        """
        if img is None:
            return None

        # 1. 灰階化
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 2. 自適應對比度增強 (CLAHE - Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # 3. 雙邊濾波去噪 (保留文字邊緣，濾除背景毛邊與噪點)
        denoised = cv2.bilateralFilter(enhanced, d=9, sigmaColor=75, sigmaSpace=75)

        # 4. 自適應二值化 (使用高斯加權，處理陰影或漸層背景對話框)
        binary = cv2.adaptiveThreshold(
            denoised, 
            255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 
            blockSize=15, 
            C=8
        )

        # 讓文字為黑色背景、白色前景 (如果 PaddleOCR 對這種極性有偏好，可以調整)
        # 通常 PaddleOCR 對原始影像或常規二值化均有極佳支援，這裡回傳清晰的二值化影像
        return binary

    def local_ocr(self, img: np.ndarray) -> tuple:
        """
        封裝本地 PaddleOCR 日文辨識功能
        傳回值: (recognized_text, confidence_score, recommend_vision_api)
        - recognized_text: 辨識出的日文台詞 (字串)
        - confidence_score: 辨識平均信心度 (float)
        - recommend_vision_api: 是否建議轉交 Vision API (bool)
        """
        if not PADDLE_AVAILABLE or self.ocr_engine is None:
            logger.debug("本地 OCR 不可用，將直接推薦轉交 Vision API。")
            return "", 0.0, True

        try:
            # 進行影像預處理，以提升辨識率
            preprocessed_img = self.preprocess_for_ocr(img)

            # 在二值化圖像上進行辨識，如果二值化效果不佳，也可以作為備用直接送原始圖
            # 為了保險起見，我們直接將預處理後的二值化影像送入 PaddleOCR
            # 註：PaddleOCR 在某些彩色場景下原始影像表現也很好，我們可以使用 cv2.cvtColor(preprocessed_img, cv2.COLOR_GRAY2BGR) 轉回三通道
            color_preprocessed = cv2.cvtColor(preprocessed_img, cv2.COLOR_GRAY2BGR)
            
            result = self.ocr_engine.ocr(color_preprocessed, cls=False)
            
            if not result or result[0] is None:
                logger.info("本地 OCR 辨識結果為空，推薦轉交 Vision API。")
                return "", 0.0, True

            text_lines = []
            confidence_sum = 0.0
            text_count = 0

            for line in result[0]:
                box, (text, conf) = line
                # 去除無意義字元與空格
                text = text.strip()
                if text:
                    text_lines.append(text)
                    confidence_sum += conf
                    text_count += 1

            if text_count == 0:
                return "", 0.0, True

            full_text = "\n".join(text_lines)
            avg_confidence = float(confidence_sum / text_count)
            
            # 取得 config 中的信心度門檻值
            threshold = getattr(config, 'LOCAL_OCR_CONFIDENCE_THRESHOLD', 0.85)
            recommend_vision = avg_confidence < threshold

            logger.info(f"本地 OCR 辨識結果: {full_text.replace(chr(10), ' ')} | 信心度: {avg_confidence:.4f} (閥值: {threshold}) | 建議 Vision: {recommend_vision}")
            return full_text, avg_confidence, recommend_vision

        except Exception as e:
            logger.error(f"本地 OCR 執行期間發生異常: {e}")
            return "", 0.0, True


# ==============================================================================
# 自我驗證測試模組 (僅於直接執行此指令碼時運作)
# ==============================================================================
if __name__ == "__main__":
    logger.info("啟動 ocr_vision.py 自我驗證測試程序...")
    
    # 1. 實例化偵測器
    detector = PCRDVisionDetector()

    # 2. 模擬生成一張 1280x720 的假遊戲畫面
    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    # 畫出假對話框區域 (背景為暗色，模擬遊戲中對話框)
    # DIALOG_BOX_RATIO: left 10%, top 70%, width 80%, height 20% -> 128x504 到 1152x648
    cv2.rectangle(dummy_frame, (128, 504), (1152, 648), (50, 40, 40), -1)
    
    # 在名字框區域畫上假說話者名字
    # SPEAKER_RATIO: left 15%, top 66%, width 20%, height 5% -> 192x475 到 448x511
    cv2.rectangle(dummy_frame, (192, 475), (448, 511), (70, 60, 60), -1)

    # 3. 測試裁剪功能
    cropped_dialog = detector.crop_dialog_box(dummy_frame)
    cropped_speaker = detector.crop_speaker(dummy_frame)

    if cropped_dialog is not None and cropped_dialog.shape[0] > 0:
        logger.info(f"【驗收成功】對話框裁剪正常，大小: {cropped_dialog.shape}")
    else:
        logger.error("【驗收失敗】對話框裁剪異常！")

    if cropped_speaker is not None and cropped_speaker.shape[0] > 0:
        logger.info(f"【驗收成功】說話者裁剪正常，大小: {cropped_speaker.shape}")
    else:
        logger.error("【驗收失敗】說話者裁剪異常！")

    # 4. 測試畫面變化過濾器 (Throttling)
    # 同一張圖比對，應該為 False
    changed_1 = detector.has_text_changed(cropped_dialog) # 第一次呼叫必定為 True
    changed_2 = detector.has_text_changed(cropped_dialog) # 第二次呼叫，完全一樣，應該為 False
    
    if changed_1 is True and changed_2 is False:
        logger.info("【驗收成功】畫面變化過濾器運作正常！完全相同畫面成功被過濾。")
    else:
        logger.error(f"【驗收失敗】畫面變化過濾器異常：首次={changed_1}, 二次={changed_2}")

    # 5. 測試粉紅箭頭監控 (在右下角畫一個假粉紅箭頭)
    # 對話框寬度 1024, 高度 144
    # 右下角子區域 (X: 85% ~ 98% -> 870 到 1003, Y: 55% ~ 95% -> 79 到 136)
    # 我們在該區域內畫一個粉紅色倒三角形
    h_c, w_c = cropped_dialog.shape[:2]
    arrow_center_x = int(w_c * 0.91)
    arrow_center_y = int(h_c * 0.75)
    
    # 繪製倒三角形 (經典粉紅色：BGR=[180, 105, 240])
    pts = np.array([
        [arrow_center_x - 12, arrow_center_y - 8], 
        [arrow_center_x + 12, arrow_center_y - 8], 
        [arrow_center_x, arrow_center_y + 12]
    ], np.int32)
    
    dialog_with_arrow = cropped_dialog.copy()
    cv2.drawContours(dialog_with_arrow, [pts], 0, (180, 105, 240), -1)

    has_arrow_dummy = detector.detect_pink_arrow(cropped_dialog) # 原圖應該無箭頭
    has_arrow_real = detector.detect_pink_arrow(dialog_with_arrow) # 有畫箭頭的圖應該有箭頭

    if has_arrow_dummy is False and has_arrow_real is True:
        logger.info("【驗收成功】粉紅箭頭 ▼ 偵測演算法運作正常！")
    else:
        logger.error(f"【驗收失敗】粉紅箭頭偵測異常：無箭頭幀={has_arrow_dummy}, 有箭頭幀={has_arrow_real}")

    # 6. 測試影像預處理功能
    preprocessed = detector.preprocess_for_ocr(cropped_dialog)
    if preprocessed is not None and len(preprocessed.shape) == 2:
        logger.info("【驗收成功】OCR 影像預處理（灰階二值化）正常！")
    else:
        logger.error("【驗收失敗】OCR 影像預處理異常！")

    logger.info("所有自我驗證測試程序執行完畢。")
