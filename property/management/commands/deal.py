"""
management/commands/import_dealclinchers.py
============================================
Import Dealclinchers Homes properties from an Apify dataset
or a locally saved JSON export into the Nestova Property model.

DATASET STRUCTURE (from live scraper)
────────────────────────────────────────────────────────────────
  26 total items · 3 are "Oh oh! Page not found." (auto-skipped)
  23 valid properties across Lagos, Abuja, Ogun, Oyo

PRICE FIELD — READ THIS
────────────────────────────────────────────────────────────────
  The dataset has three price fields. ONLY `price` is correct:

    price      → the actual outright price  ← USE THIS
    price_min  → always ₦2,000,000 (minimum payment-plan tier)
    price_max  → highest payment plan tier

  price_min and price_max are NOT property prices; they come from
  the payment_plans array scraped off each page. Do not use them.

STATUS MAPPING
────────────────────────────────────────────────────────────────
  Scraper     → PropertyStatus
  for_sale    → for_sale
  sold_out    → sold       (is_sold_out == True)
  off_plan    → pending    (is_off_plan == True  + is_new=True)

PROPERTY TYPE RESOLUTION
────────────────────────────────────────────────────────────────
  1. Direct map on property_type slug
  2. If property_type_raw contains "Land" → residential_land
  3. Keyword scan across title
  4. Fallback → estate_house

DEDUP KEY
────────────────────────────────────────────────────────────────
  source_url is unique per listing; stored in additional_features.
  On re-runs, existing properties are skipped (or updated with
  --update-existing).

IMAGES
────────────────────────────────────────────────────────────────
  featured_image == images[0] in every item.
  images[0]  → Property.featured_image
  images[1:] → PropertyImage gallery rows (capped at 12 extra)

USAGE
────────────────────────────────────────────────────────────────
  # DEV — 5 items, no images, dry run first:
  python manage.py import_dealclinchers --dataset-id <ID> --limit 5 --dry-run
  python manage.py import_dealclinchers --dataset-id <ID> --limit 5 --skip-images

  # FULL run:
  python manage.py import_dealclinchers --dataset-id <ID>

  # From local file:
  python manage.py import_dealclinchers --from-file dataset_web-scraper_*.json

  # Re-import and overwrite price / description:
  python manage.py import_dealclinchers --dataset-id <ID> --update-existing

SETUP
────────────────────────────────────────────────────────────────
  pip install requests Pillow
  Set APIFY_API_TOKEN in your .env  OR  pass --apify-token on CLI.
"""

import json
import os
import re
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Optional

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from property.models import (
    City,
    Developer,
    Property,
    PropertyAmenity,
    PropertyAmenityLink,
    PropertyImage,
    PropertyStatus,
    PropertyType,
    State,
)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

DEVELOPER_NAME    = 'Dealclinchers Homes Limited'
DEVELOPER_WEBSITE = 'https://dealclinchersltd.com'
DEVELOPER_HQ      = 'Lagos, Nigeria'

# Scraped state name (lowercase) → (canonical DB name, state code)
STATE_REGISTRY = {
    'lagos':   ('Lagos',                     'LA'),
    'abuja':   ('Federal Capital Territory', 'FCT'),
    'fct':     ('Federal Capital Territory', 'FCT'),
    'ogun':    ('Ogun',                      'OG'),
    'oyo':     ('Oyo',                       'OY'),
    'rivers':  ('Rivers',                    'RV'),
    'delta':   ('Delta',                     'DE'),
    'anambra': ('Anambra',                   'AN'),
    'enugu':   ('Enugu',                     'EN'),
    'imo':     ('Imo',                       'IM'),
    'kano':    ('Kano',                      'KN'),
    'kaduna':  ('Kaduna',                    'KD'),
    'kwara':   ('Kwara',                     'KW'),
}

DEFAULT_STATE_NAME = 'Lagos'
DEFAULT_STATE_CODE = 'LA'
DEFAULT_CITY_NAME  = 'Lagos'

