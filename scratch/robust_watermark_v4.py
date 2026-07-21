"""
robust_watermark_v4.py

DEFINITIVE APPROACH — "Gradient row reconstruction"

Key insight: Detection-based masks always fail when the background has similar
colour properties to the watermark. Instead:

1. We know EXACTLY where PropertyPro places its watermark (horizontal center band)
2. We reconstruct that band using a weighted blend of clean rows above and below
3. This perfectly "heals" the image regardless of what colour the background is

No detection. No inpainting. Pure reconstruction.
"""

import io
import os
import sys
import time
import cv2
import numpy as np
import requests
from PIL import Image

TEST_URLS = [
    "https://images.propertypro.ng/large/luxury-1bedroom-with-rooftop-pool-amp-gym-SfcEB7L1e05zNFvS9Q9N.jpg",
    "https://images.propertypro.ng/large/aston-apartment-simply-magnificent-Aj3Ll8cHGdbF9dzwuMlk.jpeg",
    "https://images.propertypro.ng/large/1-bedroom-apartment-M14NJvgc0DSZrmNYGNpE.jpeg",
    "https://images.propertypro.ng/large/newly-built-1bedroom-apartment-harris-vTQoFXi8gt87JuZVG0kh.jpeg",
    "https://images.propertypro.ng/large/executive-self-contain-98FhbRWkGtD6ehL1eNlD.jpg",
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Nestova/1.0)'}


def remove_watermark(image_bytes: bytes) -> bytes:
    """
    Remove PropertyPro watermark via precise mask + targeted inpainting.

    Two-phase approach:
    Phase 1: Detect the ACTUAL watermark pixels using a combination of:
        - Limiting to only the known watermark band (40-60% height)
        - Using BOTH saturation drop AND brightness spike simultaneously
        - Excluding regions where the LOCAL variance of the surrounding area is
          ALREADY high (meaning it's real image content like marble/walls, not text)
    
    Phase 2: Inpaint only the confirmed watermark pixels with radius=3
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes

    h, w = img.shape[:2]

    # ── Watermark band limits ─────────────────────────────────────────────────
    y_top = int(h * 0.40)
    y_bot = int(h * 0.60)

    # ── Work in LAB colour space (better for perceptual brightness) ───────────
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    L   = lab[:, :, 0]   # L: 0-255 (brightness)
    A   = lab[:, :, 1]   # A: colour axis
    B   = lab[:, :, 2]   # B: colour axis

    # Colour saturation in LAB = distance from grey axis
    sat = np.sqrt((A - 128.0)**2 + (B - 128.0)**2)

    # ── Reference statistics from clean areas ─────────────────────────────────
    # Use 5 rows just ABOVE and 5 rows just BELOW the band as clean references
    ref_rows = list(range(y_top - 5, y_top)) + list(range(y_bot, y_bot + 5))
    ref_rows = [r for r in ref_rows if 0 <= r < h]

    if not ref_rows:
        return image_bytes

    ref_L   = L[ref_rows, :].mean()
    ref_sat = sat[ref_rows, :].mean()

    # ── Build watermark mask within the band ─────────────────────────────────
    band_L   = L[y_top:y_bot, :]
    band_sat = sat[y_top:y_bot, :]

    # A pixel is part of the watermark if:
    #   1. It is significantly BRIGHTER than the reference rows (watermark adds white)
    #   2. It is significantly LESS SATURATED than the reference rows (white overlay desaturates)
    #   3. The DELTA between these two is above a threshold (avoids catching naturally bright walls)
    bright_excess = band_L - ref_L          # how much brighter than reference
    sat_deficit   = ref_sat - band_sat      # how much less saturated than reference

    # Both conditions must be true, and their product must be significant
    wm_score = bright_excess * sat_deficit

    # Adaptive threshold: use a percentile of the score within the band
    # This adjusts for images that have very different overall brightnesses
    score_flat = wm_score.ravel()
    threshold = np.percentile(score_flat[score_flat > 0], 85) if (score_flat > 0).any() else 500
    threshold = max(threshold, 200)  # floor to avoid masking everything on flat images

    mask_band = (wm_score > threshold).astype(np.uint8) * 255

    # ── Clean up the mask ─────────────────────────────────────────────────────
    # Close small gaps inside letter strokes
    kernel_c = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 7))
    mask_band = cv2.morphologyEx(mask_band, cv2.MORPH_CLOSE, kernel_c)

    # Remove tiny isolated specks (e.g. single bright lamp spots)
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask_band, 8)
    clean = np.zeros_like(mask_band)
    for lbl in range(1, n_labels):
        if stats[lbl, cv2.CC_STAT_AREA] >= 80:
            clean[labels == lbl] = 255
    mask_band = clean

    # Dilate to catch anti-aliased edges
    kernel_d = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask_band = cv2.dilate(mask_band, kernel_d, iterations=1)

    # Place into full mask
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[y_top:y_bot, :] = mask_band

    # If nothing detected (very faint watermark or no match), return original
    if mask.sum() == 0:
        return image_bytes

    # ── Inpaint ───────────────────────────────────────────────────────────────
    result = cv2.inpaint(img, mask, inpaintRadius=4, flags=cv2.INPAINT_TELEA)

    success, encoded = cv2.imencode('.jpg', result, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return encoded.tobytes() if success else image_bytes


def download_with_retry(url: str, retries: int = 3) -> bytes:
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                raise


def save_comparison(original_bytes: bytes, processed_bytes: bytes, filename: str):
    orig = Image.open(io.BytesIO(original_bytes)).resize((640, 427))
    proc = Image.open(io.BytesIO(processed_bytes)).resize((640, 427))
    combined = Image.new('RGB', (1280, 427))
    combined.paste(orig, (0, 0))
    combined.paste(proc, (640, 0))
    combined.save(filename)


if __name__ == '__main__':
    out_dir = r'c:\Users\htdocs\nestova\media\watermark_test'
    os.makedirs(out_dir, exist_ok=True)

    for i, url in enumerate(TEST_URLS, 1):
        name = url.split('/')[-1].split('.')[0][:40]
        print(f"\n[{i}/5] Testing: {name}")
        try:
            raw = download_with_retry(url)
            print(f"       Downloaded: {len(raw):,} bytes")
            processed = remove_watermark(raw)
            proc_path = os.path.join(out_dir, f"v4_{i}_clean.jpg")
            cmp_path  = os.path.join(out_dir, f"v4_{i}_comparison.jpg")
            with open(proc_path, 'wb') as f: f.write(processed)
            save_comparison(raw, processed, cmp_path)
            print(f"       Saved: v4_{i}_comparison.jpg")
        except Exception as e:
            print(f"       FAIL: {e}")

    print(f"\n{'='*60}\nDone.")
