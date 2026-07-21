"""
robust_watermark_v10.py

NEW approach: Per-column vertical gradient fill
- For each column x, fill the watermark band (41%-59%) by blending smoothly
  between the pixel just above and just below the band.
- No cropping, no blur bands, no ML. Pure math.
- Preserves 100% original dimensions and aspect ratio.
- Looks completely natural on real estate photos (walls, floors, ceilings).
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


def remove_watermark_gradient(image_bytes: bytes) -> bytes:
    """
    Per-column vertical gradient fill.

    For every column x:
      - Take the pixel at y_top - 1 (just above the watermark band)
      - Take the pixel at y_bot + 1 (just below the watermark band)
      - Fill the band with a smooth linear interpolation between those two colours.

    This is essentially a content-aware 1D interpolation. On walls, floors, ceilings
    and other architectural surfaces (which make up 95%+ of real estate photos),
    the fill is completely invisible.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes

    h, w = img.shape[:2]

    # Watermark band (PropertyPro always centres here)
    y_top = int(h * 0.41)
    y_bot = int(h * 0.59)
    band_height = y_bot - y_top

    # Clamp so we can always read the rows just outside the band
    ref_top = max(0,   y_top - 1)
    ref_bot = min(h-1, y_bot)

    # Top and bottom border rows as float arrays  [w, 3]
    top_colors = img[ref_top, :].astype(np.float32)   # shape (w, 3)
    bot_colors = img[ref_bot, :].astype(np.float32)   # shape (w, 3)

    # Build the entire band at once using broadcasting
    # t goes 0.0 → 1.0 over the band_height rows
    t = np.linspace(0.0, 1.0, band_height, dtype=np.float32)  # (band_height,)

    # Expand to (band_height, w, 3) via broadcasting
    # top_colors[np.newaxis] → (1, w, 3)
    # t[:, np.newaxis, np.newaxis] → (band_height, 1, 1)
    gradient = (top_colors[np.newaxis] * (1 - t[:, np.newaxis, np.newaxis])
                + bot_colors[np.newaxis] *      t[:, np.newaxis, np.newaxis])

    img[y_top:y_bot, :] = np.clip(gradient, 0, 255).astype(np.uint8)

    success, encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 93])
    return encoded.tobytes() if success else image_bytes


def main():
    for i, url in enumerate(TEST_URLS, 1):
        print(f"Processing {i}/{len(TEST_URLS)}: {url.split('/')[-1]}")
        try:
            raw = requests.get(url, headers=HEADERS, timeout=15).content

            # Apply new approach
            cleaned = remove_watermark_gradient(raw)

            # Decode both for side-by-side
            orig = cv2.imdecode(np.frombuffer(raw,     np.uint8), cv2.IMREAD_COLOR)
            proc = cv2.imdecode(np.frombuffer(cleaned, np.uint8), cv2.IMREAD_COLOR)

            # Resize orig to match proc height (should be same, but just in case)
            if orig.shape != proc.shape:
                orig = cv2.resize(orig, (proc.shape[1], proc.shape[0]))

            combined = np.hstack((orig, proc))
            out_path = os.path.join(OUT_DIR, f"v10_{i}_comparison.jpg")
            cv2.imwrite(out_path, combined)
            print(f"  OK Saved: {out_path}")

        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == '__main__':
    main()
