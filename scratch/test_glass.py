import sys
sys.path.insert(0, r'c:\Users\htdocs\nestova')

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nestova.settings')

import django
django.setup()

import io
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def process_glassmorphism(raw_bytes: bytes, fmt: str = "JPEG") -> bytes:
    """
    Applies a frosted glass banner across the center of the image to cover
    the PropertyPro watermark, and stamps NESTOVA inside it.
    """
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
    
    # Find a nice font size
    font_size = max(40, int(w * 0.08)) 
    font_candidates = [
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    font = ImageFont.load_default()
    for f in font_candidates:
        if os.path.exists(f):
            font = ImageFont.truetype(f, font_size)
            break
            
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
    
    if fmt == "JPEG":
        pil_img = pil_img.convert("RGB")
        
    buf = io.BytesIO()
    pil_img.save(buf, format=fmt, quality=90)
    return buf.getvalue()

import requests

# Let's download a real PropertyPro image to test
test_url = "https://images.propertypro.ng/large/executive-fully-furnished-2bed-yaba-gBrxV3lhvnWvZj8yWFn8.jpg"
resp = requests.get(test_url, headers={'User-Agent': 'Mozilla/5.0'})

if resp.status_code == 200:
    out_path = r'c:\Users\htdocs\nestova\media\test_glassmorphism.jpg'
    processed = process_glassmorphism(resp.content, fmt='JPEG')
    with open(out_path, 'wb') as f:
        f.write(processed)
    print(f"Saved processed image to: {out_path}")
else:
    print("Download failed")
