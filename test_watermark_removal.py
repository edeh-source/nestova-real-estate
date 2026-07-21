#!/usr/bin/env python3
"""
test_watermark_removal.py
──────────────────────────────────────────────────────────────────────
Standalone test for the watermark removal pipeline.
NO Django, NO Cloudinary, NO database required.

Saves three files side by side so you can compare:
  watermark_BEFORE.jpg  — original image
  watermark_MASK.jpg    — detection mask (red = what gets inpainted; green
                          lines = search band boundaries)
  watermark_AFTER.jpg   — cleaned result

USAGE
──────
  # Built-in sample PropertyPro image (no argument needed):
  python test_watermark_removal.py

  # Any PropertyPro URL:
  python test_watermark_removal.py "https://storage.googleapis.com/...jpg"

  # Local file:
  python test_watermark_removal.py --file my_photo.jpg

REQUIREMENTS  (install once)
────────────────────────────
  pip install opencv-python pillow requests
  (Linux/Render: pip install opencv-python-headless pillow requests)
"""

import argparse
import os
import sys

import cv2
import numpy as np
import requests

# ── Tuning knobs (must match image_processor.py) ─────────────────────────────
_WM_SAT_MAX   = 20    # HSV saturation ceiling
_WM_VAL_MIN   = 150   # HSV value floor
_WM_BAND_TOP  = 0.33  # search band top  (fraction of height)
_WM_BAND_BOT  = 0.52  # search band bottom
_WM_INPAINT_R = 7     # inpaint radius (px)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_TEST_URL = (
    "https://storage.googleapis.com/eden-africa/production/listing_images/"
    "image_5c77c66c-4c9f-4f95-9893-c0c820c82b77.jpg"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://propertypro.ng/",
}


# ─────────────────────────────────────────────────────────────────────────────
# WATERMARK REMOVAL
# ─────────────────────────────────────────────────────────────────────────────

