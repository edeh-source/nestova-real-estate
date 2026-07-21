"""
bookings/image_processor.py

Erases the PropertyPro watermark from scraped images using OpenCV inpainting,
then optionally stamps a NESTOVA watermark (stamp_nestova=True, the old default).

To produce clean images with NO watermark at all, call:
    process_image_bytes(raw, fmt, stamp_nestova=False)

Uses Pillow for watermark stamping; OpenCV only for erasure.
"""

import io
import os
import logging

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


# Font search order: Windows fonts first, then Linux/Render server paths
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


def _erase_propertypro_cv2(image_bytes: bytes) -> bytes:
    """
    Uses OpenCV inpainting to erase the white, centered watermark text
    (works for both the PropertyPro watermark and the NESTOVA stamp, since
    both are white text positioned in the central 40–60 % height band).
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return image_bytes

    h, w = img.shape[:2]

    # Target the central band where both PropertyPro and NESTOVA stamps live
    y_start = int(h * 0.40)
    y_end   = int(h * 0.60)
    roi     = img[y_start:y_end, 0:w]

    # Mask: bright / white pixels that make up the watermark text
    lower_white = np.array([150, 150, 150], dtype=np.uint8)
    upper_white = np.array([255, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(roi, lower_white, upper_white)

    # Dilate slightly to catch anti-aliased edges
    kernel = np.ones((3, 3), np.uint8)
    mask   = cv2.dilate(mask, kernel, iterations=1)

    # Inpaint the watermark region
    inpainted_roi              = cv2.inpaint(roi, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
    img[y_start:y_end, 0:w]   = inpainted_roi

    success, encoded = cv2.imencode('.jpg', img)
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
    stamp_nestova: bool = True,         # ← NEW: pass False to get a clean image
) -> bytes:
    """
    Process a raw image downloaded from a PropertyPro CDN URL.

    Steps
    -----
    1. Erase white-text watermark in the central band (PropertyPro *and* NESTOVA
       if already stamped) using OpenCV inpainting.
    2. Optionally stamp the NESTOVA mark (stamp_nestova=True, the legacy default).
       Pass stamp_nestova=False to return a clean, watermark-free image.

    Parameters
    ----------
    raw_bytes     : Raw bytes of the source image.
    fmt           : Output format — 'JPEG', 'PNG', or 'WEBP'.
    stamp_nestova : When False, skip the NESTOVA stamp and return a clean image.

    Returns
    -------
    bytes
        Processed image bytes, or the original raw_bytes if processing fails.
    """
    fmt = fmt.upper()
    if fmt == "JPG":
        fmt = "JPEG"

    try:
        # ── Step 1: Erase watermark (PropertyPro and/or NESTOVA) ──
        erased_bytes = _erase_propertypro_cv2(raw_bytes)

        if not stamp_nestova:
            # Return clean image — no watermark added
            pil_img = Image.open(io.BytesIO(erased_bytes))
            if fmt == "JPEG":
                pil_img = pil_img.convert("RGB")
            buf = io.BytesIO()
            pil_img.save(buf, format=fmt, quality=90)
            return buf.getvalue()

        # ── Step 2: Stamp NESTOVA (legacy / opt-in behaviour) ──
        pil_img = Image.open(io.BytesIO(erased_bytes))
        result  = _stamp_nestova(pil_img)

        if fmt == "JPEG":
            result = result.convert("RGB")

        buf = io.BytesIO()
        result.save(buf, format=fmt, quality=90)
        return buf.getvalue()

    except Exception as exc:
        logger.error("image_processor.process_image_bytes failed: %s", exc, exc_info=True)
        return raw_bytes  # fall back: return original unmodified bytes


def reprocess_local_image(file_path: str, stamp_nestova: bool = False) -> bool:
    """
    Read an already-downloaded local image, optionally stamp Nestova, save in place.
    Defaults to stamp_nestova=False (clean output) to match the new pipeline intent.
    Returns True on success.
    """
    try:
        with open(file_path, "rb") as f:
            raw = f.read()

        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
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