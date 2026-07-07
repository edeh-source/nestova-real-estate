"""
Django management command: import Valpaint products from an Apify dataset.

Usage:
    python manage.py import_valpaint apify_output.json
    python manage.py import_valpaint apify_output.json --download-images
    python manage.py import_valpaint apify_output.json --update --download-images
    python manage.py import_valpaint apify_output.json --dry-run

Apify JSON schema — a mixed array of two object types:

  { "type": "finish_map",
    "finish_name": "Textured",
    "finish_name_it": "Materico",
    "product_ids": ["74", "22", ...] }

  { "type": "product",
    "product_id": "74",
    "name": "ARMONIE D'ARGILLA",
    "short_desc": "",
    "description": "",
    "use_type": "interior",
    "image_url": "https://...",
    "gallery_images": ["https://...", ...],
    "valpaint_url": "https://..." }
"""

import json
import time
from pathlib import Path

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from valpaint.models import Finish, ProductCategory, ValpaintProduct


# ── Category definitions ──────────────────────────────────────────────────────

CATEGORY_DEFS = [
    {
        'slug':       'interior',
        'name':       'Interior',
        'use_type':   ProductCategory.USE_INTERIOR,
        'sort_order': 1,
        'icon':       'bi-house',
    },
    {
        'slug':       'exterior',
        'name':       'Exterior',
        'use_type':   ProductCategory.USE_EXTERIOR,
        'sort_order': 2,
        'icon':       'bi-building',
    },
    {
        'slug':       'interior-exterior',
        'name':       'Interior & Exterior',
        'use_type':   ProductCategory.USE_BOTH,
        'sort_order': 3,
        'icon':       'bi-layers',
    },
]

USE_TYPE_TO_SLUG = {
    'interior': 'interior',
    'exterior': 'exterior',
    'both':     'interior-exterior',
}

FINISH_ICONS = {
    'textured':            'bi-texture',
    'metallic':            'bi-stars',
    'satin':               'bi-gem',
    'glitter':             'bi-stars',
    'cement':              'bi-square',
    'stucco':              'bi-layers',
    'sand effect':         'bi-dot',
    'velvet':              'bi-circle',
    'silk effect':         'bi-circle-half',
    'pearlescent':         'bi-brightness-high',
    'luminescent':         'bi-lightbulb',
    'fabric effect':       'bi-grid',
    'antiqued':            'bi-clock-history',
    'corten / oxidized':   'bi-shield',
}


