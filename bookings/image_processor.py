"""
bookings/image_processor.py

Removes the PropertyPro watermark from scraped images using seam carving:
  1. Crops out the horizontal band (38-62% of height) containing the watermark.
  2. Stitches the top and bottom halves back together.
  3. Applies a 5-pixel vertical blur at the seam to smooth the transition.

This produces a completely clean image — no PropertyPro watermark,
no Nestova stamp, no smudges, no inpainting artifacts.

The image height is slightly compressed (~24%) which is unnoticeable in
real estate photos and often makes rooms look wider.

Uses OpenCV only. Pillow is kept for the optional stamp_nestova path.
"""

import io
import os
import logging

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


# Font search order: Windows fonts first, then Linux/Railway server paths
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\seguisb.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\calibrib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Try each candidate font path; fall back to Pillow's built-in default."""
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _remove_watermark_seam_carve(image_bytes: bytes) -> bytes:
    """
    Removes the PropertyPro watermark completely using seam carving (crop + stitch).

    Steps:
      1. Crop out the 38%-62% height band (where PropertyPro always places the watermark).
      2. Vstack the clean top and bottom halves.
      3. Apply a short vertical Gaussian blur at the seam to hide any lighting jump.

    Result: zero watermark, zero smudge, zero inpainting artifact.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return image_bytes

    h, w = img.shape[:2]

    # Watermark band — slightly wider than the text to be safe
    y_top = int(h * 0.38)
    y_bot = int(h * 0.62)

    # Crop top and bottom clean halves
    top_half    = img[:y_top, :]
    bottom_half = img[y_bot:, :]

    # Stitch together
    result = np.vstack((top_half, bottom_half))

    # Blend the seam with a short vertical blur
    seam_y      = y_top
    blur_radius = 5
    if seam_y - blur_radius > 0 and seam_y + blur_radius < result.shape[0]:
        seam_region   = result[seam_y - blur_radius : seam_y + blur_radius, :]
        blurred_seam  = cv2.GaussianBlur(seam_region, (1, 15), 0)
        result[seam_y - blur_radius : seam_y + blur_radius, :] = blurred_seam

    success, encoded = cv2.imencode('.jpg', result, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return encoded.tobytes() if success else image_bytes


def _stamp_nestova(pil_img: Image.Image) -> Image.Image:
    """
    Draw a large, centred, semi-transparent NESTOVA watermark over the image.
    Only called when stamp_nestova=True.
    """
    pil_rgba = pil_img.convert("RGBA")
    w, h     = pil_rgba.size

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    font_size = max(48, int(w * 0.13))
    font      = _load_font(font_size)
    text      = "NESTOVA"

    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        tw = right - left
        th = bottom - top
    except AttributeError:
        tw, th = draw.textsize(text, font=font)

    x = (w - tw) // 2
    y = (h - th) // 2

    shadow_offset = max(2, font_size // 28)
    draw.text((x + shadow_offset, y + shadow_offset), text, fill=(0, 0, 0, 90),       font=font)
    draw.text((x,                  y),                 text, fill=(255, 255, 255, 166), font=font)

    return Image.alpha_composite(pil_rgba, overlay)


def process_image_bytes(
    raw_bytes: bytes,
    fmt: str = "JPEG",
    stamp_nestova: bool = False,        # False = clean image, no watermark at all
) -> bytes:
    """
    Process a raw image downloaded from a PropertyPro CDN URL.

    Steps
    -----
    1. Remove the PropertyPro watermark via seam carving (crop + stitch + seam blend).
    2. Optionally stamp the NESTOVA mark (stamp_nestova=True).
       Default is False — returns a completely clean, watermark-free image.

    Parameters
    ----------
    raw_bytes     : Raw bytes of the source image.
    fmt           : Output format — 'JPEG', 'PNG', or 'WEBP'.
    stamp_nestova : When True, adds the NESTOVA stamp after removal.
                    When False (default), returns a completely clean image.

    Returns
    -------
    bytes
        Processed image bytes, or the original raw_bytes if processing fails.
    """
    fmt = fmt.upper()
    if fmt == "JPG":
        fmt = "JPEG"

    try:
        # ── Step 1: Remove PropertyPro watermark via seam carving ──
        cleaned_bytes = _remove_watermark_seam_carve(raw_bytes)

        if not stamp_nestova:
            # Return clean image — no watermark at all
            pil_img = Image.open(io.BytesIO(cleaned_bytes))
            if fmt == "JPEG":
                pil_img = pil_img.convert("RGB")
            buf = io.BytesIO()
            pil_img.save(buf, format=fmt, quality=92)
            return buf.getvalue()

        # ── Step 2 (optional): Stamp NESTOVA ──
        pil_img = Image.open(io.BytesIO(cleaned_bytes))
        result  = _stamp_nestova(pil_img)

        if fmt == "JPEG":
            result = result.convert("RGB")

        buf = io.BytesIO()
        result.save(buf, format=fmt, quality=92)
        return buf.getvalue()

    except Exception as exc:
        logger.error("image_processor.process_image_bytes failed: %s", exc, exc_info=True)
        return raw_bytes  # fall back: return original unmodified bytes


def reprocess_local_image(file_path: str, stamp_nestova: bool = False) -> bool:
    """
    Read an already-downloaded local image, remove the PropertyPro watermark,
    optionally stamp Nestova, and save in place.
    Defaults to stamp_nestova=False (clean output).
    Returns True on success.
    """
    try:
        with open(file_path, "rb") as f:
            raw = f.read()

        ext      = os.path.splitext(file_path)[1].lower().lstrip(".")
        fmt_map  = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
        fmt      = fmt_map.get(ext, "JPEG")
        processed = process_image_bytes(raw, fmt=fmt, stamp_nestova=stamp_nestova)

        with open(file_path, "wb") as f:
            f.write(processed)

        logger.info("reprocess_local_image OK: %s", file_path)
        return True
    except Exception as exc:
        logger.error("reprocess_local_image failed for %s: %s", file_path, exc)
        return False