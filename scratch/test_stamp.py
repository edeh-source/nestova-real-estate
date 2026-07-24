import os
import cv2
import numpy as np
import requests
import sys

sys.path.insert(0, r'c:\Users\htdocs\nestova')
from bookings.image_processor import process_image_bytes

IMG3_URL = "https://images.propertypro.ng/large/1-bedroom-apartment-M14NJvgc0DSZrmNYGNpE.jpeg"
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Nestova/1.0)'}
OUT_DIR = r'c:\Users\htdocs\nestova\media\watermark_test'

def run():
    raw = requests.get(IMG3_URL, headers=HEADERS, timeout=15).content
    
    # 1. Base inpainting (v11d) WITH the Nestova stamp
    res_stamp = process_image_bytes(raw, stamp_nestova=True)
    with open(os.path.join(OUT_DIR, "v13_base_with_stamp.jpg"), 'wb') as f:
        f.write(res_stamp)
    print("Done")

if __name__ == '__main__':
    run()
