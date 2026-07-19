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
        pil_img = Image.open(io.BytesIO(raw_bytes))

        # Stamp Nestova watermark
        result = _stamp_nestova(pil_img)

        # JPEG doesn't support alpha — convert to RGB
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
