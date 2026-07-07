"""
valpaint/tasks.py
Celery task: sync the stored Apify dataset into ValpaintProduct.

Mirrors the propertypro tasks.py pattern exactly:
  - ApifyClient reads the stored dataset (no new actor run needed)
  - update_or_create per product (idempotent — safe to re-run)
  - Downloads the first image only if the product doesn't already have one
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
# Image download helper (same pattern as propertypro)
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
# Taxonomy helpers (run once per task invocation)
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


def _ensure_finishes(items):
    """
    Collect all finish names in the dataset, get_or_create a Finish row for each.
    Returns {display_name: Finish object}.
    """
    seen = {}
    for item in items:
        for fname in (item.get('finishes') or []):
            fname = fname.strip()
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


def _get(item, *keys, default=''):
    """Try multiple field name variants (handles snake_case and camelCase)."""
    for key in keys:
        val = item.get(key)
        if val is not None:
            return val
    return default


# ─────────────────────────────────────────────────────────────────────────────
# Main Celery task
# ─────────────────────────────────────────────────────────────────────────────

@shared_task
def sync_valpaint_products():
    """
    Reads the stored Apify dataset (APIFY_DATASET_ID) and syncs all
    products into ValpaintProduct. Safe to call multiple times.

    Dev test (no Celery running needed):
        from valpaint.tasks import sync_valpaint_products
        print(sync_valpaint_products())

    Trigger manually:
        celery -A nestova call valpaint.tasks.sync_valpaint_products
    """
    client     = ApifyClient(token=settings.APIFY_API_TOKEN)
    dataset_id = settings.APIFY_DATASET_ID

    items = list(client.dataset(dataset_id).iterate_items())
    logger.info(f'Fetched {len(items)} items from Apify dataset {dataset_id!r}')

    if not items:
        logger.warning('Dataset is empty — nothing to import')
        return 'Dataset is empty.'

    categories = _ensure_categories()
    finishes   = _ensure_finishes(items)

    total_created = 0
    total_updated = 0
    total_images  = 0
    total_errors  = 0

    for item in items:
        name = (_get(item, 'name', 'productName') or '').strip()
        if not name:
            logger.warning('Skipping item with no name')
            continue

        slug         = slugify(name)
        use_raw      = (_get(item, 'use_type', 'useType') or 'interior').lower()
        category     = categories.get(use_raw if use_raw in categories else 'interior')
        short_desc   = _get(item, 'short_description', 'shortDescription', 'shortDesc')[:320]
        description  = _get(item, 'description', 'fullDescription')
        valpaint_url = _get(item, 'url', 'productUrl')
        raw_id       = _get(item, 'product_id', 'productId', 'id')
        sku          = str(raw_id) if raw_id else ''
        images       = item.get('images') or []
        first_image  = images[0] if images else None

        item_finish_objs = [
            finishes[f.strip()]
            for f in (item.get('finishes') or [])
            if f.strip() in finishes
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
                    'sku':          sku,
                    'image_alt':    name,
                    'is_active':    True,
                    'in_stock':     True,
                },
            )

            if item_finish_objs:
                obj.finishes.set(item_finish_objs)

            if not obj.image and first_image:
                filename, content = download_image(first_image)
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