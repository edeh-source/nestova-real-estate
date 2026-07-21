from celery import shared_task
from apify_client import ApifyClient
from django.conf import settings
from django.core.files.base import ContentFile
from .models import ScrapedListing
from .image_processor import process_image_bytes
import requests
import uuid
import logging

logger = logging.getLogger(__name__)


def download_image(image_url: str, stamp_nestova: bool = False) -> tuple:
    """
    Fetch an image from the PropertyPro CDN, erase the PropertyPro watermark
    via OpenCV inpainting, and return (filename, ContentFile).

    Parameters
    ----------
    image_url     : Original PropertyPro CDN URL.
    stamp_nestova : When True, also stamp the NESTOVA mark (legacy behaviour).
                    Defaults to False — produces a clean, watermark-free image.

    Returns
    -------
    (filename, ContentFile) on success, (None, None) on failure.
    """
    if not image_url:
        return None, None
    try:
        resp = requests.get(image_url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://propertypro.ng/",
        })
        if resp.status_code == 200:
            raw = resp.content

            # Determine image format from URL extension
            ext     = image_url.split(".")[-1].split("?")[0][:4].lower() or "jpg"
            fmt_map = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
            fmt     = fmt_map.get(ext, "JPEG")
            save_ext = "jpg" if fmt == "JPEG" else ext

            # Erase PropertyPro watermark; optionally stamp NESTOVA
            processed = process_image_bytes(
                raw,
                fmt=fmt,
                stamp_nestova=stamp_nestova,   # ← False by default (clean image)
            )

            filename = f"{uuid.uuid4().hex}.{save_ext}"
            return filename, ContentFile(processed)

    except Exception as e:
        logger.warning(f"Image download failed for {image_url}: {e}")
    return None, None


@shared_task
def sync_propertypro_listings():
    client = ApifyClient(token=settings.APIFY_API_TOKEN)

    cities       = ["lagos", "abuja", "port-harcourt"]
    total_saved  = 0
    total_images = 0

    for city in cities:
        try:
            run = client.actor(settings.APIFY_ACTOR_ID).call(run_input={
                "city":     city,
                "maxPages": 5,
            })

            for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                obj, created = ScrapedListing.objects.update_or_create(
                    url=item.get("url", ""),
                    defaults={
                        "title":     item.get("title", ""),
                        "price":     item.get("price", ""),
                        "location":  item.get("location", ""),
                        "image_url": item.get("image", ""),   # keep original as backup
                        "city":      city,
                    },
                )

                # Download & process image — clean, no watermark
                if not obj.image_file and obj.image_url:
                    filename, content = download_image(
                        obj.image_url,
                        stamp_nestova=False,   # ← clean image, no NESTOVA stamp
                    )
                    if filename and content:
                        obj.image_file.save(filename, content, save=True)
                        total_images += 1
                        logger.info(f"Saved clean image for: {obj.title[:50]}")

                if created:
                    total_saved += 1

            logger.info(
                f"Synced {city}: {total_saved} new listings, {total_images} images saved"
            )

        except Exception as e:
            logger.error(f"Failed to sync {city}: {e}")

    return f"Done. {total_saved} new listings saved, {total_images} images downloaded."