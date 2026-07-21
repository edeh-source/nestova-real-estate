"""
bookings/image_processor.py

Covers the PropertyPro watermark on scraped images by:
  1. Heavily blurring the central band (41-59% of height) to obliterate their text.
  2. Darkening the blurred band slightly.
  3. Stamping a crisp NESTOVA watermark over the blurred band.

This preserves the full original image dimensions and aspect ratio — no cropping,
no distortion.

Uses OpenCV for blurring; Pillow for watermark stamping.
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


def _cover_propertypro_with_nestova(image_bytes: bytes) -> bytes:
    """
    Covers the PropertyPro watermark band by:
      1. Applying a heavy Gaussian blur over the 41%-59% height band to
         completely obliterate the PropertyPro text.
      2. Darkening the blurred band slightly to create a clean backdrop.
      3. Stamping a crisp NESTOVA watermark over the blurred band.

    This approach preserves the full original image dimensions and aspect ratio,
    preventing any structural distortion.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return image_bytes

    h, w = img.shape[:2]

    # The exact band where PropertyPro watermark sits
    y_top = int(h * 0.41)
    y_bot = int(h * 0.59)
    band_height = y_bot - y_top

    roi = img[y_top:y_bot, 0:w]

    # 1. Heavy blur to obliterate PropertyPro text
    blurred_roi = cv2.GaussianBlur(roi, (75, 75), 0)

    # 2. Darken slightly to make white NESTOVA text pop
    darkened_roi = cv2.addWeighted(blurred_roi, 0.7, np.zeros_like(blurred_roi), 0.3, 0)

    img[y_top:y_bot, 0:w] = darkened_roi

    # Convert to PIL for text stamping
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb).convert("RGBA")

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    text = "NESTOVA"
    font_size = max(32, int(band_height * 0.7))
    font = _load_font(font_size)

    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        tw = right - left
        th = bottom - top
    except AttributeError:
        tw, th = draw.textsize(text, font=font)

    x = (w - tw) // 2
    y = y_top + (band_height - th) // 2

    shadow_offset = max(2, font_size // 15)
    draw.text((x + shadow_offset, y + shadow_offset), text, fill=(0, 0, 0, 150), font=font)
    draw.text((x, y), text, fill=(255, 255, 255, 220), font=font)

    result_pil = Image.alpha_composite(pil_img, overlay)

    # Convert back to BGR bytes
    result_rgb = np.array(result_pil.convert("RGB"))
    result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)

    success, encoded = cv2.imencode('.jpg', result_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return encoded.tobytes() if success else image_bytes


def process_image_bytes(
    raw_bytes: bytes,
    fmt: str = "JPEG",
    stamp_nestova: bool = True,
) -> bytes:
    """
    Process a raw image downloaded from a PropertyPro CDN URL.

    Steps
    -----
    1. Blur the PropertyPro watermark band to completely obliterate their text.
    2. Stamp a clean NESTOVA watermark over the blurred band.

    Parameters
    ----------
    raw_bytes     : Raw bytes of the source image.
    fmt           : Output format — 'JPEG', 'PNG', or 'WEBP'.
    stamp_nestova : When True (default), stamps NESTOVA over the blurred band.
                    When False, only blurs the PropertyPro band (no stamp added).

    Returns
    -------
    bytes
        Processed image bytes, or the original raw_bytes if processing fails.
    """
    fmt = fmt.upper()
    if fmt == "JPG":
        fmt = "JPEG"

    try:
        if stamp_nestova:
            # Blur PropertyPro band + stamp NESTOVA on top (main path)
            return _cover_propertypro_with_nestova(raw_bytes)

        # stamp_nestova=False: just blur the PropertyPro band, no text added
        nparr = np.frombuffer(raw_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return raw_bytes

        h, w = img.shape[:2]
        y_top = int(h * 0.41)
        y_bot = int(h * 0.59)
        roi = img[y_top:y_bot, 0:w]
        blurred_roi = cv2.GaussianBlur(roi, (75, 75), 0)
        img[y_top:y_bot, 0:w] = blurred_roi

        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        if fmt == "JPEG":
            pil_img = pil_img.convert("RGB")
        buf = io.BytesIO()
        pil_img.save(buf, format=fmt, quality=90)
        return buf.getvalue()

    except Exception as exc:
        logger.error("image_processor.process_image_bytes failed: %s", exc, exc_info=True)
        return raw_bytes  # fall back: return original unmodified bytes


def reprocess_local_image(file_path: str, stamp_nestova: bool = True) -> bool:
    """
    Read an already-downloaded local image, cover PropertyPro watermark with
    NESTOVA stamp, and save in place.
    Returns True on success.
    """
    try:
        with open(file_path, "rb") as f:
            raw = f.read()

        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        fmt_map = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
        fmt = fmt_map.get(ext, "JPEG")
        processed = process_image_bytes(raw, fmt=fmt, stamp_nestova=stamp_nestova)

        with open(file_path, "wb") as f:
            f.write(processed)

        logger.info("reprocess_local_image OK: %s", file_path)
        return True
    except Exception as exc:
        logger.error("reprocess_local_image failed for %s: %s", file_path, exc)
        return False