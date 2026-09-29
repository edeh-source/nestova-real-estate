"""
management/commands/import_landgate.py
=======================================
Import Landgate Investments Limited projects from an Apify dataset
or a locally saved JSON export into the Nestova Property model.

DATASET STRUCTURE (from live scraper)
────────────────────────────────────────────────────────────────
  19 known projects as of Sep 2026 across Lagos and Ogun State.
  All are land / estate developments — no individual house units.
  project_id  = URL slug  (e.g. "murewa-gardens-prestige")
  source_url  = full project page URL

PRICE FIELDS — READ THIS
────────────────────────────────────────────────────────────────
  The scraper outputs five price-related fields:

    price           → price_from (the minimum listed plot price)  ← USE THIS
    price_from      → same value (duplicate kept for transparency)
    price_min       → derived from payment_plan table totals
    price_max       → highest plan total across all plot sizes
    initial_deposit → the deposit needed to start a payment plan

  ALWAYS map `price` (not price_min) → Property.price.
  price_min and price_max come from the nested payment tables and
  represent individual plan tiers, not standalone property prices.

PAYMENT PLANS STRUCTURE — DIFFERENT FROM DEALCLINCHERS
────────────────────────────────────────────────────────────────
  payment_plans is a list of per-plot-size objects:

    [
      {
        "plot_size": "300 SQM",
        "plans": [
          {"plan": "Outright",  "initial_deposit": 8000000, "balance": 0,
           "instalment": 0, "total": 8000000},
          {"plan": "3 Months",  "initial_deposit": 2000000, "balance": 6000000,
           "instalment": 2000000, "total": 8000000},
          ...
        ]
      },
      { "plot_size": "500 SQM", "plans": [...] },
    ]

  The whole structure is stored in additional_features.payment_plans
  so Nestova can render per-size pricing tables on the detail page.

STATUS MAPPING
────────────────────────────────────────────────────────────────
  Scraper status     → PropertyStatus     Notes
  for_sale           → for_sale
  sold_out           → sold               is_sold_out == True
  coming_soon        → pending            is_coming_soon == True + is_new=True
  (selling_fast      stays for_sale;      is_hot=True)

PROPERTY TYPE RESOLUTION
────────────────────────────────────────────────────────────────
  1. Direct map on property_type slug
  2. Keyword scan across title + plot_sizes string
  3. Fallback → residential_land  (Landgate is primarily a land developer)

AREA / PLOT SIZE
────────────────────────────────────────────────────────────────
  plot_sizes is a string: "300, 500, 1000 Sqm"
  We store the minimum size as Property.square_feet so the listing
  card shows a useful number.  The full string goes in extra.

DEDUP KEY
────────────────────────────────────────────────────────────────
  source_url is unique per project; stored in additional_features.
  On re-runs, existing projects are skipped (or updated with
  --update-existing).

IMAGES
────────────────────────────────────────────────────────────────
  featured_image == images[0] in every item.
  images[0]  → Property.featured_image
  images[1:] → PropertyImage gallery rows (capped at 12 extra)

USAGE
────────────────────────────────────────────────────────────────
  # DEV — 3 items, no images, dry run first:
  python manage.py import_landgate --dataset-id <ID> --limit 3 --dry-run
  python manage.py import_landgate --dataset-id <ID> --limit 3 --skip-images

  # FULL run:
  python manage.py import_landgate --dataset-id <ID>

  # From local file (preferred for testing before deployment):
  python manage.py import_landgate --from-file landgate_dataset.json --dry-run
  python manage.py import_landgate --from-file landgate_dataset.json --limit 5 --skip-images
  python manage.py import_landgate --from-file landgate_dataset.json

  # Re-import and overwrite price / description on existing rows:
  python manage.py import_landgate --dataset-id <ID> --update-existing

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

DEVELOPER_NAME    = 'Landgate Investments Limited'
DEVELOPER_WEBSITE = 'https://landgateltd.com.ng'
DEVELOPER_HQ      = 'Lekki Phase 1, Lagos, Nigeria'

# Scraped state name (lowercase) → (canonical DB name, state code)
# Landgate only operates in Lagos and Ogun; keep the full registry
# for any future expansion.
STATE_REGISTRY = {
    'lagos':   ('Lagos',                     'LA'),
    'ogun':    ('Ogun',                      'OG'),
    'abuja':   ('Federal Capital Territory', 'FCT'),
    'fct':     ('Federal Capital Territory', 'FCT'),
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
# Landgate is almost entirely land; residential types cover
# the "Affordable Homes" sub-category projects.
PROPERTY_TYPE_MAP = {
    'land':             'residential_land',
    'residential_land': 'residential_land',
    'commercial_land':  'commercial_land',
    'bungalow':         'bungalow',
    'terrace':          'terrace',
    'duplex':           'duplex',
    'apartment':        '2_bed_flat',
    'hostel':           'estate_house',   # student hostel → estate_house bucket
    'villa':            'villa',
    'studio':           'studio',
    'semi_detached':    'semi_detached',
    'commercial':       'office',
    'residential':      'estate_house',
    'estate_house':     'estate_house',
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
    'residential_land': 'land',        'commercial_land': 'land',
    'agricultural_land':'land',        'industrial_land': 'land',
    'mixed_use_land':   'land',
    'office':           'commercial',  'shop':           'commercial',
    'mall':             'commercial',  'showroom':       'commercial',
    'warehouse':        'commercial',  'factory':        'commercial',
    'hotel':            'commercial',  'event_center':   'commercial',
    'filling_station':  'commercial',
}

# Scraper status string → PropertyStatus.STATUS_CHOICES key
STATUS_MAP = {
    'for_sale':    'for_sale',
    'sold_out':    'sold',
    'coming_soon': 'pending',
}


# ─────────────────────────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = 'Import Landgate Investments projects from Apify or a local JSON file'

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
            help='Apify API token (or set APIFY_API_TOKEN in your .env)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Max items to process (default: 50). Use --limit 3 during dev.',
        )
        parser.add_argument(
            '--skip-images',
            action='store_true',
            help='Skip all image downloads — much faster for dev / test runs',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be imported without touching the database',
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Overwrite price and description on already-imported projects',
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

            # Skip empty or clearly broken items (no title / page_type mismatch)
            if not title or item.get('page_type') not in ('project', None):
                self.stdout.write(self.style.WARNING('       ↳ empty / wrong page_type — skip'))
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
                f'  ⚠  {no_price} project{"" if no_price == 1 else "s"} '
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
                'tagline':      'Affordable Land & Real Estate Investment in Lagos and Ogun',
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
        code     = code or 'residential_land'
        category = TYPE_CATEGORY_MAP.get(code, 'land')
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
        Convert the scraped `price` integer (e.g. 8000000) or string
        (e.g. '₦8,000,000') → Decimal.

        Returns None when the value is absent, zero, or unparseable so
        the listing shows as 'Price on Request' rather than ₦0.

        NOTE: always call this with item['price'], NOT item['price_min'].
        price_min is derived from payment table totals, not the listed price.
        """
        if raw is None:
            return None
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
    def _parse_min_plot_size(raw: str) -> Optional[int]:
        """
        Extract the minimum (smallest) plot size from the plot_sizes string.

        Examples:
          "300, 500, 1000 Sqm"  →  300
          "500 SQM"             →  500
          "300-500 Sqm"         →  300

        Returns None when no valid size is found.
        Filters out obviously wrong values (> 50,000 Sqm).
        """
        if not raw:
            return None
        numbers = [int(n) for n in re.findall(r'\d+', str(raw)) if 0 < int(n) < 50_000]
        return min(numbers) if numbers else None

    @staticmethod
    def _map_type(scraped_type: str, title: str = '', plot_sizes: str = '') -> str:
        """
        Resolve a PropertyType.TYPE_CHOICES key from:
          1. Direct match on scraped property_type slug
          2. Keyword scan across title + plot_sizes
          3. Fallback → residential_land  (Landgate default)
        """
        slug = (scraped_type or '').strip().lower()

        # Step 1 — direct slug match
        if slug in PROPERTY_TYPE_MAP:
            return PROPERTY_TYPE_MAP[slug]

        # Step 2 — keyword scan on combined text
        combined = f'{scraped_type} {title} {plot_sizes}'.lower()
        for keyword, code in PROPERTY_TYPE_MAP.items():
            if keyword in combined:
                return code

        # Step 3 — Landgate default: residential land
        return 'residential_land'

    @staticmethod
    def _resolve_status(item: dict) -> tuple:
        """
        Return (status_code: str, is_new: bool).

        Priority order:
          is_sold_out flag    → 'sold'       + is_new=False
          is_coming_soon flag → 'pending'    + is_new=True
          status field        → mapped via STATUS_MAP
          fallback            → 'for_sale'   + is_new=False
        """
        if item.get('is_sold_out'):
            return 'sold', False
        if item.get('is_coming_soon'):
            return 'pending', True
        code = STATUS_MAP.get((item.get('status') or 'for_sale').lower(), 'for_sale')
        return code, False

    @staticmethod
    def _clean_video_url(raw: str) -> str:
        """
        Return a YouTube watch/embed URL that EmbedVideoField accepts.
        Rejects channel URLs, empty strings, and junk.
        Only /watch?v= and /embed/ paths are valid.
        """
        if not raw:
            return ''
        url = raw.split(';')[0].strip()
        invalid_markers = ['about:blank', '@landgate', '@', '/channel/']
        if any(m in url for m in invalid_markers):
            return ''
        if 'youtube.com/watch' in url or 'youtu.be/' in url:
            return url
        if 'youtube.com/embed/' in url:
            video_id = url.split('/embed/')[-1].split('?')[0]
            return f'https://www.youtube.com/watch?v={video_id}'
        return ''

    # ─────────────────────────────────────────────────────────────────────────
    # CORE IMPORT
    # ─────────────────────────────────────────────────────────────────────────

    def _import_one(self, item: dict) -> str:
        """
        Import or update one scraped project dict.
        Returns: 'imported' | 'updated' | 'exists' | 'dry_run'
        Side-effect: sets item['_had_price'] for the caller's no_price counter.
        """
        title      = (item.get('title') or '').strip()
        desc       = (item.get('description') or '').strip()
        source_url = (item.get('source_url') or '').strip()

        # Address: prefer location_label ("Ketu, Epe, Lagos") then city
        address = (
            item.get('location_label') or
            item.get('city') or
            ''
        ).strip()

        # ── Price — use `price` (= price_from), never `price_min` ──────────────
        price: Optional[Decimal] = self._parse_price(item.get('price'))
        is_cfp: bool             = bool(item.get('is_call_for_price'))
        item['_had_price']       = (price is not None) or is_cfp

        # ── Plot size → square_feet ────────────────────────────────────────────
        # We store the minimum plot size as square_feet (e.g. 300 from "300, 500, 1000 Sqm")
        area = self._parse_min_plot_size(item.get('plot_sizes') or '')

        # ── Location ───────────────────────────────────────────────────────────
        raw_state = (item.get('state') or '').strip()
        raw_city  = (item.get('city')  or '').strip()

        # ── Type & status ──────────────────────────────────────────────────────
        type_code           = self._map_type(
            item.get('property_type', ''),
            title,
            item.get('plot_sizes', ''),
        )
        status_code, is_new = self._resolve_status(item)

        # ── Badges ─────────────────────────────────────────────────────────────
        # Landgate doesn't use "featured" badges on its site.
        # Map is_selling_fast → is_hot (same "hot deal" intent).
        is_featured = False
        is_hot      = bool(item.get('is_selling_fast'))

        # ── Video ──────────────────────────────────────────────────────────────
        video_url = self._clean_video_url(item.get('youtube_url') or '')

        # ── JSON extras ────────────────────────────────────────────────────────
        # Store everything Nestova's detail page might need but that has
        # no dedicated model column, including the full payment plan tables.
        extra = {
            # Identity / dedup
            'source_url':            source_url,
            'external_id':           item.get('project_id') or '',
            # Legal / land details
            'legal_title':           item.get('legal_title') or '',
            'plot_sizes':            item.get('plot_sizes') or '',
            'location_label':        item.get('location_label') or '',
            # Pricing detail
            'price_from':            item.get('price_from'),
            'price_max':             item.get('price_max'),
            'initial_deposit':       item.get('initial_deposit'),
            # Full per-plot-size payment plan tables
            'payment_plans':         item.get('payment_plans') or [],
            # Neighbourhood proximity notes from the page
            'neighbourhood':         item.get('neighbourhood') or [],
            # Status detail
            'status_badge':          item.get('status_badge') or '',
            # Extended amenities not in model boolean columns
            'has_borehole':          bool(item.get('has_borehole')),
            'has_power_supply':      bool(item.get('has_power_supply')),
            'has_perimeter_fencing': bool(item.get('has_perimeter_fencing')),
            'has_supermarket':       bool(item.get('has_supermarket')),
            'has_drainage':          bool(item.get('has_drainage')),
            'has_cleaning_service':  bool(item.get('has_cleaning_service')),
            'has_playground':        bool(item.get('has_playground')),
            'is_gated':              bool(item.get('is_gated')),
            'google_maps_url':       item.get('google_maps_url') or '',
        }

        # ── DRY RUN ────────────────────────────────────────────────────────────
        if self.dry_run:
            price_display = (
                'Call for Price' if is_cfp
                else f'₦{float(price):,.0f}' if price is not None
                else 'Price TBD'
            )
            plans_count = sum(
                len(g.get('plans', []))
                for g in (item.get('payment_plans') or [])
            )
            self.stdout.write(
                f'       ↳ [{status_code}] {type_code} | '
                f'{price_display} | {area or "?"}sqm | '
                f'{raw_city or "?"}, {raw_state or "?"} | '
                f'{plans_count} plan(s) across '
                f'{len(item.get("payment_plans") or [])} plot size(s)'
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
                    # Landgate sells land / estates — no bedrooms or bathrooms
                    bedrooms=0,
                    bathrooms=0,
                    # Minimum plot size in sqm (e.g. 300 from "300, 500, 1000 Sqm")
                    square_feet=area,
                    price=price,
                    is_call_for_price=is_cfp,
                    parking_spaces=0,
                    year_built=None,
                    developer=self.developer,
                    # Badges
                    is_featured=is_featured,
                    is_hot=is_hot,
                    is_new=is_new,
                    # Boolean amenities — direct from scraper, no guessing
                    has_ac=False,                          # N/A for land
                    has_gym=bool(item.get('has_gym')),
                    has_pool=bool(item.get('has_pool')),
                    has_security=bool(item.get('has_security')),
                    has_garage=bool(item.get('has_parking')),
                    # Video
                    video_url=video_url,
                    # JSON extras (payment plans, neighbourhood, etc.)
                    additional_features=extra,
                    is_active=True,
                )
                prop.save()
                action = 'imported'

            # ── Images ────────────────────────────────────────────────────────
            if not self.skip_images and action == 'imported':
                self._save_images(prop, item.get('images') or [], title)

            # ── Amenities ─────────────────────────────────────────────────────
            if action == 'imported':
                self._save_amenities(prop, item.get('features') or [])

        return action

    # ─────────────────────────────────────────────────────────────────────────
    # IMAGE SAVING
    # ─────────────────────────────────────────────────────────────────────────

    def _download_image(self, url: str, filename: str) -> Optional[ContentFile]:
        """Download url → ContentFile, or None on any failure."""
        if not url:
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
                'image/gif':  'gif', 'image/avif': 'avif',
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
        images[0]  → Property.featured_image
        images[1:] → PropertyImage gallery rows, capped at 12 extras
        """
        base = slugify(title)[:35]

        for idx, url in enumerate(image_urls[:13]):   # idx 0 = featured; 1-12 = gallery
            if not url:
                continue

            fname = f'landgate_{base}_{idx}'
            file  = self._download_image(url, fname)
            if not file:
                continue

            if idx == 0:
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