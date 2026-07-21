"""
robust_watermark_v9.py
Test script: Blur the watermark band to hide PropertyPro, and stamp NESTOVA over it.
This restores the normal aspect ratio and prevents structural distortion.
"""

import os
import cv2
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

TEST_URLS = [
    "https://images.propertypro.ng/large/luxury-1bedroom-with-rooftop-pool-amp-gym-SfcEB7L1e05zNFvS9Q9N.jpg",
    "https://images.propertypro.ng/large/aston-apartment-simply-magnificent-Aj3Ll8cHGdbF9dzwuMlk.jpeg",
    "https://images.propertypro.ng/large/1-bedroom-apartment-M14NJvgc0DSZrmNYGNpE.jpeg",
    "https://images.propertypro.ng/large/newly-built-1bedroom-apartment-harris-vTQoFXi8gt87JuZVG0kh.jpeg",
    "https://images.propertypro.ng/large/executive-self-contain-98FhbRWkGtD6ehL1eNlD.jpg",
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Nestova/1.0)'}

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\seguisb.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]

def _load_font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

def test_blur_and_stamp():
    out_dir = r'c:\Users\htdocs\nestova\media\watermark_test'
    os.makedirs(out_dir, exist_ok=True)

    for i, url in enumerate(TEST_URLS, 1):
        try:
            raw = requests.get(url, headers=HEADERS, timeout=10).content
            nparr = np.frombuffer(raw, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            h, w = img.shape[:2]

            # The exact band where PropertyPro sits
            y_top = int(h * 0.41)
            y_bot = int(h * 0.59)
            
            roi = img[y_top:y_bot, 0:w]
            
            # 1. Heavily blur the band to obliterate the PropertyPro text
            blurred_roi = cv2.GaussianBlur(roi, (75, 75), 0)
            
            # 2. Darken the band slightly to make white NESTOVA text pop
            darkened_roi = cv2.addWeighted(blurred_roi, 0.7, np.zeros_like(blurred_roi), 0.3, 0)
            
            img[y_top:y_bot, 0:w] = darkened_roi

            # Convert to PIL for text stamping
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb).convert("RGBA")
            
            overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            text = "NESTOVA"
            # Choose a font size that fits nicely in the band
            band_height = y_bot - y_top
            font_size = int(band_height * 0.7)
            font = _load_font(font_size)
            
            try:
                left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
                tw = right - left
                th = bottom - top
            except AttributeError:
                tw, th = draw.textsize(text, font=font)

            x = (w - tw) // 2
            y = y_top + (band_height - th) // 2
            
            # Draw shadow
            shadow_offset = max(2, font_size // 15)
            draw.text((x + shadow_offset, y + shadow_offset), text, fill=(0, 0, 0, 150), font=font)
            # Draw text
            draw.text((x, y), text, fill=(255, 255, 255, 220), font=font)
            
            final_pil = Image.alpha_composite(pil_img, overlay).convert("RGB")
            
            # Save final image
            final_bgr = cv2.cvtColor(np.array(final_pil), cv2.COLOR_RGB2BGR)
            
            # Create side-by-side
            orig_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            combined = np.hstack((orig_img, final_bgr))
            
            cv2.imwrite(os.path.join(out_dir, f"v9_{i}_comparison.jpg"), combined)
            print(f"Saved v9_{i}_comparison.jpg")
            
        except Exception as e:
            print(f"Error on {i}: {e}")

if __name__ == '__main__':
    test_blur_and_stamp()