# ─────────────────────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = 'Import Valpaint products from an Apify dataset JSON file'

    def add_arguments(self, parser):
        parser.add_argument(
            'json_file',
            type=str,
            help='Path to the Apify dataset JSON file',
        )
        parser.add_argument(
            '--download-images',
            action='store_true',
            default=False,
            help='Download the first product image from valpaint.it into Django media',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Print what would happen without writing anything to the DB',
        )
        parser.add_argument(
            '--update',
            action='store_true',
            default=False,
            help='Re-apply scraped data to products that already exist (by slug)',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.5,
            help='Seconds to wait between image downloads (default: 0.5)',
        )

    # ── Entry point ───────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        json_path       = Path(options['json_file'])
        dry_run         = options['dry_run']
        download_images = options['download_images']
        do_update       = options['update']
        delay           = options['delay']

        if not json_path.exists():
            raise CommandError(f'File not found: {json_path}')

        with open(json_path, encoding='utf-8') as fh:
            raw = json.load(fh)

        if not isinstance(raw, list):
            raise CommandError(
                'Expected a JSON array at the top level. '
                'Download the dataset from the Apify console using '
                '"Export → JSON" and try again.'
            )

        # Split the mixed array into products and finish maps
        products    = [i for i in raw if i.get('type') == 'product']
        finish_maps = [i for i in raw if i.get('type') == 'finish_map']

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n{"[DRY RUN] " if dry_run else ""}'
            f'Importing {len(products)} products '
            f'({len(finish_maps)} finish maps) from {json_path.name}'
        ))

        # ── Step 1: categories ────────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_LABEL('\n● Step 1 — product categories'))
        categories = self._ensure_categories(dry_run)

        # ── Step 2: finish objects ────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_LABEL('● Step 2 — finish types'))
        finishes = self._ensure_finishes(finish_maps, dry_run)

        # ── Step 3: product_id → finish names lookup ──────────────────────────
        product_finish_map = self._build_product_finish_map(finish_maps)

        # ── Step 4: import products ───────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_LABEL('● Step 3 — products\n'))
        stats = self._import_products(
            products, categories, finishes, product_finish_map,
            dry_run=dry_run,
            download_images=download_images,
            do_update=do_update,
            delay=delay,
        )

        # ── Summary ───────────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f'\n{"[DRY RUN] " if dry_run else ""}Done.\n'
            f'  Created  : {stats["created"]}\n'
            f'  Updated  : {stats["updated"]}\n'
            f'  Skipped  : {stats["skipped"]}\n'
            f'  Errors   : {stats["errors"]}\n'
            f'  Images ↓ : {stats["images"]}'
        ))

    # ── Step 1: categories ────────────────────────────────────────────────────

    def _ensure_categories(self, dry_run):
        categories = {}
        for defn in CATEGORY_DEFS:
            if not dry_run:
                cat, created = ProductCategory.objects.get_or_create(
                    slug=defn['slug'],
                    defaults={
                        'name':       defn['name'],
                        'use_type':   defn['use_type'],
                        'sort_order': defn['sort_order'],
                        'icon':       defn['icon'],
                    },
                )
                status = 'created' if created else 'exists '
            else:
                cat    = None
                status = 'dry-run'

            self.stdout.write(f'  [{status}] {defn["name"]}')

            for raw_key, slug in USE_TYPE_TO_SLUG.items():
                if slug == defn['slug']:
                    categories[raw_key] = cat

        return categories

    # ── Step 2: finish types ──────────────────────────────────────────────────

    def _ensure_finishes(self, finish_maps, dry_run):
        """
        Reads finish names from the finish_map items (not from product items).
        Returns {finish_name: Finish instance}.
        """
        seen = {}   # lower → original casing (first seen wins)
        for item in finish_maps:
            fname = (item.get('finish_name') or '').strip()
            if fname and fname.lower() not in seen:
                seen[fname.lower()] = fname

        finishes = {}
        for i, (lower_name, display_name) in enumerate(sorted(seen.items())):
            icon = FINISH_ICONS.get(lower_name, '')
            if not dry_run:
                obj, created = Finish.objects.get_or_create(
                    slug=slugify(display_name),
                    defaults={'name': display_name, 'sort_order': i * 10, 'icon': icon},
                )
                status = 'created' if created else 'exists '
            else:
                obj    = None
                status = 'dry-run'

            finishes[display_name] = obj
            self.stdout.write(f'  [{status}] {display_name}')

        return finishes

    # ── Step 3: product_id → finish names lookup ──────────────────────────────

    def _build_product_finish_map(self, finish_maps):
        """
        Inverts the finish_map structure so we can look up finishes by product_id.
        Returns {product_id_str: [finish_name, ...]}
        """
        result = {}
        for item in finish_maps:
            fname = (item.get('finish_name') or '').strip()
            if not fname:
                continue
            for pid in (item.get('product_ids') or []):
                result.setdefault(str(pid), []).append(fname)
        return result

    # ── Step 4: products ──────────────────────────────────────────────────────

    def _import_products(self, products, categories, finishes, product_finish_map,
                         *, dry_run, download_images, do_update, delay):
        stats = dict(created=0, updated=0, skipped=0, errors=0, images=0)

        for item in products:
            name = (item.get('name') or '').strip()
            if not name:
                self.stdout.write(self.style.WARNING('  ⚠  Skipping item with no name'))
                continue

            slug = slugify(name)

            # -- Resolve fields ------------------------------------------------
            use_raw      = (item.get('use_type') or 'interior').lower()
            use_key      = use_raw if use_raw in categories else 'interior'
            category     = categories.get(use_key)

            description  = item.get('description') or ''
            short_desc   = (item.get('short_desc') or '')[:320]
            valpaint_url = item.get('valpaint_url') or ''
            product_id   = str(item.get('product_id') or '')
            image_url    = item.get('image_url') or ''       # single hero image
            gallery      = item.get('gallery_images') or []  # full gallery

            # Look up finishes for this product via the inverted map
            finish_names     = product_finish_map.get(product_id, [])
            item_finish_objs = [
                finishes[fname]
                for fname in finish_names
                if fname in finishes and finishes[fname]
            ]

            # -- Dry run -------------------------------------------------------
            if dry_run:
                self.stdout.write(
                    f'  [DRY] {name[:50]:<50} | use={use_key:<10} '
                    f'| finishes={finish_names} | images={len(gallery)}'
                )
                stats['created'] += 1
                continue

            # -- Real import ---------------------------------------------------
            existing = ValpaintProduct.objects.filter(slug=slug).first()

            if existing and not do_update:
                stats['skipped'] += 1
                self.stdout.write(f'  –  (skip) {name}')
                continue

            try:
                if existing:
                    product = existing
                    if category:
                        product.category = category
                    if description:
                        product.description = description
                    if short_desc:
                        product.short_desc = short_desc
                    if product_id:
                        product.sku = product_id
                    if valpaint_url:
                        product.valpaint_url = valpaint_url
                    product.is_active = True
                    product.save()
                    stats['updated'] += 1
                    label = '↻'
                else:
                    product = ValpaintProduct.objects.create(
                        name         = name,
                        slug         = slug,
                        sku          = product_id,
                        category     = category,
                        short_desc   = short_desc,
                        description  = description,
                        valpaint_url = valpaint_url,
                        image_alt    = name,
                        is_active    = True,
                        in_stock     = True,
                    )
                    stats['created'] += 1
                    label = '✓'

                # Sync finishes M2M
                if item_finish_objs:
                    product.finishes.set(item_finish_objs)

                # Download hero image (image_url, not images[0])
                img_status = ''
                if download_images and image_url and not product.image:
                    downloaded = self._download_image(product, image_url)
                    if downloaded:
                        stats['images'] += 1
                        img_status = ' [img ✓]'
                    if delay:
                        time.sleep(delay)

                self.stdout.write(f'  {label}  {name}{img_status}')

            except Exception as exc:
                stats['errors'] += 1
                self.stdout.write(self.style.ERROR(f'  ✗  {name}: {exc}'))

        return stats

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _download_image(self, product, url):
        try:
            resp = requests.get(url, timeout=20, headers={
                'User-Agent': 'Nestova/1.0 (product import)',
                'Referer':    'https://www.valpaint.it/',
            })
            resp.raise_for_status()
            ext = url.split('?')[0].rsplit('.', 1)[-1].lower()
            if ext not in ('jpg', 'jpeg', 'png', 'webp'):
                ext = 'jpg'
            filename = f'{product.slug}.{ext}'
            product.image.save(filename, ContentFile(resp.content), save=True)
            return True
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'    ↓ image failed ({exc})'))
            return False