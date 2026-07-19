import os
from PIL import Image, ImageDraw, ImageFont

def add_watermark(image_path, text="NESTOVA"):
    try:
        # Load image and convert to RGBA
        img = Image.open(image_path)
        original_format = img.format if img.format else 'WEBP'
        img = img.convert("RGBA")
        
        width, height = img.size
        
        # Create a transparent overlay for the watermark
        txt_img = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_img)
        
        # Make the font size larger (15% of the image width)
        font_size = max(36, int(width * 0.14))
        
        # Load Windows font
        font = None
        font_paths = [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\calibri.ttf"
        ]
        for path in font_paths:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, font_size)
                    break
                except Exception:
                    continue
        
        if font is None:
            font = ImageFont.load_default()
            
        # Get text size to center it
        try:
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            text_width = right - left
            text_height = bottom - top
        except AttributeError:
            text_width, text_height = draw.textsize(text, font=font)
            
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        # Draw a faint dark shadow/outline first for readability
        shadow_offset = max(1, int(font_size * 0.03))
        draw.text((x + shadow_offset, y + shadow_offset), text, fill=(0, 0, 0, 35), font=font)
        draw.text((x - shadow_offset, y - shadow_offset), text, fill=(0, 0, 0, 20), font=font)
        
        # Draw the main faint white text (opacity 75 out of 255)
        draw.text((x, y), text, fill=(255, 255, 255, 75), font=font)
        
        # Combine original image with watermark overlay
        watermarked = Image.alpha_composite(img, txt_img)
        
        # Convert back to RGB or keep RGBA if saving to PNG/WEBP
        if original_format == 'JPEG':
            watermarked = watermarked.convert("RGB")
            
        # Overwrite the original file
        watermarked.save(image_path, format=original_format, quality=90)
        print(f"Successfully watermarked with large text: {image_path}")
        return True
    except Exception as e:
        print(f"Failed to watermark {image_path}: {e}")
        return False

# Target directories containing listing images
directories = [
    r"media/properties/featured",
    r"media/apartments",
    r"media/apartments/gallery"
]

print("Starting watermark inscription...")
for directory in directories:
    if not os.path.exists(directory):
        continue
        
    for filename in os.listdir(directory):
        if filename.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            if "Gemini" in filename:
                continue
            file_path = os.path.join(directory, filename)
            add_watermark(file_path)

print("Watermark process finished.")
