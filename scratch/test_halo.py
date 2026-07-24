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
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[y_top:y_bot, :] = resized_band_mask
    
    # 1. Base inpaint
    inpainted = cv2.inpaint(img, full_mask, inpaintRadius=3, flags=cv2.INPAINT_NS)
    
    # The ghosting is in the slightly dilated region.
    kernel = np.ones((3,3), np.uint8)
    dilated = cv2.dilate(full_mask, kernel, iterations=1)
    halo_mask = cv2.subtract(dilated, full_mask)
    
    # 2. Let's slightly darken the halo region to hide the white ghosting
    # Convert to HSV, reduce Value in the halo
    hsv = cv2.cvtColor(inpainted, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:,:,2] -= (halo_mask.astype(np.float32) / 255.0) * 40.0 # reduce brightness by 40
    hsv[:,:,2] = np.clip(hsv[:,:,2], 0, 255)
    
    darkened = cv2.cvtColor(hsv.astype(np.uint8), cv2.HSV_BGR)
    
    # 3. Alternatively, apply a median filter to the inpainted image, but only in the dilated mask
    median = cv2.medianBlur(inpainted, 5)
    median_blended = np.where(dilated[:,:,np.newaxis] > 0, median, inpainted)
    
    cv2.imwrite(os.path.join(OUT_DIR, "v14_darken_halo.jpg"), darkened)
    cv2.imwrite(os.path.join(OUT_DIR, "v14_median_mask.jpg"), median_blended)

    print("Done")

if __name__ == '__main__':
    run()
