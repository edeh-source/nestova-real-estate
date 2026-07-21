import cv2
import base64
import re
import math

# Load the mask
img = cv2.imread('c:/Users/htdocs/nestova/media/watermark_test/v11d_canonical_mask.jpg', cv2.IMREAD_GRAYSCALE)
band = img[246:354, :]
_, enc = cv2.imencode('.png', band)
b64 = base64.b64encode(enc).decode('utf-8')

# Split into 76 character chunks
chunks = [b64[i:i+76] for i in range(0, len(b64), 76)]
formatted_b64 = 'WATERMARK_MASK_B64 = (\n    "' + '"\n    "'.join(chunks) + '"\n)'

# Read file
with open('c:/Users/htdocs/nestova/bookings/image_processor.py', 'r') as f:
    content = f.read()

# Replace block
content = re.sub(r'WATERMARK_MASK_B64 = \(\n(?:    "[^"]*"\n)+\)', formatted_b64, content)

with open('c:/Users/htdocs/nestova/bookings/image_processor.py', 'w') as f:
    f.write(content)
print("Updated mask successfully!")
