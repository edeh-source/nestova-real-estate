"""
robust_watermark_v11.py

IMPROVED approach: Smart patch-based reconstruction
- For each column x, sample multiple rows ABOVE and BELOW the watermark band
- Use a weighted average of nearby pixels (closer = more weight) to fill the band
- This handles cases where the pixel just above/below is an edge or bright object
- Preserves 100% original dimensions and aspect ratio
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


def remove_watermark_smart(image_bytes: bytes) -> bytes:
    """
    Uses OpenCV inpainting (TELEA algorithm) with a precisely detected mask.

    Key improvement over previous attempts:
    - We only mask pixels in the center band that are BRIGHTER THAN THEIR
      LOCAL NEIGHBOURHOOD (not just absolutely bright).
    - This detects the semi-transparent white overlay effect without catching
      naturally bright walls or windows.
    - We compare each pixel against a heavily blurred version of the same band
      to find pixels that are anomalously bright vs their local surroundings.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes

    h, w = img.shape[:2]

    y_top = int(h * 0.41)
    y_bot = int(h * 0.59)
    band_height = y_bot - y_top

    # ── Step 1: Build a precise watermark mask ──────────────────────────────
    # Convert to grayscale just in the band
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    band_gray = gray[y_top:y_bot, :]

    # Blur heavily to get the "expected" brightness of the local region
    blurred = cv2.GaussianBlur(band_gray, (101, 101), 0)

    # Find pixels significantly brighter than their local background
    # (the semi-transparent white watermark lifts brightness by ~40-80 points)
    diff = band_gray - blurred

    # Threshold: pixels >25 brighter than their local context are watermark
    watermark_band_mask = (diff > 25).astype(np.uint8) * 255

    # Also catch the watermark logo (circle icon) on the left
    # The logo area typically has high contrast, so widen mask horizontally
    # by also including ANY bright pixel in the known text-height region
    text_zone = band_gray[int(band_height*0.2):int(band_height*0.8), :]
    blurred_text = cv2.GaussianBlur(text_zone, (51, 51), 0)
    text_diff = text_zone - blurred_text
    text_mask = (text_diff > 15).astype(np.uint8) * 255

    watermark_band_mask[int(band_height*0.2):int(band_height*0.8), :] = np.maximum(
        watermark_band_mask[int(band_height*0.2):int(band_height*0.8), :],
        text_mask
    )

    # Dilate mask to cover anti-aliasing and semi-transparent edges
    kernel = np.ones((5, 5), np.uint8)
    watermark_band_mask = cv2.dilate(watermark_band_mask, kernel, iterations=3)

    # ── Step 2: Place band mask into full-image mask ────────────────────────
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[y_top:y_bot, :] = watermark_band_mask

    # ── Step 3: Inpaint ─────────────────────────────────────────────────────
    # Use a moderate radius — inpainting with a precise mask needs less radius
    result = cv2.inpaint(img, full_mask, inpaintRadius=12, flags=cv2.INPAINT_TELEA)

    success, encoded = cv2.imencode('.jpg', result, [cv2.IMWRITE_JPEG_QUALITY, 93])
    return encoded.tobytes() if success else image_bytes


def main():
    for i, url in enumerate(TEST_URLS, 1):
        print(f"Processing {i}/{len(TEST_URLS)}: {url.split('/')[-1]}")
        try:
            raw = requests.get(url, headers=HEADERS, timeout=15).content

            cleaned = remove_watermark_smart(raw)

            orig = cv2.imdecode(np.frombuffer(raw,     np.uint8), cv2.IMREAD_COLOR)
            proc = cv2.imdecode(np.frombuffer(cleaned, np.uint8), cv2.IMREAD_COLOR)

            combined = np.hstack((orig, proc))
            out_path = os.path.join(OUT_DIR, f"v11_{i}_comparison.jpg")
            cv2.imwrite(out_path, combined)
            print(f"  OK Saved: {out_path}")

        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == '__main__':
    main()
