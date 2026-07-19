"""
bookings/image_processor.py

Stamps a large, centered NESTOVA watermark over scraped PropertyPro images,
replicating the same style PropertyPro uses for their own watermark:
  - Large semi-transparent white text
  - Centered on the image
  - Subtle dark shadow for depth
  - No background band (text directly over the photo)

Uses only Pillow (no OpenCV dependency needed in production).
"""

import io
import os
import logging
import cv2
import numpy as np

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


# Font search order: Windows fonts, then Linux/Production server fonts
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\seguisb.ttf",       # Segoe UI Semibold
    r"C:\Windows\Fonts\segoeui.ttf",       # Segoe UI
    r"C:\Windows\Fonts\arialbd.ttf",       # Arial Bold
    r"C:\Windows\Fonts\arial.ttf",         # Arial
    r"C:\Windows\Fonts\calibrib.ttf",      # Calibri Bold
    # Linux / Railway / Render server paths
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
    Uses OpenCV inpainting to completely erase the PropertyPro watermark.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return image_bytes

    h, w = img.shape[:2]
    
    # PropertyPro watermark is roughly in the center, between 40% and 60% height
    y_start = int(h * 0.40)
    y_end = int(h * 0.60)
    
    roi = img[y_start:y_end, 0:w]
    
    # Create a mask for bright pixels (the white watermark)
    lower_white = np.array([150, 150, 150], dtype=np.uint8)
    upper_white = np.array([255, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(roi, lower_white, upper_white)
    
    # Dilate mask to cover edges of the text
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    
    # Inpaint to remove the text
    inpainted_roi = cv2.inpaint(roi, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
    
    img[y_start:y_end, 0:w] = inpainted_roi
    
    success, encoded = cv2.imencode('.jpg', img)
    if success:
        return encoded.tobytes()
    return image_bytes



def _stamp_nestova(pil_img: Image.Image) -> Image.Image:
    """
    Draw a large, centered, semi-transparent NESTOVA watermark over the image.

    Replicates PropertyPro's watermark style:
      • Large white text, ~45% of image width
      • About 65% opacity (alpha 166) — clearly visible but not harsh
      • Subtle dark drop-shadow for depth on all backgrounds
      • Text centered both horizontally and vertically
    """
    pil_rgba = pil_img.convert("RGBA")
    w, h = pil_rgba.size

    # Create a transparent overlay to draw on
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(overlay)

    # Font size: roughly 13% of image width (large and prominent)
    font_size = max(48, int(w * 0.13))
    font = _load_font(font_size)
    text = "NESTOVA"

    # Measure text dimensions
    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        tw = right - left
        th = bottom - top
    except AttributeError:   # older Pillow fallback
        tw, th = draw.textsize(text, font=font)

    # Centre coordinates
    x = (w - tw) // 2
    y = (h - th) // 2

    # 1. Dark shadow (offset slightly, low opacity) for readability
    shadow_offset = max(2, font_size // 28)
    draw.text(
        (x + shadow_offset, y + shadow_offset),
        text,
        fill=(0, 0, 0, 90),   # near-black, ~35% opacity
        font=font,
    )

    # 2. White watermark text — ~65% opacity (matches PropertyPro's style)
    draw.text(
        (x, y),
        text,
        fill=(255, 255, 255, 166),  # white, 65% opacity
        font=font,
    )

    return Image.alpha_composite(pil_rgba, overlay)


def process_image_bytes(raw_bytes: bytes, fmt: str = "JPEG") -> bytes:
    """
    Given raw image bytes from a PropertyPro CDN download, stamp the Nestova
    watermark and return processed image bytes.

    Parameters
    ----------
    raw_bytes : bytes
        Raw bytes of the downloaded image.
    fmt : str
        Output format ('JPEG', 'WEBP', 'PNG').

    Returns
    -------
    bytes
        Processed image bytes.
    """
    fmt = fmt.upper()
    if fmt == "JPG":
        fmt = "JPEG"

    try:
        # Step 1: Completely erase PropertyPro watermark using OpenCV
        erased_bytes = _erase_propertypro_cv2(raw_bytes)

        # Step 2: Stamp NESTOVA using Pillow
        pil_img = Image.open(io.BytesIO(erased_bytes))
        result = _stamp_nestova(pil_img)

        if fmt == "JPEG":
            result = result.convert("RGB")

        buf = io.BytesIO()
        result.save(buf, format=fmt, quality=90)
        return buf.getvalue()

    except Exception as exc:
        logger.error(
            "image_processor.process_image_bytes failed: %s", exc, exc_info=True
        )
        return raw_bytes   # fall back: return original unmodified bytes


def reprocess_local_image(file_path: str) -> bool:
    """
    Read an already-downloaded local image, stamp Nestova, save back in place.
    Returns True on success.
    """
    try:
        with open(file_path, "rb") as f:
            raw = f.read()

        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        fmt_map = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
        fmt = fmt_map.get(ext, "JPEG")

        processed = process_image_bytes(raw, fmt=fmt)

        with open(file_path, "wb") as f:
            f.write(processed)

        logger.info("reprocess_local_image OK: %s", file_path)
        return True
    except Exception as exc:
        logger.error("reprocess_local_image failed for %s: %s", file_path, exc)
        return False
