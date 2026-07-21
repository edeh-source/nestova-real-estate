import cv2
import numpy as np
import requests

def download_image(url):
    r = requests.get(url)
    r.raise_for_status()
    return r.content

def remove_watermark(image_bytes):
    # Decode image
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return image_bytes

    h, w = img.shape[:2]
    
    # PropertyPro watermark is roughly in the center, between 40% and 60% height
    y_start = int(h * 0.40)
    y_end = int(h * 0.60)
    
    # We only process the center band
    roi = img[y_start:y_end, 0:w]
    
    # The watermark is bright white/light gray. 
    # Create a mask for bright pixels
    lower_white = np.array([200, 200, 200], dtype=np.uint8)
    upper_white = np.array([255, 255, 255], dtype=np.uint8)
    
    mask = cv2.inRange(roi, lower_white, upper_white)
    
    # Dilate the mask slightly to cover edges
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    
    # Inpaint the ROI
    inpainted_roi = cv2.inpaint(roi, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
    
    # Put it back
    img[y_start:y_end, 0:w] = inpainted_roi
    
    # Encode back to jpeg
    success, encoded = cv2.imencode('.jpg', img)
    if success:
        return encoded.tobytes()
    return image_bytes

# Test
url = "https://images.propertypro.ng/large/executive-fully-furnished-2bed-yaba-gBrxV3lhvnWvZj8yWFn8.jpg"
raw = download_image(url)

print("Downloaded")
processed = remove_watermark(raw)
with open("test_inpaint.jpg", "wb") as f:
    f.write(processed)
print("Done")
