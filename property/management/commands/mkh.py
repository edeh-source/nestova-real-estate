"""
Django management command — import MKH Properties scraped data
into Nestova's Property model.

Usage:
    python manage.py import_mkh_properties --file mkh_dataset.json

The JSON file is the Apify dataset export (JSON Lines or array).
Download from:  Apify Console → your run → Export → JSON

Place this file at:
    <your_app>/management/commands/import_mkh_properties.py
"""
rediss://default:gQAAAAAAAtQ4AAIgcDE3ZmY3YjczYjFjNzY0NTk2YmIyODg5ODQ4NTFhMjNkYQ@desired-gnat-185400.upstash.io:6379?ssl_cert_reqs=none
redis-cli --tls -u redis://default:AZyeAAIncDEzMDI4Zjk3OWNkMjg0YTM0YjFkZDVkMGIxZWEzOTI1M3AxNDAwOTQ@new-pegasus-40094.upstash.io:6379
import json
import re
import sys
import requests
from pathlib import Path
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.db import transaction

from property.models import (   # adjust app label as needed
    Property, PropertyImage, PropertyType, PropertyStatus,
    PropertyAmenity, PropertyAmenityLink,
    State, City, Developer,
)


# ──────────────────────────────────────────────────────────────────
#  MAPPING: scraper string  →  PropertyType.TYPE_CHOICES key
#  (already aligned; kept here as a safety net)
# ──────────────────────────────────────────────────────────────────
VALID_TYPES = {c[0] for c in PropertyType.TYPE_CHOICES}

# ──────────────────────────────────────────────────────────────────
#  MAPPING: scraper string  →  PropertyStatus.STATUS_CHOICES key
# ──────────────────────────────────────────────────────────────────
VALID_STATUSES = {c[0] for c in PropertyStatus.STATUS_CHOICES}


def download_image(url: str, timeout: int = 15):
    """Return (filename, ContentFile) or (None, None) on failure."""
    try:
        r = requests.get(url, timeout=timeout, stream=True)
        r.raise_for_status()
        content_type = r.headers.get('Content-Type', 'image/jpeg')
        ext = {
            'image/jpeg': '.jpg',
            'image/png':  '.png',
            'image/webp': '.webp',
            'image/gif':  '.gif',
        }.get(content_type.split(';')[0].strip(), '.jpg')
        parsed = urlparse(url)
        basename = Path(parsed.path).stem[:80] or 'property_image'
        filename = f"{basename}{ext}"
        return filename, ContentFile(r.content)
    except Exception as e:
        print(f"    [WARN] Could not download {url}: {e}")
        return None, None