# Scraper property_type slug → PropertyType.TYPE_CHOICES key
PROPERTY_TYPE_MAP = {
    'studio':          'studio',
    'semi_detached':   'semi_detached',
    'terrace':         'terrace',
    'fully_detached':  'detached_house',
    'detached_house':  'detached_house',
    'duplex':          'duplex',
    'bungalow':        'bungalow',
    'villa':           'villa',
    'mansion':         'mansion',
    'penthouse':       'penthouse',
    'maisonette':      'maisonette',
    'serviced_apt':    'serviced_apt',
    'mini_flat':       'mini_flat',
    'self_contain':    'self_contain',
    'apartment':       '2_bed_flat',
    '1_bed_flat':      '1_bed_flat',
    '2_bed_flat':      '2_bed_flat',
    '3_bed_flat':      '3_bed_flat',
    '4_bed_flat':      '4_bed_flat',
    'residential_land':'residential_land',
    'commercial_land': 'commercial_land',
    'land':            'residential_land',
    'commercial':      'office',
    'office':          'office',
    'shop':            'shop',
    'warehouse':       'warehouse',
    'estate_house':    'estate_house',
}

TYPE_CATEGORY_MAP = {
    'detached_house':   'residential', 'semi_detached':  'residential',
    'terrace':          'residential', 'duplex':         'residential',
    'bungalow':         'residential', 'mansion':        'residential',
    'villa':            'residential', 'studio':         'residential',
    '1_bed_flat':       'residential', '2_bed_flat':     'residential',
    '3_bed_flat':       'residential', '4_bed_flat':     'residential',
    'penthouse':        'residential', 'maisonette':     'residential',
    'serviced_apt':     'residential', 'self_contain':   'residential',
    'room_parlour':     'residential', 'mini_flat':      'residential',
    'boys_quarters':    'residential', 'estate_house':   'residential',
    'cottage':          'residential',
    'residential_land': 'land',        'commercial_land':'land',
    'agricultural_land':'land',        'industrial_land':'land',
    'mixed_use_land':   'land',
    'office':           'commercial',  'shop':           'commercial',
    'mall':             'commercial',  'showroom':       'commercial',
    'warehouse':        'commercial',  'factory':        'commercial',
    'hotel':            'commercial',  'event_center':   'commercial',
    'filling_station':  'commercial',
}

# Scraper status string → PropertyStatus.STATUS_CHOICES key
STATUS_MAP = {
    'for_sale': 'for_sale',
    'sold_out': 'sold',
    'off_plan': 'pending',
}

# 404-page markers — skip any item whose featured_image is this pixel
_404_IMAGE = 'https://pixel.wp.com/g.gif'


