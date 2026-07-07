"""
valpaint/tasks.py
Celery task: sync the stored Apify dataset into ValpaintProduct.

The Apify dataset is a mixed array of two item types:
  - {"type": "finish_map", "finish_name": "...", "product_ids": [...]}
  - {"type": "product",    "product_id": "...", "image_url": "...", ...}
"""

import logging
import uuid

import requests
from apify_client import ApifyClient
from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.text import slugify

from .models import Finish, ProductCategory, ValpaintProduct

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Image download helper
# ─────────────────────────────────────────────────────────────────────────────

def download_image(image_url):
    """Fetch image from valpaint.it. Returns (filename, ContentFile) or (None, None)."""
    if not image_url:
        return None, None
    try:
        resp = requests.get(image_url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer':    'https://www.valpaint.it/',
        })
        if resp.status_code == 200:
            ext = image_url.split('.')[-1].split('?')[0][:4] or 'jpg'
            if ext not in ('jpg', 'jpeg', 'png', 'webp'):
                ext = 'jpg'
            filename = f"{uuid.uuid4().hex}.{ext}"
            return filename, ContentFile(resp.content)
    except Exception as e:
        logger.warning(f'Image download failed for {image_url}: {e}')
    return None, None


# ─────────────────────────────────────────────────────────────────────────────
# Taxonomy helpers
# ─────────────────────────────────────────────────────────────────────────────

_CATEGORY_DEFS = [
    {'slug': 'interior',          'name': 'Interior',            'use_type': 'interior', 'sort_order': 1},
    {'slug': 'exterior',          'name': 'Exterior',            'use_type': 'exterior', 'sort_order': 2},
    {'slug': 'interior-exterior', 'name': 'Interior & Exterior', 'use_type': 'both',     'sort_order': 3},
]

_USE_TO_SLUG = {
    'interior': 'interior',
    'exterior': 'exterior',
    'both':     'interior-exterior',
}


def _ensure_categories():
    """Get or create the 3 base ProductCategory rows. Returns {raw_use_type: obj}."""
    categories = {}
    for defn in _CATEGORY_DEFS:
        cat, created = ProductCategory.objects.get_or_create(
            slug=defn['slug'],
            defaults={
                'name':       defn['name'],
                'use_type':   defn['use_type'],
                'sort_order': defn['sort_order'],
            },
        )
        if created:
            logger.info(f'Created category: {defn["name"]}')
        for raw_key, slug in _USE_TO_SLUG.items():
            if slug == defn['slug']:
                categories[raw_key] = cat
    return categories


def _ensure_finishes(finish_maps):
    """
    Reads finish names from finish_map items (not product items).
    Returns {finish_name: Finish object}.
    """
    seen = {}
    for item in finish_maps:
        fname = (item.get('finish_name') or '').strip()
        if fname and fname.lower() not in seen:
            seen[fname.lower()] = fname

    finishes = {}
    for i, (_, display_name) in enumerate(sorted(seen.items())):
        obj, created = Finish.objects.get_or_create(
            slug=slugify(display_name),
            defaults={'name': display_name, 'sort_order': i * 10},
        )
        if created:
            logger.info(f'Created finish: {display_name}')
        finishes[display_name] = obj
    return finishes


def _build_product_finish_map(finish_maps):
    """
    Inverts finish_map items into {product_id_str: [finish_name, ...]}.
    """
    result = {}
    for item in finish_maps:
        fname = (item.get('finish_name') or '').strip()
        if not fname:
            continue
        for pid in (item.get('product_ids') or []):
            result.setdefault(str(pid), []).append(fname)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Main Celery task
# ─────────────────────────────────────────────────────────────────────────────

@shared_task
def sync_valpaint_products():
    """
    Reads the stored Apify dataset and syncs all products into ValpaintProduct.
    Safe to call multiple times (idempotent).

    Dev test (no Celery needed):
        from valpaint.tasks import sync_valpaint_products
        print(sync_valpaint_products())

    Trigger manually:
        celery -A nestova call valpaint.tasks.sync_valpaint_products
    """
    client     = ApifyClient(token=settings.APIFY_API_TOKEN)
    dataset_id = settings.APIFY_DATASET_ID

    all_items = list(client.dataset(dataset_id).iterate_items())
    logger.info(f'Fetched {len(all_items)} items from Apify dataset {dataset_id!r}')

    if not all_items:
        logger.warning('Dataset is empty — nothing to import')
        return 'Dataset is empty.'

    # Split the mixed array by type
    products    = [i for i in all_items if i.get('type') == 'product']
    finish_maps = [i for i in all_items if i.get('type') == 'finish_map']

    logger.info(f'{len(products)} products, {len(finish_maps)} finish maps')

    categories         = _ensure_categories()
    finishes           = _ensure_finishes(finish_maps)
    product_finish_map = _build_product_finish_map(finish_maps)

    total_created = 0
    total_updated = 0
    total_images  = 0
    total_errors  = 0

    for item in products:
        name = (item.get('name') or '').strip()
        if not name:
            logger.warning('Skipping item with no name')
            continue

        slug        = slugify(name)
        use_raw     = (item.get('use_type') or 'interior').lower()
        category    = categories.get(use_raw if use_raw in categories else 'interior')
        short_desc  = (item.get('short_desc') or '')[:320]
        description = item.get('description') or ''
        valpaint_url = item.get('valpaint_url') or ''
        product_id  = str(item.get('product_id') or '')
        image_url   = item.get('image_url') or ''   # ← correct field name

        # Look up finishes for this product via the inverted map
        finish_names     = product_finish_map.get(product_id, [])
        item_finish_objs = [
            finishes[fname]
            for fname in finish_names
            if fname in finishes
        ]

        try:
            obj, created = ValpaintProduct.objects.update_or_create(
                slug=slug,
                defaults={
                    'name':         name,
                    'category':     category,
                    'short_desc':   short_desc,
                    'description':  description,
                    'valpaint_url': valpaint_url,
                    'sku':          product_id,
                    'image_alt':    name,
                    'is_active':    True,
                    'in_stock':     True,
                },
            )

            if item_finish_objs:
                obj.finishes.set(item_finish_objs)

            # Download hero image using image_url
            if not obj.image and image_url:
                filename, content = download_image(image_url)
                if filename and content:
                    obj.image.save(filename, content, save=True)
                    total_images += 1
                    logger.info(f'Saved image for: {name[:50]}')

            if created:
                total_created += 1
                logger.info(f'Created: {name}')
            else:
                total_updated += 1

        except Exception as e:
            total_errors += 1
            logger.error(f'Error on "{name}": {e}')

    summary = (
        f'Done. {total_created} created, {total_updated} updated, '
        f'{total_images} images saved, {total_errors} errors.'
    )
    logger.info(summary)
    return summary