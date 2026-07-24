import os
import cv2
import numpy as np
import requests
import base64

IMG3_URL = "https://images.propertypro.ng/large/1-bedroom-apartment-M14NJvgc0DSZrmNYGNpE.jpeg"
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Nestova/1.0)'}
OUT_DIR = r'c:\Users\htdocs\nestova\media\watermark_test'

def run():
    raw = requests.get(IMG3_URL, headers=HEADERS, timeout=15).content
    nparr = np.frombuffer(raw, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    y_top = int(h * 0.40)
    y_bot = int(h * 0.60)
    
    # 1. v8 (Crop, no stretch)
    top = img[:y_top, :]
    bot = img[y_bot:, :]
    v8 = np.vstack((top, bot))
    cv2.imwrite(os.path.join(OUT_DIR, "opt1_crop_no_stretch.jpg"), v8)
    
    # 2. v12 (Crop + stretch)
    v12 = cv2.resize(v8, (w, h), interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(os.path.join(OUT_DIR, "opt2_crop_stretch.jpg"), v12)
    
    # 3. v11d (Inpainting)
    import sys
    sys.path.insert(0, r'c:\Users\htdocs\nestova')
    from bookings.image_processor import process_image_bytes
    v11d_raw = process_image_bytes(raw, stamp_nestova=False)
    v11d = cv2.imdecode(np.frombuffer(v11d_raw, np.uint8), cv2.IMREAD_COLOR)
    cv2.imwrite(os.path.join(OUT_DIR, "opt3_inpainting.jpg"), v11d)
    
    # 4. v9 (Blur + Stamp)
    v9 = img.copy()
    band = v9[y_top:y_bot, :]
    v9[y_top:y_bot, :] = cv2.GaussianBlur(band, (99, 99), 0)
    # Just draw a fake Nestova stamp for demonstration
    cv2.putText(v9, "NESTOVA", (w//2 - 100, (y_top+y_bot)//2), cv2.FONT_HERSHEY_SIMPLEX, 2, (255,255,255), 3, cv2.LINE_AA)
    cv2.imwrite(os.path.join(OUT_DIR, "opt4_blur_stamp.jpg"), v9)
    
    print("Generated 4 options.")

if __name__ == '__main__':
    run()
