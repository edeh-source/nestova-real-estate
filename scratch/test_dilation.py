import os
import cv2
import numpy as np
import requests

IMG3_URL = "https://images.propertypro.ng/large/1-bedroom-apartment-M14NJvgc0DSZrmNYGNpE.jpeg"
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Nestova/1.0)'}
OUT_DIR = r'c:\Users\htdocs\nestova\media\watermark_test'

import sys
sys.path.insert(0, r'c:\Users\htdocs\nestova')
from bookings.image_processor import _get_canonical_mask

def run():
    raw = requests.get(IMG3_URL, headers=HEADERS, timeout=15).content
    nparr = np.frombuffer(raw, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    
    y_top = int(h * 0.41)
    y_bot = int(h * 0.59)
    band_height = y_bot - y_top
    
    canonical = _get_canonical_mask()
    resized_band_mask = cv2.resize(canonical, (w, band_height), interpolation=cv2.INTER_NEAREST)
    
    # Base mask
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[y_top:y_bot, :] = resized_band_mask
    
    # Dilated 1
    kernel = np.ones((3,3), np.uint8)
    dilated_1 = cv2.dilate(full_mask, kernel, iterations=1)
    
    # Dilated 2
    dilated_2 = cv2.dilate(full_mask, kernel, iterations=2)
    
    # Try combinations
    res_NS_base = cv2.inpaint(img, full_mask, inpaintRadius=3, flags=cv2.INPAINT_NS)
    res_NS_dil1 = cv2.inpaint(img, dilated_1, inpaintRadius=5, flags=cv2.INPAINT_NS)
    res_NS_dil2 = cv2.inpaint(img, dilated_2, inpaintRadius=7, flags=cv2.INPAINT_NS)
    
    res_TEL_dil1 = cv2.inpaint(img, dilated_1, inpaintRadius=5, flags=cv2.INPAINT_TELEA)
    res_TEL_dil2 = cv2.inpaint(img, dilated_2, inpaintRadius=7, flags=cv2.INPAINT_TELEA)
    
    cv2.imwrite(os.path.join(OUT_DIR, "v13_NS_base.jpg"), res_NS_base)
    cv2.imwrite(os.path.join(OUT_DIR, "v13_NS_dil1.jpg"), res_NS_dil1)
    cv2.imwrite(os.path.join(OUT_DIR, "v13_NS_dil2.jpg"), res_NS_dil2)
    cv2.imwrite(os.path.join(OUT_DIR, "v13_TEL_dil1.jpg"), res_TEL_dil1)
    cv2.imwrite(os.path.join(OUT_DIR, "v13_TEL_dil2.jpg"), res_TEL_dil2)
    print("Done")

if __name__ == '__main__':
    run()
