from celery import shared_task
from apify_client import ApifyClient
from django.conf import settings
from django.core.files.base import ContentFile
from .models import ScrapedListing
import requests
import uuid
import logging

logger = logging.getLogger(__name__)


def download_image(image_url):
    """Fetch image from propertypro.ng, return (filename, ContentFile) or (None, None)"""
    if not image_url:
        return None, None
    try:
        resp = requests.get(image_url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://propertypro.ng/',
        })
        if resp.status_code == 200:
            ext = image_url.split('.')[-1].split('?')[0][:4] or 'jpg'
            filename = f"{uuid.uuid4().hex}.{ext}"
            return filename, ContentFile(resp.content)
    except Exception as e:
        logger.warning(f'Image download failed for {image_url}: {e}')
    return None, None


@shared_task
def sync_propertypro_listings():
    client = ApifyClient(token=settings.APIFY_API_TOKEN)

    cities = ['lagos', 'abuja', 'port-harcourt']
    total_saved = 0
    total_images = 0

    for city in cities:
        try:
            run = client.actor(settings.APIFY_ACTOR_ID).call(run_input={
                'city': city,
                'maxPages': 5,
            })

            for item in client.dataset(run['defaultDatasetId']).iterate_items():
                obj, created = ScrapedListing.objects.update_or_create(
                    url=item.get('url', ''),
                    defaults={
                        'title':     item.get('title', ''),
                        'price':     item.get('price', ''),
                        'location':  item.get('location', ''),
                        'image_url': item.get('image', ''),  # keep original URL
                        'city':      city,
                    }
                )

                # Download & store image only if we don't already have it
                if not obj.image_file and obj.image_url:
                    filename, content = download_image(obj.image_url)
                    if filename and content:
                        obj.image_file.save(filename, content, save=True)
                        total_images += 1
                        logger.info(f'Saved image for: {obj.title[:50]}')

                if created:
                    total_saved += 1

            logger.info(f'Synced {city}: {total_saved} new listings, {total_images} images saved')

        except Exception as e:
            logger.error(f'Failed to sync {city}: {e}')

    return f'Done. {total_saved} new listings saved, {total_images} images downloaded.'