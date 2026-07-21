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