# ─────────────────────────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = 'Import Dealclinchers Homes properties from Apify or a local JSON file'

    # ── CLI args ──────────────────────────────────────────────────────────────
    def add_arguments(self, parser):
        source = parser.add_mutually_exclusive_group(required=True)
        source.add_argument(
            '--dataset-id',
            help='Apify Dataset ID from the actor run (e.g. abc123xyz)',
        )
        source.add_argument(
            '--from-file',
            metavar='PATH',
            help='Path to a local JSON file exported from Apify',
        )
        parser.add_argument(
            '--apify-token',
            default=os.environ.get('APIFY_API_TOKEN', ''),
            help='Apify API token (or set APIFY_API_TOKEN in .env)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Max items to process (default: 50). Use --limit 5 during dev.',
        )
        parser.add_argument(
            '--skip-images',
            action='store_true',
            help='Skip all image downloads — much faster for dev/test runs',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be imported without touching the database',
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Overwrite price and description on already-imported properties',
        )

    # ── Entry point ───────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        self.skip_images     = options['skip_images']
        self.dry_run         = options['dry_run']
        self.update_existing = options['update_existing']

        if self.dry_run:
            self.stdout.write(self.style.WARNING('⚠  DRY RUN — no database writes\n'))

        # ── 1. Load items ──────────────────────────────────────────────────────
        if options['from_file']:
            items = self._load_from_file(options['from_file'], options['limit'])
        else:
            items = self._fetch_apify(
                options['dataset_id'],
                options['apify_token'],
                options['limit'],
            )

        self.stdout.write(f'📦  Loaded {len(items)} raw items\n')
        if not items:
            raise CommandError(
                'No items returned. Check that the Apify actor run has '
                'finished and the dataset ID is correct.'
            )

        # ── 2. Bootstrap developer once ────────────────────────────────────────
        if not self.dry_run:
            self.developer = self._bootstrap_developer()
        else:
            self.developer = None

        # ── 3. Process each item ───────────────────────────────────────────────
        imported = updated = skipped = no_price = errors = 0

        for idx, item in enumerate(items, 1):
            title = (item.get('title') or '').strip()
            self.stdout.write(f'[{idx:>3}/{len(items)}] {title[:65]}')

            # Skip 404 pages (two guards: title text + WordPress pixel image)
            if (
                not title
                or 'page not found' in title.lower()
                or item.get('featured_image') == _404_IMAGE
            ):
                self.stdout.write(self.style.WARNING('       ↳ 404 / empty — skip'))
                skipped += 1
                continue

            try:
                result = self._import_one(item)

                if result == 'imported':
                    imported += 1
                    if item.get('_had_price'):
                        self.stdout.write(self.style.SUCCESS('       ↳ ✓ imported'))
                    else:
                        no_price += 1
                        self.stdout.write(
                            self.style.SUCCESS('       ↳ ✓ imported') + '  ' +
                            self.style.WARNING('⚠ price=NULL')
                        )
                elif result == 'updated':
                    updated += 1
                    self.stdout.write(self.style.SUCCESS('       ↳ ↻ updated'))
                elif result == 'dry_run':
                    imported += 1
                elif result == 'exists':
                    skipped += 1
                    self.stdout.write('       ↳ already exists — skip')

            except Exception as exc:
                errors += 1
                self.stdout.write(self.style.ERROR(f'       ↳ ERROR: {exc}'))

        # ── 4. Summary ─────────────────────────────────────────────────────────
        self.stdout.write('\n' + '─' * 60)
        self.stdout.write(self.style.SUCCESS(
            f'  Done!  Imported: {imported}  Updated: {updated}  '
            f'Skipped: {skipped}  Errors: {errors}'
        ))
        if no_price:
            self.stdout.write(self.style.WARNING(
                f'  ⚠  {no_price} propert{"y" if no_price == 1 else "ies"} '
                f'saved with price=NULL — update manually or re-run with '
                f'--update-existing once the source has a price.'
            ))

    # ─────────────────────────────────────────────────────────────────────────
    # DATA FETCHERS
    # ─────────────────────────────────────────────────────────────────────────

    def _load_from_file(self, path: str, limit: int) -> list:
        if not os.path.exists(path):
            raise CommandError(f'File not found: {path}')
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and 'items' in data:
            data = data['items']
        return data[:limit]

    def _fetch_apify(self, dataset_id: str, token: str, limit: int) -> list:
        if not token:
            raise CommandError(
                'Apify API token required. Set APIFY_API_TOKEN in your .env '
                'or pass --apify-token on the command line.'
            )
        url    = f'https://api.apify.com/v2/datasets/{dataset_id}/items'
        params = {'token': token, 'limit': limit, 'clean': 'true', 'format': 'json'}

        self.stdout.write(f'🌐  Fetching dataset {dataset_id} from Apify …')
        try:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise CommandError(f'Apify request failed: {exc}')

    # ─────────────────────────────────────────────────────────────────────────
    # BOOTSTRAP HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _bootstrap_developer(self) -> Developer:
        dev, created = Developer.objects.get_or_create(
            name=DEVELOPER_NAME,
            defaults={
                'tagline':      'Premium Real Estate Across Nigeria',
                'website':      DEVELOPER_WEBSITE,
                'headquarters': DEVELOPER_HQ,
                'is_active':    True,
                'is_featured':  True,
            },
        )
        if created:
            self.stdout.write(f'  🏢  Created developer: {dev.name}')
        return dev

    def _get_or_create_state(self, raw: str) -> State:
        key        = (raw or '').strip().lower()
        name, code = STATE_REGISTRY.get(key, (DEFAULT_STATE_NAME, DEFAULT_STATE_CODE))
        state, created = State.objects.get_or_create(
            name=name,
            defaults={'code': code, 'is_active': True},
        )
        if created:
            self.stdout.write(f'  🗺   Created state: {state.name}')
        return state

    def _get_or_create_city(self, raw: str, state: State) -> City:
        name = (raw or DEFAULT_CITY_NAME).strip().title()[:100]
        city, _ = City.objects.get_or_create(
            name=name,
            state=state,
            defaults={'is_active': True},
        )
        return city

    def _get_or_create_property_type(self, code: str) -> PropertyType:
        code     = code or 'estate_house'
        category = TYPE_CATEGORY_MAP.get(code, 'residential')
        pt, _    = PropertyType.objects.get_or_create(
            name=code,
            defaults={'category': category, 'is_active': True, 'display_order': 0},
        )
        return pt

    def _get_or_create_status(self, code: str) -> PropertyStatus:
        st, _ = PropertyStatus.objects.get_or_create(name=code)
        return st

    # ─────────────────────────────────────────────────────────────────────────
    # PARSERS
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_price(raw) -> Optional[Decimal]:
        """
        Convert the scraped `price` integer (e.g. 4300000) or string
        (e.g. '₦4,300,000') → Decimal.

        Returns None when the value is absent, zero, or unparseable so
        the listing shows as 'Price on Request' rather than ₦0.

        NOTE: always call this with item['price'], NOT item['price_min'].
        price_min is the lowest payment-plan tier (always ~₦2M) and is
        not the actual property price.
        """
        if raw is None:
            return None
        # Fast path: already a positive number
        if isinstance(raw, (int, float)) and raw > 0:
            return Decimal(str(int(raw)))
        cleaned = re.sub(r'[^\d.]', '', str(raw).strip())
        if not cleaned:
            return None
        try:
            value = Decimal(cleaned)
            return value if value > 0 else None
        except InvalidOperation:
            return None

    @staticmethod
    def _parse_area(raw) -> Optional[int]:
        """Parse '500 SQM', '450 sqm', or a plain number → int, else None."""
        if not raw:
            return None
        cleaned = re.sub(r'[^\d.]', '', str(raw).strip())
        try:
            v = int(float(cleaned))
            return v if v > 0 else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _map_type(scraped_type: str, raw_type: str = '', title: str = '') -> str:
        """
        Resolve a PropertyType.TYPE_CHOICES key from:
          1. Direct match on scraped property_type slug
          2. property_type_raw override for Land listings
          3. Keyword scan of title
          4. Fallback → estate_house
        """
        slug = (scraped_type or '').strip().lower()

        # Step 1 — direct slug match
        if slug in PROPERTY_TYPE_MAP:
            resolved = PROPERTY_TYPE_MAP[slug]
            # Step 2 — override to land when raw explicitly says 'Land'
            # (e.g. property_type='studio' but raw='Land')
            if 'land' in (raw_type or '').lower() and TYPE_CATEGORY_MAP.get(resolved) != 'land':
                return 'residential_land'
            return resolved

        # Step 3 — keyword scan on title
        combined = f'{scraped_type} {title}'.lower()
        for keyword, code in PROPERTY_TYPE_MAP.items():
            if keyword in combined:
                return code

        return 'estate_house'

    @staticmethod
    def _resolve_status(item: dict) -> tuple:
        """
        Return (status_code: str, is_new: bool).

        Priority order:
          is_sold_out flag → 'sold'
          is_off_plan flag → 'pending' + is_new=True
          status field     → mapped via STATUS_MAP
          fallback         → 'for_sale'
        """
        if item.get('is_sold_out'):
            return 'sold', False
        if item.get('is_off_plan'):
            return 'pending', True
        code = STATUS_MAP.get((item.get('status') or 'for_sale').lower(), 'for_sale')
        return code, False

    @staticmethod
    def _clean_video_url(raw: str) -> str:
        """
        Return a YouTube watch/embed URL that EmbedVideoField accepts.
        Rejects: channel URLs (@handle), about:blank, empty strings.
        Only `/watch?v=` and `/embed/` URLs are valid.
        """
        if not raw:
            return ''
        # Handle "about:blank;www.youtube.com" junk
        url = raw.split(';')[0].strip()
        invalid_markers = ['about:blank', '@dealclinchers', '@', '/channel/']
        if any(m in url for m in invalid_markers):
            return ''
        if 'youtube.com/watch' in url or 'youtu.be/' in url:
            return url
        if 'youtube.com/embed/' in url:
            # Convert embed URL to watch URL so EmbedVideoField parses it
            video_id = url.split('/embed/')[-1].split('?')[0]
            return f'https://www.youtube.com/watch?v={video_id}'
        return ''

    # ─────────────────────────────────────────────────────────────────────────
    # CORE IMPORT
    # ─────────────────────────────────────────────────────────────────────────

    def _import_one(self, item: dict) -> str:
        """
        Import or update one scraped property dict.
        Returns: 'imported' | 'updated' | 'exists' | 'dry_run'
        Side-effect: sets item['_had_price'] for the caller's no_price counter.
        """
        title      = (item.get('title') or '').strip()
        desc       = (item.get('description') or '').strip()
        source_url = (item.get('source_url') or '').strip()
        address    = (item.get('address') or item.get('city') or '').strip()

        # ── Price — use `price`, never `price_min` ─────────────────────────────
        price: Optional[Decimal] = self._parse_price(item.get('price'))
        is_cfp: bool             = bool(item.get('is_call_for_price'))
        item['_had_price']       = (price is not None) or is_cfp

        # ── Specs ──────────────────────────────────────────────────────────────
        bedrooms   = int(item.get('bedrooms')  or 0)
        bathrooms  = int(item.get('bathrooms') or 0)
        garages    = int(item.get('garages')   or 0)
        area       = self._parse_area(item.get('area_size'))
        year_built = item.get('year_built') or None

        # ── Location ───────────────────────────────────────────────────────────
        raw_state = (item.get('state') or '').strip()
        raw_city  = (item.get('city')  or '').strip()

        # ── Type & status ──────────────────────────────────────────────────────
        type_code          = self._map_type(
            item.get('property_type', ''),
            item.get('property_type_raw', ''),
            title,
        )
        status_code, is_new = self._resolve_status(item)

        # ── Badges ─────────────────────────────────────────────────────────────
        is_featured = bool(item.get('is_featured'))
        is_hot      = bool(item.get('is_hot_offer'))

        # ── Video ──────────────────────────────────────────────────────────────
        video_url = self._clean_video_url(item.get('youtube_url') or '')

        # ── JSON extras ────────────────────────────────────────────────────────
        extra = {
            'source_url':       source_url,
            'external_id':      item.get('property_id') or '',
            'legal_title':      item.get('legal_title') or '',
            'price_text':       item.get('price_text') or '',
            'price_max':        item.get('price_max'),
            'payment_plans':    item.get('payment_plans') or [],
            'has_borehole':     bool(item.get('has_borehole')),
            'has_power_supply': bool(item.get('has_power_supply')),
            'has_wifi':         bool(item.get('has_wifi')),
            'is_gated':         bool(item.get('is_gated')),
            'google_maps_url':  item.get('google_maps_url') or '',
        }

        # ── DRY RUN ────────────────────────────────────────────────────────────
        if self.dry_run:
            if is_cfp:
                price_display = 'Call for Price'
            elif price is not None:
                price_display = f'₦{float(price):,.0f}'
            else:
                price_display = 'Price TBD'

            self.stdout.write(
                f'       ↳ [{status_code}] {type_code} | '
                f'{price_display} | {bedrooms}bd/{bathrooms}ba | '
                f'{raw_city or "?"}, {raw_state or "?"}'
            )
            return 'dry_run'

        # ── Dedup — match on source_url stored in additional_features ──────────
        existing = None
        if source_url:
            existing = Property.objects.filter(
                additional_features__source_url=source_url
            ).first()
        if not existing:
            # Fallback for rows imported before source_url tracking existed
            existing = Property.objects.filter(
                title=title,
                developer=self.developer,
            ).first()

        if existing and not self.update_existing:
            return 'exists'

        # ── Resolve FK objects ─────────────────────────────────────────────────
        state       = self._get_or_create_state(raw_state)
        city        = self._get_or_create_city(raw_city, state)
        prop_type   = self._get_or_create_property_type(type_code)
        prop_status = self._get_or_create_status(status_code)

        with transaction.atomic():

            if existing and self.update_existing:
                # ── UPDATE path ───────────────────────────────────────────────
                update_fields = ['updated_at']

                if desc:
                    existing.description = desc
                    update_fields.append('description')
                if address:
                    existing.address = address
                    update_fields.append('address')
                if price is not None:
                    existing.price = price
                    update_fields.append('price')

                merged = existing.additional_features or {}
                merged.update(extra)
                existing.additional_features = merged
                update_fields.append('additional_features')

                existing.save(update_fields=update_fields)
                prop   = existing
                action = 'updated'

            else:
                # ── INSERT path ───────────────────────────────────────────────
                prop = Property(
                    title=title,
                    description=desc,
                    state=state,
                    city=city,
                    address=address[:499],
                    property_type=prop_type,
                    status=prop_status,
                    bedrooms=bedrooms,
                    bathrooms=bathrooms,
                    square_feet=area,
                    price=price,
                    is_call_for_price=is_cfp,
                    parking_spaces=garages,
                    year_built=year_built,
                    developer=self.developer,
                    # Badges
                    is_featured=is_featured,
                    is_hot=is_hot,
                    is_new=is_new,
                    # Boolean amenities — direct from scraper, no guessing
                    has_ac=bool(item.get('has_ac')),
                    has_gym=bool(item.get('has_gym')),
                    has_pool=bool(item.get('has_pool')),
                    has_security=bool(item.get('has_security')),
                    has_garage=bool(item.get('has_parking')) or garages > 0,
                    # Video
                    video_url=video_url,
                    # JSON extras
                    additional_features=extra,
                    is_active=True,
                )
                prop.save()
                action = 'imported'

            # ── Images ────────────────────────────────────────────────────────
            if not self.skip_images and action == 'imported':
                images = item.get('images') or []
                self._save_images(prop, images, title)

            # ── Amenities ─────────────────────────────────────────────────────
            if action == 'imported':
                self._save_amenities(prop, item.get('features') or [])

        return action

    # ─────────────────────────────────────────────────────────────────────────
    # IMAGE SAVING
    # ─────────────────────────────────────────────────────────────────────────

    def _download_image(self, url: str, filename: str) -> Optional[ContentFile]:
        """Download url → ContentFile, or None on any failure."""
        if not url or url == _404_IMAGE:
            return None
        try:
            resp = requests.get(
                url,
                timeout=25,
                headers={
                    'User-Agent': (
                        'Mozilla/5.0 (compatible; NestovaBot/1.0; '
                        '+https://nestovaproperty.com/bot)'
                    ),
                    'Referer': DEVELOPER_WEBSITE,
                },
                stream=True,
            )
            resp.raise_for_status()

            ctype = resp.headers.get('content-type', 'image/jpeg')
            ext   = {
                'image/jpeg': 'jpg', 'image/jpg': 'jpg',
                'image/png':  'png', 'image/webp': 'webp',
                'image/gif':  'gif',
            }.get(ctype.split(';')[0].strip(), 'jpg')

            buf  = BytesIO()
            size = 0
            for chunk in resp.iter_content(chunk_size=8192):
                buf.write(chunk)
                size += len(chunk)
                if size > 8 * 1024 * 1024:   # 8 MB cap per image
                    break

            return ContentFile(buf.getvalue(), name=f'{filename}.{ext}')

        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(f'       ↳ ⚠ image skip ({url[:55]}…): {exc}')
            )
            return None

    def _save_images(self, prop: Property, image_urls: list, title: str):
        """
        images[0]  → Property.featured_image  (always == featured_image field)
        images[1:] → PropertyImage gallery rows, capped at 12 extras
        """
        base = slugify(title)[:35]

        for idx, url in enumerate(image_urls[:13]):   # idx 0 = featured; 1-12 = gallery
            if not url or url == _404_IMAGE:
                continue

            fname = f'dealclinchers_{base}_{idx}'
            file  = self._download_image(url, fname)
            if not file:
                continue

            if idx == 0:
                # Save as the property's featured image
                prop.featured_image.save(file.name, file, save=True)
            else:
                pi = PropertyImage(
                    property=prop,
                    caption=f'{title} — photo {idx}',
                    is_primary=False,
                    order=idx,
                )
                pi.image.save(file.name, file, save=False)
                pi.save()

    # ─────────────────────────────────────────────────────────────────────────
    # AMENITY SAVING
    # ─────────────────────────────────────────────────────────────────────────

    def _save_amenities(self, prop: Property, feature_list: list):
        for name in feature_list:
            name = (name or '').strip()[:100]
            if not name:
                continue
            amenity, _ = PropertyAmenity.objects.get_or_create(
                name=name,
                defaults={'icon': 'bi bi-check-circle'},
            )
            PropertyAmenityLink.objects.get_or_create(
                property=prop,
                amenity=amenity,
                defaults={'is_available': True},
            )