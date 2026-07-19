"""
bookings/image_processor.py

Removes the PropertyPro.ng watermark from a downloaded image using OpenCV inpainting,
then stamps the Nestova watermark in its place.

The PropertyPro watermark is a semi-transparent white logo + text centered on the image.
We detect it by looking for the characteristic semi-white pixels in the center region,
create a dilated binary mask, inpaint with OpenCV TELEA algorithm, then overlay Nestova.
"""

import io
import os
import logging

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# 1.  Watermark detection helpers
# ──────────────────────────────────────────────────────────────

def _propertypro_mask(bgr_img: np.ndarray) -> np.ndarray:
    """
    Return a binary mask (uint8, 0/255) that covers the PropertyPro watermark.

    The PropertyPro watermark is a HORIZONTAL STRIP of semi-transparent white
    text+logo, centred both horizontally and vertically in the image.
    It spans roughly:
      • Vertical:   40 % – 60 % of the image height  (a thin horizontal band)
      • Horizontal: 10 % – 90 % of the image width

    Strategy
    --------
    1. Only look inside that tight strip.
    2. Within the strip find near-white, low-saturation pixels.
    3. Use morphological closing + moderate dilation so inpaint has enough context.
    """
    h, w = bgr_img.shape[:2]

    # ── 1. Define the strict watermark strip ──────────────────────────────────
    y_top    = int(h * 0.38)
    y_bottom = int(h * 0.62)
    x_left   = int(w * 0.08)
    x_right  = int(w * 0.92)

    strip = bgr_img[y_top:y_bottom, x_left:x_right]

    # ── 2. Detect near-white pixels (low saturation, high brightness) ─────────
    hsv_strip = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    s = hsv_strip[:, :, 1]   # saturation 0-255
    v = hsv_strip[:, :, 2]   # value      0-255

    # PropertyPro watermark = very low saturation (< 45) AND high brightness (> 180)
    strip_mask = ((s < 45) & (v > 180)).astype(np.uint8) * 255

    # ── 3. Morphological ops to fill letter gaps ──────────────────────────────
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))

    closed  = cv2.morphologyEx(strip_mask, cv2.MORPH_CLOSE, kernel_close)
    dilated = cv2.dilate(closed, kernel_dilate, iterations=1)

    # ── 4. Place back into full-image mask ────────────────────────────────────
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[y_top:y_bottom, x_left:x_right] = dilated

    return full_mask


# ──────────────────────────────────────────────────────────────
# 2.  Nestova watermark stamp
# ──────────────────────────────────────────────────────────────

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _stamp_nestova(pil_img: Image.Image) -> Image.Image:
    """
    Draw a faint centred 'NESTOVA' watermark on *pil_img* (RGBA).
    Returns a new RGBA Image.
    """
    w, h = pil_img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(36, int(w * 0.10))          # ~10 % of image width
    font = _load_font(font_size)
    text = "NESTOVA"

    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        tw = right - left
        th = bottom - top
    except AttributeError:                       # older Pillow
        tw, th = draw.textsize(text, font=font)

    x = (w - tw) // 2
    y = (h - th) // 2

    # Subtle dark shadow for readability on light backgrounds
    shadow = max(1, font_size // 30)
    draw.text((x + shadow, y + shadow), text, fill=(0, 0, 0, 40), font=font)
    # Faint white text  (alpha ≈ 80/255 ≈ 31 % opacity)
    draw.text((x, y), text, fill=(255, 255, 255, 80), font=font)

    return Image.alpha_composite(pil_img.convert("RGBA"), overlay)


# ──────────────────────────────────────────────────────────────
# 3.  Public API
# ──────────────────────────────────────────────────────────────

def process_image_bytes(raw_bytes: bytes, fmt: str = "JPEG") -> bytes:
    """
    Given raw image bytes from a PropertyPro CDN download:
      1. Remove the PropertyPro watermark via inpainting.
      2. Stamp 'NESTOVA' in its place.
      3. Return processed image as bytes in the requested format.

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
        # ── Decode ───────────────────────────────────────────
        nparr = np.frombuffer(raw_bytes, np.uint8)
        bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if bgr is None:
            logger.warning("cv2.imdecode returned None – returning original bytes")
            return raw_bytes

        # ── Build mask & inpaint ─────────────────────────────
        mask = _propertypro_mask(bgr)
        inpainted = cv2.inpaint(bgr, mask, inpaintRadius=4, flags=cv2.INPAINT_TELEA)

        # ── Convert to PIL (RGB → RGBA) ──────────────────────
        rgb = cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb).convert("RGBA")

        # ── Stamp Nestova ────────────────────────────────────
        pil_img = _stamp_nestova(pil_img)

        # ── Encode back to bytes ─────────────────────────────
        if fmt == "JPEG":
            pil_img = pil_img.convert("RGB")   # JPEG has no alpha

        buf = io.BytesIO()
        pil_img.save(buf, format=fmt, quality=88)
        return buf.getvalue()

    except Exception as exc:
        logger.error(f"image_processor.process_image_bytes failed: {exc}", exc_info=True)
        return raw_bytes   # fall back: return unmodified bytes


def reprocess_local_image(file_path: str) -> bool:
    """
    Read an already-downloaded local image, strip PropertyPro watermark,
    stamp Nestova, save back in place.  Returns True on success.
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

        logger.info(f"reprocess_local_image OK: {file_path}")
        return True
    except Exception as exc:
        logger.error(f"reprocess_local_image failed for {file_path}: {exc}")
        return False
