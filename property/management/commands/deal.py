"""
management/commands/import_dealclinchers.py
============================================
Import scraped Dealclinchers Homes properties from an Apify dataset
into the Nestova Property model.

FIELD MAPPING (Apify scraper → Nestova)
────────────────────────────────────────────────────────────────────
  title           → Property.title
  description     → Property.description
  address         → Property.address
  area_size       → Property.square_feet   (parsed from "500 SQM")
  bedrooms        → Property.bedrooms
  bathrooms       → Property.bathrooms
  garages         → Property.parking_spaces
  price           → Property.price         (price_min used as base)
  is_call_for_price → Property.is_call_for_price
  year_built      → Property.year_built
  state           → Property.state         (dynamic; get_or_create)
  city            → Property.city          (dynamic; get_or_create)
  property_type   → Property.property_type (slug already provided)
  status          → Property.status        (mapped below)
  is_featured     → Property.is_featured
  is_hot_offer    → Property.is_hot
  is_off_plan     → status mapped to 'pending' + is_new=True
  is_sold_out     → status mapped to 'sold'
  has_ac          → Property.has_ac
  has_gym         → Property.has_gym
  has_pool        → Property.has_pool
  has_security    → Property.has_security
  has_parking     → Property.has_garage
  has_wifi / has_power_supply / has_borehole / is_gated
                  → Property.additional_features (JSON)
  source_url      → additional_features['source_url']   (dedup key)
  property_id     → additional_features['external_id']
  legal_title     → additional_features['legal_title']
  payment_plans   → additional_features['payment_plans']
  features        → PropertyAmenityLink rows
  images          → PropertyImage rows + Property.featured_image
  youtube_url     → Property.video_url
  source          → Developer.name  (bootstrapped once)

DEDUP KEY
────────────────────────────────────────────────────────────────────
  source_url is unique per property on the Dealclinchers site.
  We store it in Property.additional_features['source_url'].
  On subsequent runs the command looks this up first; if found it
  either skips or updates depending on --update-existing.

STATUS MAPPING
────────────────────────────────────────────────────────────────────
  for_sale   → PropertyStatus('for_sale')
  sold_out   → PropertyStatus('sold')
  off_plan   → PropertyStatus('pending')  + is_new=True

USAGE
────────────────────────────────────────────────────────────────────
  # DEV — fetch only 5 items to test locally:
  python manage.py import_dealclinchers --dataset-id <APIFY_DATASET_ID> --limit 5 --dry-run
  python manage.py import_dealclinchers --dataset-id <APIFY_DATASET_ID> --limit 5

  # FULL run (all ~26+ listings):
  python manage.py import_dealclinchers --dataset-id <APIFY_DATASET_ID>

  # From a locally saved JSON export:
  python manage.py import_dealclinchers --from-file dealclinchers_data.json

  # Skip image downloads (text data only — much faster for dev):
  python manage.py import_dealclinchers --dataset-id <ID> --skip-images

  # Overwrite price/description on already-imported properties:
  python manage.py import_dealclinchers --dataset-id <ID> --update-existing

SETUP
────────────────────────────────────────────────────────────────────
  pip install requests Pillow
  Set APIFY_API_TOKEN in your .env (or pass --apify-token on CLI).
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

DEALCLINCHERS_NAME    = 'Dealclinchers Homes Limited'
DEALCLINCHERS_WEBSITE = 'https://dealclinchersltd.com'
DEALCLINCHERS_HQ      = 'Lagos, Nigeria'

# ── Nigerian state name → (db_name, state_code) ──────────────────────────────
# Covers every state that appears in the scraper output.
# Add more rows here as new states are scraped.
STATE_REGISTRY = {
    'lagos':   ('Lagos',                      'LA'),
    'abuja':   ('Federal Capital Territory',  'FCT'),
    'fct':     ('Federal Capital Territory',  'FCT'),
    'ogun':    ('Ogun',                       'OG'),
    'oyo':     ('Oyo',                        'OY'),
    'rivers':  ('Rivers',                     'RV'),
    'delta':   ('Delta',                      'DE'),
    'anambra': ('Anambra',                    'AN'),
    'enugu':   ('Enugu',                      'EN'),
    'imo':     ('Imo',                        'IM'),
    'kano':    ('Kano',                       'KN'),
    'kaduna':  ('Kaduna',                     'KD'),
    'kwara':   ('Kwara',                      'KW'),
}

DEFAULT_STATE_NAME = 'Lagos'
DEFAULT_STATE_CODE = 'LA'
DEFAULT_CITY_NAME  = 'Lagos'

# ── Scraper property_type slug → PropertyType.TYPE_CHOICES key ───────────────
PROPERTY_TYPE_MAP = {
    'studio':           'studio',
    'semi_detached':    'semi_detached',
    'semi detached':    'semi_detached',
    'terrace':          'terrace',
    'townhouse':        'terrace',
    'fully_detached':   'detached_house',
    'detached_house':   'detached_house',
    'detached house':   'detached_house',
    'duplex':           'duplex',
    'bungalow':         'bungalow',
    'villa':            'villa',
    'mansion':          'mansion',
    'penthouse':        'penthouse',
    'maisonette':       'maisonette',
    'serviced_apt':     'serviced_apt',
    'mini_flat':        'mini_flat',
    'mini flat':        'mini_flat',
    'self_contain':     'self_contain',
    'apartment':        '2_bed_flat',
    '1_bed_flat':       '1_bed_flat',
    '2_bed_flat':       '2_bed_flat',
    '3_bed_flat':       '3_bed_flat',
    '4_bed_flat':       '4_bed_flat',
    'residential_land': 'residential_land',
    'commercial_land':  'commercial_land',
    'land':             'residential_land',
    'commercial':       'office',
    'office':           'office',
    'shop':             'shop',
    'warehouse':        'warehouse',
    'estate_house':     'estate_house',
}

TYPE_CATEGORY_MAP = {
    'detached_house': 'residential', 'semi_detached': 'residential',
    'terrace':        'residential', 'duplex':        'residential',
    'bungalow':       'residential', 'mansion':       'residential',
    'villa':          'residential', 'studio':        'residential',
    '1_bed_flat':     'residential', '2_bed_flat':    'residential',
    '3_bed_flat':     'residential', '4_bed_flat':    'residential',
    'penthouse':      'residential', 'maisonette':    'residential',
    'serviced_apt':   'residential', 'self_contain':  'residential',
    'room_parlour':   'residential', 'mini_flat':     'residential',
    'boys_quarters':  'residential', 'estate_house':  'residential',
    'cottage':        'residential',
    'residential_land': 'land', 'commercial_land': 'land',
    'agricultural_land': 'land', 'industrial_land': 'land',
    'mixed_use_land': 'land',
    'office':    'commercial', 'shop':     'commercial',
    'mall':      'commercial', 'showroom': 'commercial',
    'warehouse': 'commercial', 'factory':  'commercial',
    'hotel':     'commercial', 'event_center': 'commercial',
    'filling_station': 'commercial',
}

# ── Scraper status → PropertyStatus.STATUS_CHOICES key ───────────────────────
STATUS_MAP = {
    'for_sale': 'for_sale',
    'sold_out': 'sold',
    'off_plan': 'pending',   # closest valid choice; also sets is_new=True
}


# ─────────────────────────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = 'Import Dealclinchers Homes properties from an Apify dataset or JSON file'

    # ── CLI args ──────────────────────────────────────────────────────────────
    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--dataset-id',
            help='Apify Dataset ID from the actor run (e.g. abc123xyz)',
        )
        group.add_argument(
            '--from-file',
            metavar='PATH',
            help='Path to a local JSON file exported from Apify',
        )
        parser.add_argument(
            '--apify-token',
            default=os.environ.get('APIFY_API_TOKEN', ''),
            help='Apify API token (or set APIFY_API_TOKEN env var)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help=(
                'Max properties to import (default: 50). '
                'Use --limit 5 during dev to test without hammering the DB.'
            ),
        )
        parser.add_argument(
            '--skip-images',
            action='store_true',
            help='Skip downloading images — much faster for dev/test runs',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be imported without touching the DB',
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Overwrite price/description on already-imported properties',
        )

    # ── Entry point ───────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        self.skip_images     = options['skip_images']
        self.dry_run         = options['dry_run']
        self.update_existing = options['update_existing']

        if self.dry_run:
            self.stdout.write(self.style.WARNING('⚠  DRY RUN — nothing will be saved\n'))

        # ── 1. Fetch items ─────────────────────────────────────────────────────
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
                'No items found. Make sure the Apify actor run has finished '
                'and the dataset ID is correct.'
            )

        # ── 2. Bootstrap developer (once per run) ─────────────────────────────
        if not self.dry_run:
            self.developer = self._bootstrap_developer()
        else:
            self.developer = None

        # ── 3. Import each item ────────────────────────────────────────────────
        imported = updated = skipped = no_price = errors = 0

        for idx, item in enumerate(items, 1):
            title = (item.get('title') or '').strip()
            self.stdout.write(f'[{idx:>3}/{len(items)}] {title[:65]}')

            # Skip scraped 404 pages
            if not title or 'page not found' in title.lower():
                self.stdout.write(self.style.WARNING('       ↳ No valid title — skip'))
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
                            self.style.SUCCESS('       ↳ ✓ imported') +
                            '  ' + self.style.WARNING('⚠ price=NULL')
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
                f'  ⚠  {no_price} propert{"y" if no_price == 1 else "ies"} saved '
                f'with price=NULL — update manually or pass --update-existing later.'
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

    def _fetch_apify_dataset(self, dataset_id: str, token: str, limit: int) -> list:
        if not token:
            raise CommandError(
                'Apify API token required. Set APIFY_API_TOKEN in your .env '
                'or pass --apify-token on the CLI.'
            )
        url    = f'https://api.apify.com/v2/datasets/{dataset_id}/items'
        params = {'token': token, 'limit': limit, 'clean': 'true', 'format': 'json'}

        self.stdout.write(f'🌐  Fetching dataset {dataset_id} from Apify …')
        try:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise CommandError(f'Apify API request failed: {exc}')

    # ─────────────────────────────────────────────────────────────────────────
    # BOOTSTRAP HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _bootstrap_developer(self) -> Developer:
        dev, created = Developer.objects.get_or_create(
            name=DEALCLINCHERS_NAME,
            defaults={
                'tagline':      'Premium Real Estate Solutions Across Nigeria',
                'website':      DEALCLINCHERS_WEBSITE,
                'headquarters': DEALCLINCHERS_HQ,
                'is_active':    True,
                'is_featured':  True,
            },
        )
        if created:
            self.stdout.write(f'  🏢  Created developer: {dev.name}')
        return dev

    def _get_or_create_state(self, raw_state: str) -> State:
        """
        Resolve a scraped state string ('Lagos', 'Abuja', 'Ogun' …) to a
        State row, creating it if it doesn't exist yet.
        Falls back to Lagos when the value is unrecognised.
        """
        key         = (raw_state or '').strip().lower()
        name, code  = STATE_REGISTRY.get(key, (DEFAULT_STATE_NAME, DEFAULT_STATE_CODE))
        state, created = State.objects.get_or_create(
            name=name,
            defaults={'code': code, 'is_active': True},
        )
        if created:
            self.stdout.write(f'  🗺   Created state: {state.name}')
        return state

    def _get_or_create_city(self, raw_city: str, state: State) -> City:
        name = (raw_city or DEFAULT_CITY_NAME).strip().title()[:100]
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
            defaults={
                'category':      category,
                'is_active':     True,
                'display_order': 0,
            },
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
        Convert '₦4,300,000', '4300000', '0', or None → Decimal or None.
        Returns None when the value is missing, zero, or unparseable so
        the listing is shown as "Price on Request" rather than ₦0.
        """
        if not raw:
            return None
        cleaned = re.sub(r'[^\d.]', '', str(raw).strip())
        if not cleaned:
            return None
        try:
            value = Decimal(cleaned)
            return value if value > 0 else None
        except InvalidOperation:
            return None

    @staticmethod
    def _parse_area_sqm(raw) -> Optional[int]:
        """
        Parse '500 SQM', '250 sqm', '1200' → int square metres, or None.
        The model stores square_feet; we keep the unit as-is because
        Nigerian listings quote area in SQM — just store the number.
        """
        if not raw:
            return None
        cleaned = re.sub(r'[^\d.]', '', str(raw).strip())
        try:
            v = int(float(cleaned))
            return v if v > 0 else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _map_type(scraped_type: str, title: str = '') -> str:
        """Return a TYPE_CHOICES key from the scraped property_type slug."""
        key = (scraped_type or '').strip().lower().replace('-', '_').replace(' ', '_')
        if key in PROPERTY_TYPE_MAP:
            return PROPERTY_TYPE_MAP[key]
        # Fallback: scan title for keywords
        combined = f'{scraped_type} {title}'.lower()
        for keyword, code in PROPERTY_TYPE_MAP.items():
            if keyword in combined:
                return code
        return 'estate_house'

    @staticmethod
    def _map_status(item: dict) -> tuple[str, bool]:
        """
        Returns (status_code, is_new).
        is_sold_out  → 'sold',    is_new=False
        is_off_plan  → 'pending', is_new=True
        default      → 'for_sale', is_new=False
        """
        if item.get('is_sold_out'):
            return 'sold', False
        if item.get('is_off_plan'):
            return 'pending', True
        # Also read the scraped status field as a cross-check
        scraped = (item.get('status') or 'for_sale').lower()
        code = STATUS_MAP.get(scraped, 'for_sale')
        return code, False

    @staticmethod
    def _clean_youtube_url(raw: str) -> str:
        """
        Return a clean YouTube URL that EmbedVideoField will accept,
        or an empty string if the URL looks invalid.
        """
        if not raw:
            return ''
        # Reject placeholder / channel / invalid values
        if any(x in raw for x in ['about:blank', '@', 'embed']):
            return ''
        raw = raw.split(';')[0].strip()   # handle "about:blank;www.youtube.com"
        if 'youtube.com/watch' in raw or 'youtu.be' in raw:
            return raw
        return ''

    # ─────────────────────────────────────────────────────────────────────────
    # CORE IMPORT
    # ─────────────────────────────────────────────────────────────────────────

    def _import_one(self, item: dict) -> str:
        """
        Process one scraped item dict.
        Returns 'imported' | 'updated' | 'exists' | 'dry_run'.
        Side-effect: sets item['_had_price'] so the caller can count no-price rows.
        """
        title       = (item.get('title') or '').strip()
        description = (item.get('description') or '').strip()
        source_url  = (item.get('source_url') or '').strip()

        # ── Price ──────────────────────────────────────────────────────────────
        # Prefer price_min if available; fall back to price.
        raw_price: str            = item.get('price_min') or item.get('price') or ''
        price: Optional[Decimal]  = self._parse_price(raw_price)
        is_call_for_price: bool   = bool(item.get('is_call_for_price'))
        item['_had_price']        = (price is not None) or is_call_for_price

        # ── Specs ──────────────────────────────────────────────────────────────
        bedrooms    = int(item.get('bedrooms')  or 0)
        bathrooms   = int(item.get('bathrooms') or 0)
        garages     = int(item.get('garages')   or 0)
        area        = self._parse_area_sqm(item.get('area_size'))
        year_built  = item.get('year_built') or None

        # ── Location ───────────────────────────────────────────────────────────
        raw_state   = (item.get('state') or '').strip()
        raw_city    = (item.get('city')  or '').strip()
        address     = (item.get('address') or raw_city or DEFAULT_CITY_NAME).strip()

        # ── Type & status ──────────────────────────────────────────────────────
        type_code             = self._map_type(item.get('property_type', ''), title)
        status_code, is_new   = self._map_status(item)

        # ── Badges ─────────────────────────────────────────────────────────────
        is_featured  = bool(item.get('is_featured'))
        is_hot       = bool(item.get('is_hot_offer'))
        # off-plan items are "new" by definition
        if item.get('is_off_plan'):
            is_new = True

        # ── Video ──────────────────────────────────────────────────────────────
        video_url = self._clean_youtube_url(item.get('youtube_url') or '')

        # ── Extra JSON data ────────────────────────────────────────────────────
        extra = {
            'source_url':     source_url,
            'external_id':    item.get('property_id') or '',
            'legal_title':    item.get('legal_title') or '',
            'payment_plans':  item.get('payment_plans') or [],
            'price_text':     item.get('price_text') or '',
            'price_max':      str(item.get('price_max') or ''),
            'has_borehole':   bool(item.get('has_borehole')),
            'has_power_supply': bool(item.get('has_power_supply')),
            'has_wifi':       bool(item.get('has_wifi')),
            'is_gated':       bool(item.get('is_gated')),
            'google_maps_url': item.get('google_maps_url') or '',
        }

        # ── DRY RUN ────────────────────────────────────────────────────────────
        if self.dry_run:
            price_display = f'₦{float(price):,.0f}' if price else (
                'Call for Price' if is_call_for_price else 'Price TBD'
            )
            self.stdout.write(
                f'       ↳ [{status_code}] {type_code} | '
                f'{price_display} | {bedrooms}bd/{bathrooms}ba | '
                f'{raw_city}, {raw_state}'
            )
            return 'dry_run'

        # ── Dedup: match on source_url stored in additional_features ───────────
        existing = None
        if source_url:
            existing = Property.objects.filter(
                additional_features__source_url=source_url
            ).first()

        # Fallback dedup: title + developer (catches pre-import_dealclinchers rows)
        if not existing:
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

                if description:
                    existing.description = description
                    update_fields.append('description')

                if address:
                    existing.address = address
                    update_fields.append('address')

                if price is not None:
                    existing.price = price
                    update_fields.append('price')

                # Merge extra JSON without clobbering existing keys
                current_extra = existing.additional_features or {}
                current_extra.update(extra)
                existing.additional_features = current_extra
                update_fields.append('additional_features')

                existing.save(update_fields=update_fields)
                prop   = existing
                action = 'updated'

            else:
                # ── INSERT path ───────────────────────────────────────────────
                prop = Property(
                    title=title,
                    description=description,
                    state=state,
                    city=city,
                    address=address[:499],
                    property_type=prop_type,
                    status=prop_status,
                    bedrooms=bedrooms,
                    bathrooms=bathrooms,
                    square_feet=area,
                    price=price,
                    is_call_for_price=is_call_for_price,
                    parking_spaces=garages,
                    year_built=year_built,
                    developer=self.developer,
                    # Badges
                    is_featured=is_featured,
                    is_hot=is_hot,
                    is_new=is_new,
                    # Boolean amenities (direct from scraper — no guessing)
                    has_ac=bool(item.get('has_ac')),
                    has_gym=bool(item.get('has_gym')),
                    has_pool=bool(item.get('has_pool')),
                    has_security=bool(item.get('has_security')),
                    has_garage=bool(item.get('has_parking')) or garages > 0,
                    # Video
                    video_url=video_url,
                    # Extra JSON
                    additional_features=extra,
                    is_active=True,
                )
                prop.save()
                action = 'imported'

            # ── Images ────────────────────────────────────────────────────────
            if not self.skip_images and action == 'imported':
                self._save_images(prop, item.get('images') or [], title)

            # ── Amenities (from features list) ─────────────────────────────────
            if action == 'imported':
                self._save_amenities(prop, item.get('features') or [])

        return action

    # ─────────────────────────────────────────────────────────────────────────
    # IMAGE SAVING
    # ─────────────────────────────────────────────────────────────────────────

    def _download_image(self, url: str, filename: str) -> Optional[ContentFile]:
        """Download an image URL and return a ContentFile, or None on failure."""
        # Skip placeholder / proxied-content markers
        if not url or 'proxied' in url.lower():
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
                    'Referer': DEALCLINCHERS_WEBSITE,
                },
                stream=True,
            )
            resp.raise_for_status()

            content_type = resp.headers.get('content-type', 'image/jpeg')
            ext_map = {
                'image/jpeg': 'jpg', 'image/jpg': 'jpg',
                'image/png':  'png', 'image/webp': 'webp',
                'image/gif':  'gif',
            }
            ext   = ext_map.get(content_type.split(';')[0].strip(), 'jpg')
            fname = f'{filename}.{ext}'

            buf  = BytesIO()
            size = 0
            for chunk in resp.iter_content(chunk_size=8192):
                buf.write(chunk)
                size += len(chunk)
                if size > 8 * 1024 * 1024:   # 8 MB cap
                    break
            return ContentFile(buf.getvalue(), name=fname)

        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(f'       ↳ ⚠ Image skip ({url[:55]}…): {exc}')
            )
            return None

    def _save_images(self, prop: Property, image_urls: list, title: str):
        base = slugify(title)[:35]
        for idx, url in enumerate(image_urls[:10]):   # up to 10 images
            if not url:
                continue
            fname = f'dealclinchers_{base}_{idx}'
            file  = self._download_image(url, fname)
            if not file:
                continue

            if idx == 0 and not prop.featured_image:
                prop.featured_image.save(file.name, file, save=True)
            else:
                pi = PropertyImage(
                    property=prop,
                    caption=f'{title} — photo {idx + 1}',
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