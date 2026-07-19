"""
bookings/image_processor.py

Removes the PropertyPro.ng watermark from a downloaded image using a modern
frosted glassmorphism banner effect across the center, and stamps the Nestova 
watermark inside it.

This completely obscures the PropertyPro watermark without the chaotic smudges
often caused by OpenCV inpainting on large text blocks.
"""

import io
import os
import logging

from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger(__name__)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    # Linux/Production paths
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def process_image_bytes(raw_bytes: bytes, fmt: str = "JPEG") -> bytes:
    """
    Given raw image bytes from a PropertyPro CDN download:
      1. Apply a frosted glass banner across the center strip (40%-60%).
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
        # Load the image using Pillow directly
        pil_img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
        w, h = pil_img.size
        
        # ── 1. Define the watermark strip ─────────────────────────────────────────
        # PropertyPro watermark spans roughly 38% to 62% vertically
        y_top = int(h * 0.40)
        y_bottom = int(h * 0.60)
        
        # Crop just the center band
        strip = pil_img.crop((0, y_top, w, y_bottom))
        
        # ── 2. Frosted Glass Blur ─────────────────────────────────────────────────
        # Blur the strip heavily to obscure the PropertyPro logo
        blurred_strip = strip.filter(ImageFilter.GaussianBlur(radius=25))
        
        # ── 3. Overlay a semi-transparent tint ────────────────────────────────────
        tint = Image.new("RGBA", (w, y_bottom - y_top), (255, 255, 255, 60)) # White tint
        blurred_strip = Image.alpha_composite(blurred_strip, tint)
        
        # Paste the frosted banner back onto the image
        pil_img.paste(blurred_strip, (0, y_top))
        
        # ── 4. Draw NESTOVA Text ──────────────────────────────────────────────────
        draw = ImageDraw.Draw(pil_img)
        
        # Find a nice font size based on image width
        font_size = max(40, int(w * 0.08)) 
        font = _load_font(font_size)
                
        text = "NESTOVA"
        try:
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            tw, th = right - left, bottom - top
        except AttributeError:
            tw, th = draw.textsize(text, font=font)
            
        x = (w - tw) // 2
        y = y_top + ((y_bottom - y_top) - th) // 2 - (th // 4)
        
        # Draw text (dark with slight shadow for visibility)
        draw.text((x+2, y+2), text, fill=(0, 0, 0, 100), font=font)
        draw.text((x, y), text, fill=(255, 255, 255, 230), font=font)
        
        # ── Encode back to bytes ─────────────────────────────
        if fmt == "JPEG":
            pil_img = pil_img.convert("RGB")   # JPEG has no alpha
            
        buf = io.BytesIO()
        pil_img.save(buf, format=fmt, quality=90)
        return buf.getvalue()

    except Exception as exc:
        logger.error(f"image_processor.process_image_bytes failed: {exc}", exc_info=True)
        return raw_bytes   # fall back: return unmodified bytes


def reprocess_local_image(file_path: str) -> bool:
    """
    Read an already-downloaded local image, apply glassmorphism banner,
    stamp Nestova, save back in place. Returns True on success.
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