def remove_watermark(raw_bytes: bytes, debug_mask_path: str = None) -> bytes:
    """
    Erase the PropertyPro.ng watermark using HSV-saturation masking.

    v2 fix (over the broken v1):
    ────────────────────────────
    v1 used inRange([150,150,150], [255,255,255]) in BGR space — that's ANY
    bright pixel, which caught cream furniture + kitchen backsplash + bed linen
    and caused large dark-smear artefacts when inpainting those areas.

    v2 key changes:
      1. Work in HSV, filter on SATURATION (not just brightness).
            Watermark text: near-neutral white → S ≈ 0–15, V > 150
            Warm furniture: cream/amber        → S ≈ 20–80  (excluded)
            Kitchen tiles:  slight warm tint   → S ≈ 20–40  (excluded)
      2. Narrow the search band to 33–52 % of image height.
            Row scan shows PropertyPro watermark peaks at 38–46 %.
            Old band went to 60–67 %, catching white bed linen at 68 %+.
      3. Erode → dilate instead of dilate only:
            erode(1) kills isolated single-pixel noise first,
            dilate(2) re-fills anti-aliased stroke edges.

    Parameters
    ----------
    raw_bytes       : Raw JPEG/PNG image bytes.
    debug_mask_path : If given, saves a visualisation of the detection mask
                      (red pixels = will be inpainted; green lines = band).
    """
    nparr = np.frombuffer(raw_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        print("  ⚠  cv2.imdecode returned None — image bytes may be corrupt.")
        return raw_bytes

    h, w = img.shape[:2]
    print(f"  Image size: {w} × {h} px")

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    y0 = int(h * _WM_BAND_TOP)
    y1 = int(h * _WM_BAND_BOT)
    roi     = img[y0:y1]
    roi_hsv = hsv[y0:y1]

    # Near-neutral white: any hue, low saturation, high brightness
    lower = np.array([0,           0, _WM_VAL_MIN], dtype=np.uint8)
    upper = np.array([180, _WM_SAT_MAX,        255], dtype=np.uint8)
    mask  = cv2.inRange(roi_hsv, lower, upper)

    # erode → remove isolated noise; dilate → restore stroke coverage
    k    = np.ones((3, 3), np.uint8)
    mask = cv2.erode(mask,  k, iterations=1)
    mask = cv2.dilate(mask, k, iterations=2)

    nonzero = cv2.countNonZero(mask)
    band_px = w * (y1 - y0)
    print(f"  Search band: y={y0}–{y1} ({_WM_BAND_TOP:.0%}–{_WM_BAND_BOT:.0%} of height)")
    print(f"  Mask pixels: {nonzero:,} ({100*nonzero/band_px:.1f}% of band)")

    # ── Save debug mask visualisation ──────────────────────────────────────
    if debug_mask_path:
        vis = img.copy()
        full_mask = np.zeros((h, w), dtype=np.uint8)
        full_mask[y0:y1] = mask
        vis[full_mask > 0] = [0, 0, 220]              # red = will be inpainted
        cv2.line(vis, (0, y0), (w, y0), (0, 200, 0), 2)   # green band top
        cv2.line(vis, (0, y1), (w, y1), (0, 200, 0), 2)   # green band bottom
        cv2.imwrite(debug_mask_path, vis)
        print(f"  ✓ Mask saved → {os.path.abspath(debug_mask_path)}")

    if nonzero < 50:
        print("  ⚠  Very few mask pixels — returning original unchanged.")
        return raw_bytes

    inpainted     = cv2.inpaint(roi, mask, inpaintRadius=_WM_INPAINT_R,
                                 flags=cv2.INPAINT_TELEA)
    img[y0:y1, :] = inpainted

    ok, encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if ok:
        print("  ✓ Inpainting complete")
    return encoded.tobytes() if ok else raw_bytes


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def download(url: str) -> bytes:
    print(f"  Downloading: {url[:90]}")
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    print(f"  ✓ {len(r.content) // 1024} KB received  (HTTP {r.status_code})")
    return r.content


def save(data: bytes, path: str) -> None:
    with open(path, "wb") as f:
        f.write(data)
    print(f"  ✓ Saved → {os.path.abspath(path)}")


def open_image(path: str) -> None:
    """Try to open the image in the default viewer (best-effort)."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            os.system(f"open '{path}'")
        else:
            os.system(f"xdg-open '{path}' &")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Test PropertyPro watermark removal — no Django needed."
    )
    parser.add_argument("url", nargs="?", default=None,
                        help="PropertyPro image URL (optional)")
    parser.add_argument("--file", "-f", default=None,
                        help="Path to a local image file instead of a URL")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  Watermark Removal v2 — Local Test")
    print("=" * 60)

    # ── Get raw bytes ──────────────────────────────────────────────────────
    if args.file:
        print(f"\n[1] Reading local file: {args.file}")
        with open(args.file, "rb") as f:
            raw = f.read()
        print(f"  ✓ {len(raw) // 1024} KB read")
        stem = os.path.splitext(args.file)[0]
        before_path = f"{stem}_BEFORE.jpg"
        after_path  = f"{stem}_AFTER.jpg"
        mask_path   = f"{stem}_MASK.jpg"
    else:
        url = args.url or DEFAULT_TEST_URL
        print(f"\n[1] Downloading source image")
        raw = download(url)
        before_path = "watermark_BEFORE.jpg"
        after_path  = "watermark_AFTER.jpg"
        mask_path   = "watermark_MASK.jpg"

    # ── Save the BEFORE image ──────────────────────────────────────────────
    print(f"\n[2] Saving BEFORE image")
    save(raw, before_path)

    # ── Run watermark removal (with mask debug output) ─────────────────────
    print(f"\n[3] Running watermark removal")
    clean = remove_watermark(raw, debug_mask_path=mask_path)

    # ── Save the AFTER image ───────────────────────────────────────────────
    print(f"\n[4] Saving AFTER image")
    save(clean, after_path)

    # ── Report ────────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  DONE — compare these files:")
    print(f"    BEFORE  →  {os.path.abspath(before_path)}")
    print(f"    MASK    →  {os.path.abspath(mask_path)}  ← red = inpainted; green = band")
    print(f"    AFTER   →  {os.path.abspath(after_path)}")
    print("=" * 60 + "\n")

    open_image(before_path)
    open_image(mask_path)
    open_image(after_path)


if __name__ == "__main__":
    main()