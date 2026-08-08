"""
management/commands/import_pineleaf.py
=======================================
Import crawled Pineleaf Estates properties from an Apify dataset
into the Nestova Property model.

USAGE
-----
# Fetch live from Apify dataset
python manage.py import_pineleaf --dataset-id <APIFY_DATASET_ID>

# Load from a local JSON file (after downloading from Apify)
python manage.py import_pineleaf --from-file pineleaf_data.json

# Dry run (preview without saving)
python manage.py import_pineleaf --dataset-id <ID> --dry-run

# Skip downloading images (faster; use if you only want text data first)
python manage.py import_pineleaf --dataset-id <ID> --skip-images

SETUP
-----
pip install apify-client requests Pillow
Set APIFY_API_TOKEN in your .env (or Django settings) OR pass --apify-token.
"""

import json
import os
import re
import time
from decimal import Decimal, InvalidOperation
from io import BytesIO

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

# ──────────────────────────────────────────────────────────────────────────────
# Adjust these imports if your app is named differently
# ──────────────────────────────────────────────────────────────────────────────
from properties.models import (
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

PINELEAF_NAME    = 'Pineleaf Estates and Properties Limited'
PINELEAF_WEBSITE = 'https://pineleafestates.com'
PINELEAF_HQ      = 'Port Harcourt, Rivers State'

DEFAULT_STATE_NAME = 'Rivers'
DEFAULT_STATE_CODE = 'RV'
DEFAULT_CITY_NAME  = 'Port Harcourt'

# Maps scraped type strings → PropertyType.TYPE_CHOICES keys
PROPERTY_TYPE_MAP = {
    'semi_detached':    'semi_detached',
    'semi detached':    'semi_detached',
    'terrace':          'terrace',
    'townhouse':        'terrace',
    'duplex':           'duplex',
    'bungalow':         'bungalow',
    'villa':            'villa',
    'mansion':          'mansion',
    'penthouse':        'penthouse',
    'studio':           'studio',
    'maisonette':       'maisonette',
    'mini_flat':        'mini_flat',
    'mini flat':        'mini_flat',
    'self_contain':     'self_contain',
    'self contain':     'self_contain',
    'residential_land': 'residential_land',
    'residential land': 'residential_land',
    'commercial_land':  'commercial_land',
    'commercial land':  'commercial_land',
    'agricultural_land':'agricultural_land',
    'industrial_land':  'industrial_land',
    'estate_house':     'estate_house',
    '3_bed_flat':       '3_bed_flat',
    '2_bed_flat':       '2_bed_flat',
    '1_bed_flat':       '1_bed_flat',
    '4_bed_flat':       '4_bed_flat',
    'shop':             'shop',
    'office':           'office',
    'warehouse':        'warehouse',
    'event_center':     'event_center',
    'detached_house':   'detached_house',
    'detached house':   'detached_house',
}

# Category assignment per type code
TYPE_CATEGORY_MAP = {
    'detached_house': 'residential', 'semi_detached': 'residential',
    'terrace': 'residential', 'duplex': 'residential', 'bungalow': 'residential',
    'mansion': 'residential', 'villa': 'residential', 'studio': 'residential',
    '1_bed_flat': 'residential', '2_bed_flat': 'residential',
    '3_bed_flat': 'residential', '4_bed_flat': 'residential',
    'penthouse': 'residential', 'maisonette': 'residential',
    'serviced_apt': 'residential', 'self_contain': 'residential',
    'room_parlour': 'residential', 'mini_flat': 'residential',
    'boys_quarters': 'residential', 'estate_house': 'residential',
    'cottage': 'residential',
    'residential_land': 'land', 'commercial_land': 'land',
    'agricultural_land': 'land', 'industrial_land': 'land',
    'mixed_use_land': 'land',
    'office': 'commercial', 'shop': 'commercial', 'mall': 'commercial',
    'showroom': 'commercial', 'warehouse': 'commercial', 'factory': 'commercial',
    'hotel': 'commercial', 'event_center': 'commercial',
    'filling_station': 'commercial',
    'compound': 'special', 'farm_house': 'special',
    'student_accommodation': 'special',
}


# ─────────────────────────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = 'Import Pineleaf Estates properties from an Apify dataset or JSON file'

    # ── CLI args ─────────────────────────────────────────────────────────────
    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--dataset-id',
            help='Apify Dataset ID from your actor run (e.g. abc123xyz)',
        )
        group.add_argument(
            '--from-file',
            metavar='PATH',
            help='Load from a local JSON file exported from Apify',
        )

        parser.add_argument(
            '--apify-token',
            default=os.environ.get('APIFY_API_TOKEN', ''),
            help='Apify API token (or set APIFY_API_TOKEN env var)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=65,
            help='Maximum properties to import (default: 65)',
        )
        parser.add_argument(
            '--skip-images',
            action='store_true',
            help='Skip downloading images (much faster; text only)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be imported without touching the DB',
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update price/description of already-imported properties',
        )

    # ── Entry point ──────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        self.skip_images    = options['skip_images']
        self.dry_run        = options['dry_run']
        self.update_existing = options['update_existing']

        if self.dry_run:
            self.stdout.write(self.style.WARNING('⚠  DRY RUN — nothing will be saved\n'))

        # ── 1. Fetch items ────────────────────────────────────────────────────
        if options['from_file']:
            items = self._load_from_file(options['from_file'], options['limit'])
        else:
            items = self._fetch_apify_dataset(
                options['dataset_id'],
                options['apify_token'],
                options['limit'],
            )

        self.stdout.write(f'📦  Loaded {len(items)} items\n')
        if not items:
            raise CommandError(
                'No items found. Make sure your Apify actor run has finished '
                'and the dataset ID is correct.'
            )

        # ── 2. Bootstrap FK objects (once) ────────────────────────────────────
        if not self.dry_run:
            self.developer = self._bootstrap_developer()
            self.default_state = self._bootstrap_state()
        else:
            self.developer = None
            self.default_state = None

        # ── 3. Import each property ───────────────────────────────────────────
        imported = skipped = errors = 0
        for idx, item in enumerate(items, 1):
            title = (item.get('title') or '').strip()
            self.stdout.write(f'[{idx:>3}/{len(items)}] {title[:65]}')
            if not title:
                self.stdout.write(self.style.WARNING('       ↳ No title — skip'))
                skipped += 1
                continue

            try:
                result = self._import_one(item)
                if result == 'imported':
                    imported += 1
                    self.stdout.write(self.style.SUCCESS('       ↳ ✓ imported'))
                elif result == 'updated':
                    imported += 1
                    self.stdout.write(self.style.SUCCESS('       ↳ ↻ updated'))
                elif result == 'dry_run':
                    imported += 1
                    self.stdout.write(self.style.WARNING('       ↳ (dry-run preview)'))
                else:
                    skipped += 1
                    self.stdout.write(f'       ↳ already exists — skip')
            except Exception as exc:
                errors += 1
                self.stdout.write(self.style.ERROR(f'       ↳ ERROR: {exc}'))

        # ── 4. Summary ────────────────────────────────────────────────────────
        self.stdout.write('\n' + '─' * 60)
        self.stdout.write(self.style.SUCCESS(
            f'  Done!  Imported/updated: {imported}  '
            f'Skipped: {skipped}  Errors: {errors}'
        ))

    # ──────────────────────────────────────────────────────────────────────────
    # DATA FETCHERS
    # ──────────────────────────────────────────────────────────────────────────

    def _load_from_file(self, path, limit):
        if not os.path.exists(path):
            raise CommandError(f'File not found: {path}')
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and 'items' in data:
            data = data['items']
        return data[:limit]

    def _fetch_apify_dataset(self, dataset_id, token, limit):
        if not token:
            raise CommandError(
                'Apify API token is required. Set APIFY_API_TOKEN environment variable '
                'or pass --apify-token.'
            )
        url = f'https://api.apify.com/v2/datasets/{dataset_id}/items'
        params = {'token': token, 'limit': limit, 'clean': 'true', 'format': 'json'}

        self.stdout.write(f'🌐  Fetching dataset {dataset_id} from Apify …')
        try:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise CommandError(f'Apify API request failed: {exc}')

    # ──────────────────────────────────────────────────────────────────────────
    # BOOTSTRAP HELPERS
    # ──────────────────────────────────────────────────────────────────────────

    def _bootstrap_developer(self):
        dev, created = Developer.objects.get_or_create(
            name=PINELEAF_NAME,
            defaults={
                'tagline':      'Building Premium Estates in Rivers State',
                'website':      PINELEAF_WEBSITE,
                'headquarters': PINELEAF_HQ,
                'is_active':    True,
                'is_featured':  True,
            },
        )
        if created:
            self.stdout.write(f'  🏢  Created developer: {dev.name}')
        return dev

    def _bootstrap_state(self):
        state, created = State.objects.get_or_create(
            name=DEFAULT_STATE_NAME,
            defaults={'code': DEFAULT_STATE_CODE, 'is_active': True},
        )
        if created:
            self.stdout.write(f'  🗺   Created state: {state.name}')
        return state

    def _get_or_create_city(self, name):
        name = (name or DEFAULT_CITY_NAME).strip().title()
        # Cap at 100 chars (model limit)
        name = name[:100]
        city, _ = City.objects.get_or_create(
            name=name,
            state=self.default_state,
            defaults={'is_active': True},
        )
        return city

    def _get_or_create_property_type(self, code):
        code = code or 'estate_house'
        category = TYPE_CATEGORY_MAP.get(code, 'residential')
        pt, _ = PropertyType.objects.get_or_create(
            name=code,
            defaults={
                'category':     category,
                'is_active':    True,
                'display_order': 0,
            },
        )
        return pt

    def _get_or_create_status(self, code):
        st, _ = PropertyStatus.objects.get_or_create(name=code)
        return st

    # ──────────────────────────────────────────────────────────────────────────
    # PARSERS
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_price(raw) -> Decimal:
        """Convert '₦45,000,000' or '45000000' to Decimal."""
        if not raw:
            return Decimal('0')
        cleaned = re.sub(r'[^\d.]', '', str(raw))
        if not cleaned:
            return Decimal('0')
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return Decimal('0')

    @staticmethod
    def _map_type(scraped_type: str, title: str = '') -> str:
        """Return a TYPE_CHOICES key from the scraped type string."""
        if not scraped_type:
            scraped_type = ''
        # Direct match
        key = scraped_type.strip().lower().replace('-', '_')
        if key in PROPERTY_TYPE_MAP:
            return PROPERTY_TYPE_MAP[key]
        # Partial match on type string or title
        combined = f'{scraped_type} {title}'.lower()
        for keyword, code in PROPERTY_TYPE_MAP.items():
            if keyword in combined:
                return code
        return 'estate_house'

    @staticmethod
    def _parse_sqft(value, bedrooms=0) -> int:
        """Return a reasonable square feet value."""
        if value and int(value) > 0:
            return int(value)
        # Rough fallback: 700 sqft per bedroom for Nigerian estates
        return max(bedrooms * 700, 1200)

    @staticmethod
    def _extract_bool_features(item: dict) -> dict:
        """Pull boolean feature flags from the scraped data."""
        features = item.get('features') or {}
        amenity_text = ' '.join(item.get('amenities') or []).lower()
        page_text    = (item.get('description') or '').lower()
        combined     = f'{amenity_text} {page_text}'

        def has(*words):
            return any(w in combined for w in words) or bool(features.get(f'has_{words[0]}'))

        return {
            'has_pool':     has('pool', 'swimming'),
            'has_gym':      has('gym', 'fitness'),
            'has_security': has('security', 'gatehouse', 'fence'),
            'has_balcony':  has('balcon'),
            'has_garden':   has('garden', 'landscap'),
            'has_garage':   has('garage'),
            'has_ac':       has('air condition', 'ac ', ' ac', 'a/c'),
            'is_furnished': has('furnished'),
            'pet_friendly': has('pet'),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # CORE IMPORT
    # ──────────────────────────────────────────────────────────────────────────

    def _import_one(self, item: dict) -> str:
        """Process a single scraped item. Returns 'imported'|'updated'|'exists'|'dry_run'."""

        title       = (item.get('title') or '').strip()
        description = (item.get('description') or '').strip()
        source_url  = item.get('url', '')

        # ── prices & specs ──────────────────────────────────────────────────
        raw_price    = item.get('price') or item.get('rawPrice') or ''
        price        = self._parse_price(raw_price)
        bedrooms     = int(item.get('bedrooms') or 0)
        bathrooms    = int(item.get('bathrooms') or 0)
        square_feet  = self._parse_sqft(item.get('squareFeet') or 0, bedrooms)
        parking      = int(item.get('parkingSpaces') or 0)
        year_built   = item.get('yearBuilt') or None

        # ── location ────────────────────────────────────────────────────────
        location  = (item.get('location') or '').strip() or DEFAULT_CITY_NAME
        city_name = (item.get('city') or '').strip() or DEFAULT_CITY_NAME
        address   = location or DEFAULT_CITY_NAME

        # ── type & status ────────────────────────────────────────────────────
        type_code   = self._map_type(item.get('propertyType', ''), title)
        status_code = item.get('status') or 'for_sale'
        if status_code not in ('for_sale', 'for_rent', 'sold', 'rented', 'pending'):
            status_code = 'for_sale'

        # ── boolean features ─────────────────────────────────────────────────
        bool_flags = self._extract_bool_features(item)

        # ── DRY RUN ─────────────────────────────────────────────────────────
        if self.dry_run:
            self.stdout.write(
                f'       ↳ [{status_code}] {type_code} | '
                f'₦{float(price):,.0f} | {bedrooms}bd/{bathrooms}ba | {city_name}'
            )
            return 'dry_run'

        # ── Check for existing property (avoid duplicates) ───────────────────
        existing = Property.objects.filter(
            title=title,
            developer=self.developer,
        ).first()

        if existing and not self.update_existing:
            return 'exists'

        # ── Resolve FK objects ────────────────────────────────────────────────
        city     = self._get_or_create_city(city_name)
        prop_type = self._get_or_create_property_type(type_code)
        prop_status = self._get_or_create_status(status_code)

        with transaction.atomic():
            if existing and self.update_existing:
                # Update core fields only
                existing.description = description or existing.description
                existing.price       = price if price > 0 else existing.price
                existing.address     = address or existing.address
                existing.save(update_fields=['description', 'price', 'address', 'updated_at'])
                prop = existing
                action = 'updated'
            else:
                # Build additional_features JSON (store source URL, pineleaf-specific data)
                additional_features = {
                    'source_url':     source_url,
                    'source':         'pineleaf_estates',
                    'imported_at':    time.strftime('%Y-%m-%d'),
                }

                prop = Property(
                    title=title,
                    description=description,
                    state=self.default_state,
                    city=city,
                    address=address[:499],
                    property_type=prop_type,
                    status=prop_status,
                    bedrooms=bedrooms,
                    bathrooms=bathrooms,
                    square_feet=square_feet,
                    price=price if price > 0 else Decimal('1'),
                    parking_spaces=parking,
                    year_built=year_built,
                    developer=self.developer,
                    is_new=True,
                    is_active=True,
                    additional_features=additional_features,
                    **bool_flags,
                )
                prop.save()
                action = 'imported'

            # ── Images ──────────────────────────────────────────────────────
            if not self.skip_images and action == 'imported':
                images = item.get('images') or []
                self._save_images(prop, images, title)

            # ── Amenities ────────────────────────────────────────────────────
            if action == 'imported':
                amenities = item.get('amenities') or []
                self._save_amenities(prop, amenities)

        return action

    # ──────────────────────────────────────────────────────────────────────────
    # IMAGE SAVING
    # ──────────────────────────────────────────────────────────────────────────

    def _download_image(self, url: str, filename: str):
        """Download an image URL and return a ContentFile, or None on failure."""
        try:
            resp = requests.get(
                url,
                timeout=20,
                headers={
                    'User-Agent': (
                        'Mozilla/5.0 (compatible; NestovaBot/1.0; '
                        '+https://nestova.com/bot)'
                    ),
                    'Referer': PINELEAF_WEBSITE,
                },
                stream=True,
            )
            resp.raise_for_status()

            # Determine extension from content-type
            content_type = resp.headers.get('content-type', 'image/jpeg')
            ext_map = {
                'image/jpeg': 'jpg', 'image/jpg': 'jpg',
                'image/png': 'png', 'image/webp': 'webp',
                'image/gif': 'gif',
            }
            ext = ext_map.get(content_type.split(';')[0].strip(), 'jpg')
            fname = f'{filename}.{ext}'

            # Read up to 8 MB
            content = BytesIO()
            size = 0
            for chunk in resp.iter_content(chunk_size=8192):
                content.write(chunk)
                size += len(chunk)
                if size > 8 * 1024 * 1024:
                    break
            return ContentFile(content.getvalue(), name=fname)

        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(f'       ↳ ⚠ Image skip ({url[:50]}): {exc}')
            )
            return None

    def _save_images(self, prop: Property, image_urls: list, title: str):
        base = slugify(title)[:35]
        for idx, url in enumerate(image_urls[:8]):
            if not url:
                continue
            fname = f'pineleaf_{base}_{idx}'
            file  = self._download_image(url, fname)
            if not file:
                continue

            if idx == 0 and not prop.featured_image:
                # Set as the featured (hero) image
                prop.featured_image.save(file.name, file, save=True)
            else:
                # Add to gallery
                pi = PropertyImage(
                    property=prop,
                    caption=f'{title} — photo {idx + 1}',
                    is_primary=False,
                    order=idx,
                )
                pi.image.save(file.name, file, save=False)
                pi.save()

    # ──────────────────────────────────────────────────────────────────────────
    # AMENITY SAVING
    # ──────────────────────────────────────────────────────────────────────────

    def _save_amenities(self, prop: Property, amenity_names: list):
        for name in amenity_names:
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