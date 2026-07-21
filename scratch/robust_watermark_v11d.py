"""
robust_watermark_v11d.py

Using a RAZOR-THIN STATIC MASK with Navier-Stokes inpainting.
The previous static mask was dilated too much, creating a fat mask that forced
the inpainting algorithm to guess over a large area, causing "ghost text".
By keeping the mask as thin as possible (hugging the actual white pixels),
inpainting can easily bridge the small gaps and leave almost no ghosting.
"""

import os
import cv2
import numpy as np
import requests

TEST_URLS = [
    "https://images.propertypro.ng/large/luxury-1bedroom-with-rooftop-pool-amp-gym-SfcEB7L1e05zNFvS9Q9N.jpg",
    "https://images.propertypro.ng/large/aston-apartment-simply-magnificent-Aj3Ll8cHGdbF9dzwuMlk.jpeg",
    "https://images.propertypro.ng/large/1-bedroom-apartment-M14NJvgc0DSZrmNYGNpE.jpeg",
    "https://images.propertypro.ng/large/newly-built-1bedroom-apartment-harris-vTQoFXi8gt87JuZVG0kh.jpeg",
    "https://images.propertypro.ng/large/executive-self-contain-98FhbRWkGtD6ehL1eNlD.jpg",
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Nestova/1.0)'}
OUT_DIR  = r'c:\Users\htdocs\nestova\media\watermark_test'
os.makedirs(OUT_DIR, exist_ok=True)

def generate_thin_static_mask(w, h):
    masks = []
    for url in TEST_URLS:
        raw = requests.get(url, headers=HEADERS, timeout=15).content
        nparr = np.frombuffer(raw, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None: continue
        
        img = cv2.resize(img, (800, 600))
        y_top = int(600 * 0.41)
        y_bot = int(600 * 0.59)
        
        band_hsv = cv2.cvtColor(img[y_top:y_bot, :], cv2.COLOR_BGR2HSV).astype(np.float32)
        band_v = band_hsv[:, :, 2]
        blurred_v = cv2.GaussianBlur(band_v, (51, 51), 0)
        diff_v = band_v - blurred_v
        
        band_s = band_hsv[:, :, 1]
        blurred_s = cv2.GaussianBlur(band_s, (51, 51), 0)
        diff_s = blurred_s - band_s
        
        bright_mask = diff_v > 15
        desat_mask  = diff_s > 5
        wm = (bright_mask & desat_mask).astype(np.uint8) * 255
        masks.append(wm)
        
    masks = np.array(masks)
    consensus = np.sum(masks == 255, axis=0)
    static_band_mask = (consensus >= 3).astype(np.uint8) * 255
    
    # Do NOT dilate 3 times with 5x5. 
    # Just dilate ONCE with a 3x3 to cover the very edge anti-aliasing.
    kernel = np.ones((3, 3), np.uint8)
    static_band_mask = cv2.dilate(static_band_mask, kernel, iterations=1)
    
    def get_mask_for_size(target_w, target_h):
        full_mask = np.zeros((target_h, target_w), dtype=np.uint8)
        y_top = int(target_h * 0.41)
        y_bot = int(target_h * 0.59)
        band_height = y_bot - y_top
        
        resized_band = cv2.resize(static_band_mask, (target_w, band_height), interpolation=cv2.INTER_NEAREST)
        full_mask[y_top:y_bot, :] = resized_band
        return full_mask
        
    return get_mask_for_size

def main():
    print("Generating THIN static consensus mask...")
    get_mask_fn = generate_thin_static_mask(800, 600)
    
    # Save the canonical mask just to see it
    cv2.imwrite(os.path.join(OUT_DIR, "v11d_canonical_mask.jpg"), get_mask_fn(800, 600))

    for i, url in enumerate(TEST_URLS, 1):
        print(f"Processing {i}/{len(TEST_URLS)}: {url.split('/')[-1]}")
        try:
            raw = requests.get(url, headers=HEADERS, timeout=15).content
            nparr = np.frombuffer(raw, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            h, w = img.shape[:2]
            mask = get_mask_fn(w, h)
            
            # Use Navier-Stokes (NS) which is often better at preserving edges, 
            # and a small radius since the mask is thin.
            result = cv2.inpaint(img, mask, inpaintRadius=3, flags=cv2.INPAINT_NS)

            orig = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            combined = np.hstack((orig, result))
            out_path = os.path.join(OUT_DIR, f"v11d_{i}_comparison.jpg")
            cv2.imwrite(out_path, combined)
            print(f"  OK Saved: {out_path}")

        except Exception as e:
            print(f"  ERROR: {e}")

if __name__ == '__main__':
    main()
