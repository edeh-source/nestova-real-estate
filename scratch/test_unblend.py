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
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR).astype(np.float32)
    h, w = img.shape[:2]
    
    y_top = int(h * 0.41)
    y_bot = int(h * 0.59)
    band_height = y_bot - y_top
    
    canonical = _get_canonical_mask()
    resized_band_mask = cv2.resize(canonical, (w, band_height), interpolation=cv2.INTER_NEAREST)
    
    # Base mask
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[y_top:y_bot, :] = resized_band_mask
    
    # The mask contains values 0 or 255.
    # Convert mask to float 0.0 - 1.0
    alpha_mask = (full_mask.astype(np.float32) / 255.0)
    
    # Try different max alpha values for the watermark
    # (If the watermark was applied at 50% opacity, true alpha is 0.5)
    for target_alpha in [0.4, 0.5, 0.6, 0.7, 0.8]:
        a = alpha_mask * target_alpha
        a = a[:, :, np.newaxis] # broadcast to 3 channels
        
        # P_watermarked = P_original * (1 - a) + 255 * a
        # P_original = (P_watermarked - 255 * a) / (1 - a)
        
        # Avoid division by zero by clamping denominator
        denom = np.clip(1 - a, 0.01, 1.0)
        
        restored = (img - 255.0 * a) / denom
        
        # Clip and convert back
        restored = np.clip(restored, 0, 255).astype(np.uint8)
        
        # Also do a slight blur on the restored area to hide noise
        # but let's see raw first
        out_name = os.path.join(OUT_DIR, f"unblend_alpha_{target_alpha}.jpg")
        cv2.imwrite(out_name, restored)
        
    print("Done")

if __name__ == '__main__':
    run()
