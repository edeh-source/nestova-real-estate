"""
robust_watermark_v11b.py

Improved v11: smarter watermark mask using BOTH brightness AND desaturation.

The PropertyPro watermark is a semi-transparent WHITE overlay. White has:
  - High Value (V) in HSV
  - Low Saturation (S) in HSV

Natural bright objects (lamps, windows, white walls) have high V but can
also have low S — so brightness alone is unreliable.

The KEY insight: the watermark makes pixels both BRIGHTER and LESS SATURATED
than their local neighbourhood. We detect pixels where:
  1. Brightness is >= 20 points above local average (same as v11)
  2. AND Saturation is <= 30 points below local average

This dual condition is much more selective and avoids catching furniture,
art, or other naturally bright/colourful content.
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


def remove_watermark_v11b(image_bytes: bytes) -> bytes:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes

    h, w = img.shape[:2]

    # Watermark band
    y_top = int(h * 0.41)
    y_bot = int(h * 0.59)

    band_bgr = img[y_top:y_bot, :].astype(np.float32)
    band_hsv = cv2.cvtColor(img[y_top:y_bot, :], cv2.COLOR_BGR2HSV).astype(np.float32)

    # ── Value (brightness) channel ──────────────────────────────────────────
    band_v = band_hsv[:, :, 2]
    blurred_v = cv2.GaussianBlur(band_v, (101, 101), 0)
    diff_v = band_v - blurred_v          # positive = brighter than neighbours

    # ── Saturation channel ──────────────────────────────────────────────────
    band_s = band_hsv[:, :, 1]
    blurred_s = cv2.GaussianBlur(band_s, (101, 101), 0)
    diff_s = blurred_s - band_s          # positive = less saturated than neighbours

    # ── Dual condition mask ─────────────────────────────────────────────────
    # Pixel is watermark if it's BOTH brighter AND less saturated than surroundings
    bright_mask = diff_v > 20
    desat_mask  = diff_s > 10
    watermark_mask = (bright_mask & desat_mask).astype(np.uint8) * 255

    # Dilate to cover anti-aliasing edges
    kernel = np.ones((7, 7), np.uint8)
    watermark_mask = cv2.dilate(watermark_mask, kernel, iterations=2)

    # ── Full-image mask ─────────────────────────────────────────────────────
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[y_top:y_bot, :] = watermark_mask

    # ── Inpaint ─────────────────────────────────────────────────────────────
    result = cv2.inpaint(img, full_mask, inpaintRadius=15, flags=cv2.INPAINT_TELEA)

    success, encoded = cv2.imencode('.jpg', result, [cv2.IMWRITE_JPEG_QUALITY, 93])
    return encoded.tobytes() if success else image_bytes


def main():
    for i, url in enumerate(TEST_URLS, 1):
        print(f"Processing {i}/{len(TEST_URLS)}: {url.split('/')[-1]}")
        try:
            raw = requests.get(url, headers=HEADERS, timeout=15).content

            cleaned = remove_watermark_v11b(raw)

            orig = cv2.imdecode(np.frombuffer(raw,     np.uint8), cv2.IMREAD_COLOR)
            proc = cv2.imdecode(np.frombuffer(cleaned, np.uint8), cv2.IMREAD_COLOR)

            # Save mask for inspection
            nparr2 = np.frombuffer(raw, np.uint8)
            img_tmp = cv2.imdecode(nparr2, cv2.IMREAD_COLOR)
            hh, ww = img_tmp.shape[:2]
            y_top = int(hh * 0.41)
            y_bot = int(hh * 0.59)
            band_hsv = cv2.cvtColor(img_tmp[y_top:y_bot, :], cv2.COLOR_BGR2HSV).astype(np.float32)
            band_v = band_hsv[:, :, 2]
            blurred_v = cv2.GaussianBlur(band_v, (101, 101), 0)
            diff_v = band_v - blurred_v
            band_s = band_hsv[:, :, 1]
            blurred_s = cv2.GaussianBlur(band_s, (101, 101), 0)
            diff_s = blurred_s - band_s
            bright_mask = diff_v > 20
            desat_mask  = diff_s > 10
            wm = ((bright_mask & desat_mask).astype(np.uint8) * 255)
            kernel = np.ones((7, 7), np.uint8)
            wm = cv2.dilate(wm, kernel, iterations=2)
            mask_vis = np.zeros((hh, ww), dtype=np.uint8)
            mask_vis[y_top:y_bot, :] = wm
            cv2.imwrite(os.path.join(OUT_DIR, f"v11b_{i}_mask.jpg"), mask_vis)

            combined = np.hstack((orig, proc))
            out_path = os.path.join(OUT_DIR, f"v11b_{i}_comparison.jpg")
            cv2.imwrite(out_path, combined)
            print(f"  OK Saved: {out_path}")

        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == '__main__':
    main()
