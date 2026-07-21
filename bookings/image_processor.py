"""
bookings/image_processor.py

Removes the PropertyPro watermark using a precomputed canonical mask and 
Navier-Stokes inpainting (v11d). This preserves the exact original image 
geometry (no aspect ratio stretching) while minimizing smudging.
"""

import io
import os
import logging
import base64

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Base64 encoded binary PNG mask for the PropertyPro watermark text.
# Extracted from a consensus of 5 images. Dimension: 800x108 (width x height)
# Corresponds to the 41%-59% vertical band on an 800x600 image.
WATERMARK_MASK_B64 = (
    "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"
)

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

_cached_canonical_mask = None

def _get_canonical_mask():
    global _cached_canonical_mask
    if _cached_canonical_mask is None:
        png_data = base64.b64decode(WATERMARK_MASK_B64)
        nparr = np.frombuffer(png_data, np.uint8)
        _cached_canonical_mask = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    return _cached_canonical_mask

def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Try each candidate font path; fall back to Pillow's built-in default."""
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

def _remove_watermark_inpaint_v11d(image_bytes: bytes) -> bytes:
    """
    Removes the PropertyPro watermark using a pre-calculated, razor-thin
    stencil mask, and applies Navier-Stokes inpainting.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes

    h, w = img.shape[:2]
    
    # PropertyPro always scales the watermark text to roughly the same 
    # vertical position (41% to 59%) and spans the width.
    y_top = int(h * 0.41)
    y_bot = int(h * 0.59)
    band_height = y_bot - y_top
    
    # Load canonical thin mask (108x800) and resize it to fit the target image
    canonical = _get_canonical_mask()
    resized_band_mask = cv2.resize(canonical, (w, band_height), interpolation=cv2.INTER_NEAREST)
    
    # Construct full-image mask
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[y_top:y_bot, :] = resized_band_mask
    
    # Inpaint. We use Navier-Stokes (NS) with a tiny radius since the mask is thin.
    result = cv2.inpaint(img, full_mask, inpaintRadius=3, flags=cv2.INPAINT_NS)
    
    success, encoded = cv2.imencode('.jpg', result, [cv2.IMWRITE_JPEG_QUALITY, 93])
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
    stamp_nestova: bool = False,
) -> bytes:
    """
    Process a raw image downloaded from a PropertyPro CDN URL.
    Uses v11d Navier-Stokes inpainting with a static stencil mask.
    """
    fmt = fmt.upper()
    if fmt == "JPG":
        fmt = "JPEG"

    try:
        # Remove watermark via thin-stencil inpainting
        cleaned_bytes = _remove_watermark_inpaint_v11d(raw_bytes)

        if not stamp_nestova:
            pil_img = Image.open(io.BytesIO(cleaned_bytes))
            if fmt == "JPEG":
                pil_img = pil_img.convert("RGB")
            buf = io.BytesIO()
            pil_img.save(buf, format=fmt, quality=93)
            return buf.getvalue()

        # Optional: stamp NESTOVA
        pil_img = Image.open(io.BytesIO(cleaned_bytes))
        result  = _stamp_nestova(pil_img)
        if fmt == "JPEG":
            result = result.convert("RGB")
        buf = io.BytesIO()
        result.save(buf, format=fmt, quality=93)
        return buf.getvalue()

    except Exception as exc:
        logger.error("image_processor.process_image_bytes failed: %s", exc, exc_info=True)
        return raw_bytes


def reprocess_local_image(file_path: str, stamp_nestova: bool = False) -> bool:
    try:
        with open(file_path, "rb") as f:
            raw = f.read()

        ext     = os.path.splitext(file_path)[1].lower().lstrip(".")
        fmt_map = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
        fmt     = fmt_map.get(ext, "JPEG")
        processed = process_image_bytes(raw, fmt=fmt, stamp_nestova=stamp_nestova)

        with open(file_path, "wb") as f:
            f.write(processed)

        logger.info("reprocess_local_image OK: %s", file_path)
        return True
    except Exception as exc:
        logger.error("reprocess_local_image failed for %s: %s", file_path, exc)
        return False