class Command(BaseCommand):
    help = "Import scraped MKH Properties data into Nestova Property model"

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', '-f',
            required=True,
            help='Path to Apify JSON export (array or JSON-Lines)',
        )
        parser.add_argument(
            '--skip-images',
            action='store_true',
            default=False,
            help='Skip downloading and saving property images',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Validate & preview without writing to the database',
        )

    def handle(self, *args, **options):
        filepath   = options['file']
        skip_imgs  = options['skip_images']
        dry_run    = options['dry_run']

        # ── Load JSON ────────────────────────────────────────────
        raw = Path(filepath).read_text(encoding='utf-8').strip()
        if raw.startswith('['):
            records = json.loads(raw)
        else:
            # JSON-Lines format (one object per line)
            records = [json.loads(line) for line in raw.splitlines() if line.strip()]

        self.stdout.write(f"Loaded {len(records)} records from {filepath}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN mode — no DB writes"))

        # ── Get / create Developer ───────────────────────────────
        developer, _ = Developer.objects.get_or_create(
            slug='mkh-properties',
            defaults={
                'name':        'MKH Properties',
                'headquarters': 'Nigeria',
                'is_active':   True,
            }
        )

        created_count = 0
        skipped_count = 0
        error_count   = 0

        for idx, rec in enumerate(records, 1):
            title = (rec.get('title') or '').strip()
            url   = rec.get('url', '')

            if not title:
                self.stdout.write(f"  [{idx}] SKIP — no title ({url})")
                skipped_count += 1
                continue

            self.stdout.write(f"\n  [{idx}/{len(records)}] {title}")

            # ── Resolve State ────────────────────────────────────
            state_name = (rec.get('state_name') or '').strip()
            if not state_name:
                self.stdout.write(f"         SKIP — no state resolved")
                skipped_count += 1
                continue

            try:
                state_obj = State.objects.get(name__iexact=state_name)
            except State.DoesNotExist:
                # Create on the fly with a placeholder code
                code = re.sub(r'[^A-Z]', '', state_name.upper())[:5] or 'UNK'
                state_obj, _ = State.objects.get_or_create(
                    name=state_name,
                    defaults={'code': code, 'is_active': True},
                )

            # ── Resolve City ─────────────────────────────────────
            city_name = (rec.get('city_name') or state_name).strip()
            city_obj, _ = City.objects.get_or_create(
                name=city_name,
                state=state_obj,
                defaults={'is_active': True},
            )

            # ── Resolve PropertyType ──────────────────────────────
            raw_type = rec.get('property_type', 'estate_house')
            ptype_key = raw_type if raw_type in VALID_TYPES else 'estate_house'
            ptype_obj, _ = PropertyType.objects.get_or_create(
                name=ptype_key,
                defaults={'category': 'residential', 'is_active': True},
            )

            # ── Resolve PropertyStatus ────────────────────────────
            raw_status = rec.get('status', 'for_sale')
            pstatus_key = raw_status if raw_status in VALID_STATUSES else 'for_sale'
            pstatus_obj, _ = PropertyStatus.objects.get_or_create(
                name=pstatus_key,
            )

            # ── Price ─────────────────────────────────────────────
            price_str = (rec.get('price') or '').replace(',', '').strip()
            try:
                price = Decimal(price_str) if price_str else None
            except InvalidOperation:
                price = None

            # ── Square feet fallback ───────────────────────────────
            sq_ft = int(rec.get('square_feet') or 0) or None

            # ── Build Property dict ───────────────────────────────
            prop_defaults = dict(
                description    = rec.get('description', ''),
                address        = rec.get('address', ''),
                state          = state_obj,
                city           = city_obj,
                property_type  = ptype_obj,
                status         = pstatus_obj,
                price          = price,
                bedrooms       = int(rec.get('bedrooms')  or 0),
                bathrooms      = int(rec.get('bathrooms') or 0),
                square_feet    = sq_ft or 0,
                parking_spaces = int(rec.get('parking_spaces') or 0),
                year_built     = rec.get('year_built'),
                # Boolean features
                has_pool       = bool(rec.get('has_pool')),
                has_gym        = bool(rec.get('has_gym')),
                has_security   = bool(rec.get('has_security')),
                has_balcony    = bool(rec.get('has_balcony')),
                has_garden     = bool(rec.get('has_garden')),
                has_garage     = bool(rec.get('has_garage')),
                has_ac         = bool(rec.get('has_ac')),
                is_furnished   = bool(rec.get('is_furnished')),
                # Badges
                is_active      = True,
                is_featured    = bool(rec.get('is_featured', False)),
                is_new         = bool(rec.get('is_new', True)),
                developer      = developer,
                # Store source URL in additional_features for traceability
                additional_features = {'source_url': url, 'raw_price': rec.get('rawPrice', '')},
            )

            if dry_run:
                self.stdout.write(
                    f"         [DRY] Would create: {title} | ₦{price} | {city_name}, {state_name} | "
                    f"beds={prop_defaults['bedrooms']} baths={prop_defaults['bathrooms']} | "
                    f"imgs={len(rec.get('images', []))}"
                )
                created_count += 1
                continue

            # ── Write to DB ───────────────────────────────────────
            try:
                with transaction.atomic():
                    prop, created = Property.objects.get_or_create(
                        title=title,
                        state=state_obj,
                        defaults=prop_defaults,
                    )

                    if not created:
                        # Update existing record in case price / details changed
                        for k, v in prop_defaults.items():
                            setattr(prop, k, v)
                        prop.save()
                        self.stdout.write(f"         Updated existing record (id={prop.pk})")
                    else:
                        self.stdout.write(f"         Created (id={prop.pk})")

                    # ── Images ────────────────────────────────────
                    if not skip_imgs:
                        images = rec.get('images', [])
                        # Clear old images so we start fresh
                        prop.images.all().delete()

                        for img_data in images:
                            img_url    = img_data.get('url', '')
                            is_primary = img_data.get('is_primary', False)
                            order      = img_data.get('order', 0)

                            if not img_url:
                                continue

                            filename, content = download_image(img_url)
                            if not filename:
                                continue

                            prop_img = PropertyImage(
                                property   = prop,
                                is_primary = is_primary,
                                order      = order,
                                caption    = title if is_primary else '',
                            )
                            prop_img.image.save(filename, content, save=True)

                            if is_primary:
                                # Also set as the Property.featured_image
                                prop.featured_image.save(filename, content, save=False)

                        prop.save(update_fields=['featured_image'])
                        self.stdout.write(f"         Saved {len(images)} images")

                    # ── Amenities ─────────────────────────────────
                    amenities = rec.get('amenities', [])
                    for amenity_name in amenities:
                        amenity_name = amenity_name.strip()
                        if not amenity_name:
                            continue
                        amenity_obj, _ = PropertyAmenity.objects.get_or_create(
                            name=amenity_name,
                            defaults={'icon': 'bi bi-check-circle'},
                        )
                        PropertyAmenityLink.objects.get_or_create(
                            property=prop,
                            amenity=amenity_obj,
                            defaults={'is_available': True},
                        )

                    created_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"         ERROR: {e}"))
                error_count += 1
                continue

        # ── Summary ───────────────────────────────────────────────
        self.stdout.write('\n' + '─' * 60)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created/updated: {created_count} | "
                f"Skipped: {skipped_count} | Errors: {error_count}"
            )
        )