"""
management/commands/import_victoriacrest.py
============================================
Import Victoria Crest Homes properties from an Apify dataset or a local
JSON/JSONL/CSV export into the Nestova Property model.

Designed around the current Victoria Crest Apify fields, including:

    source_url
    source_property_id
    title
    description
    description_text
    address
    country
    state
    city
    neighborhood
    google_maps_url
    property_type
    source_property_type
    status
    source_status
    bedrooms
    bathrooms
    rooms
    year_built
    parking_spaces
    square_feet
    lot_size
    price
    source_price_text
    is_call_for_price
    features
    images
    featured_image
    additional_features

USAGE
-----

1. Dry-run a local Apify JSON export:

    python manage.py import_victoriacrest \
        --from-file victoriacrest_data.json \
        --dry-run

2. Import locally from JSON:

    python manage.py import_victoriacrest \
        --from-file victoriacrest_data.json

3. Import directly from Apify:

    python manage.py import_victoriacrest \
        --dataset-id YOUR_DATASET_ID \
        --apify-token YOUR_TOKEN

4. Import without downloading pictures:

    python manage.py import_victoriacrest \
        --from-file victoriacrest_data.json \
        --skip-images

5. Update existing records:

    python manage.py import_victoriacrest \
        --from-file victoriacrest_data.json \
        --update-existing

6. Re-download / replace the gallery during updates:

    python manage.py import_victoriacrest \
        --from-file victoriacrest_data.json \
        --update-existing \
        --replace-images

DEPENDENCIES
------------

    pip install requests Pillow

Set APIFY_API_TOKEN in .env/environment, or pass --apify-token.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urlparse

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.html import strip_tags
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


# ============================================================================
# SOURCE CONFIGURATION
# ============================================================================

SOURCE_NAME = "Victoria Crest Homes"
SOURCE_WEBSITE = "https://victoriacresthomes.ng"
SOURCE_DOMAIN = "victoriacresthomes.ng"

DEFAULT_STATE_NAME = "Lagos"
DEFAULT_STATE_CODE = "LA"
DEFAULT_CITY_CANDIDATES = (
    "Lekki",
    "Ajah",
    "Sangotedo",
)


# ============================================================================
# DJANGO PROPERTY TYPE MAPPING
# ============================================================================

PROPERTY_TYPE_MAP = {
    "detached": "detached_house",
    "detached_house": "detached_house",
    "detached house": "detached_house",
    "semi_detached": "semi_detached",
    "semi detached": "semi_detached",
    "semi-detached": "semi_detached",
    "terrace": "terrace",
    "terrace house": "terrace",
    "townhouse": "terrace",
    "duplex": "duplex",
    "bungalow": "bungalow",
    "villa": "villa",
    "mansion": "mansion",
    "penthouse": "penthouse",
    "studio": "studio",
    "maisonette": "maisonette",
    "serviced apartment": "serviced_apt",
    "serviced_apt": "serviced_apt",
    "self contain": "self_contain",
    "self_contain": "self_contain",
    "mini flat": "mini_flat",
    "mini_flat": "mini_flat",
    "room and parlour": "room_parlour",
    "room_parlour": "room_parlour",
    "boys quarters": "boys_quarters",
    "boys_quarters": "boys_quarters",
    "shop": "shop",
    "store": "shop",
    "showroom": "showroom",
    "mall": "mall",
    "office": "office",
    "warehouse": "warehouse",
    "factory": "factory",
    "hotel": "hotel",
    "event center": "event_center",
    "event centre": "event_center",
    "filling station": "filling_station",
    "residential land": "residential_land",
    "commercial land": "commercial_land",
    "agricultural land": "agricultural_land",
    "industrial land": "industrial_land",
    "mixed use land": "mixed_use_land",
    "estate house": "estate_house",
}


TYPE_CATEGORY_MAP = {
    "detached_house": "residential",
    "semi_detached": "residential",
    "terrace": "residential",
    "duplex": "residential",
    "bungalow": "residential",
    "mansion": "residential",
    "villa": "residential",
    "studio": "residential",
    "1_bed_flat": "residential",
    "2_bed_flat": "residential",
    "3_bed_flat": "residential",
    "4_bed_flat": "residential",
    "penthouse": "residential",
    "maisonette": "residential",
    "serviced_apt": "residential",
    "self_contain": "residential",
    "room_parlour": "residential",
    "mini_flat": "residential",
    "boys_quarters": "residential",
    "estate_house": "residential",
    "cottage": "residential",
    "residential_land": "land",
    "commercial_land": "land",
    "agricultural_land": "land",
    "industrial_land": "land",
    "mixed_use_land": "land",
    "office": "commercial",
    "shop": "commercial",
    "mall": "commercial",
    "showroom": "commercial",
    "warehouse": "commercial",
    "factory": "commercial",
    "hotel": "commercial",
    "event_center": "commercial",
    "filling_station": "commercial",
    "compound": "special",
    "farm_house": "special",
    "student_accommodation": "special",
}


VALID_STATUS = {
    "for_sale",
    "for_rent",
    "sold",
    "rented",
    "pending",
}


# ============================================================================
# SOURCE LOCATION NORMALIZATION
# ============================================================================

# Victoria Crest uses estate/project names as City/Town values.  Those are
# source values, not necessarily canonical Nigerian cities in your database.
# Keep the source value in additional_features, but use these aliases when a
# canonical Django City exists.

LOCATION_ALIASES = {
    "citadel 1.0 phase b": "Sangotedo",
    "citadel 1.0 phase b (ajah)": "Sangotedo",
    "citadel views 1.0": "Sangotedo",
    "citadel oasis": "Ajah",
    "oasis height": "Lekki",
    "oasis heights": "Lekki",
    "capital terrace": "Ibeju-Lekki",
    "capital loft": "Ibeju-Lekki",
    "brum heights 7": "Lekki",
    "brum heights": "Lekki",
    "the den heights": "Lekki",
}

STATE_ALIASES = {
    "lagos state": "Lagos",
    "lagos": "Lagos",
    "fct": "Federal Capital Territory",
    "abuja": "Federal Capital Territory",
    "rivers state": "Rivers",
    "rivers": "Rivers",
}


# ============================================================================
# COMMAND
# ============================================================================


class Command(BaseCommand):
    help = (
        "Import Victoria Crest Homes properties from an Apify dataset "
        "or a local JSON/JSONL/CSV file"
    )

    def add_arguments(self, parser):
        source_group = parser.add_mutually_exclusive_group(required=True)

        source_group.add_argument(
            "--dataset-id",
            help="Apify Dataset ID from the actor run",
        )

        source_group.add_argument(
            "--from-file",
            metavar="PATH",
            help="Local Apify export: JSON, JSONL, CSV, or Apify JSON with an items wrapper",
        )

        parser.add_argument(
            "--apify-token",
            default=os.environ.get("APIFY_API_TOKEN", ""),
            help="Apify API token or APIFY_API_TOKEN environment variable",
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=1000,
            help="Maximum properties to process (default: 1000)",
        )

        parser.add_argument(
            "--skip-images",
            action="store_true",
            help="Do not download property images",
        )

        parser.add_argument(
            "--replace-images",
            action="store_true",
            help="During --update-existing, replace the existing gallery with source images",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be imported without writing to the database",
        )

        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update an existing source property instead of skipping it",
        )

        parser.add_argument(
            "--max-images",
            type=int,
            default=12,
            help="Maximum images saved per property (default: 12)",
        )

        parser.add_argument(
            "--image-timeout",
            type=int,
            default=30,
            help="Image download timeout in seconds (default: 30)",
        )

        parser.add_argument(
            "--image-delay",
            type=float,
            default=0.15,
            help="Delay between image downloads (default: 0.15 seconds)",
        )

        parser.add_argument(
            "--developer-name",
            default=SOURCE_NAME,
            help="Developer/brand name to attach to imported properties",
        )

    # ------------------------------------------------------------------
    # ENTRY POINT
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]
        self.skip_images = options["skip_images"]
        self.replace_images = options["replace_images"]
        self.update_existing = options["update_existing"]
        self.max_images = max(0, options["max_images"])
        self.image_timeout = max(5, options["image_timeout"])
        self.image_delay = max(0.0, options["image_delay"])
        self.developer_name = options["developer_name"]

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING("⚠ DRY RUN — no database changes will be made\n")
            )

        # 1. Load source data.
        if options["from_file"]:
            items = self._load_from_file(
                options["from_file"],
                options["limit"],
            )
        else:
            items = self._fetch_apify_dataset(
                options["dataset_id"],
                options["apify_token"],
                options["limit"],
            )

        # Only import actual property pages.
        property_items = [
            item for item in items
            if self._is_property_item(item)
        ]

        ignored = len(items) - len(property_items)

        self.stdout.write(
            f"📦 Loaded {len(items)} dataset rows; "
            f"{len(property_items)} property rows; "
            f"{ignored} non-property rows ignored\n"
        )

        if not property_items:
            raise CommandError(
                "No property records found. Check the Apify export and make sure "
                "page_type is 'property' or source_url points to /property/<slug>/."
            )

        # 2. Bootstrap shared objects.
        if not self.dry_run:
            self.developer = self._bootstrap_developer()
        else:
            self.developer = None

        # 3. Import.
        imported = 0
        updated = 0
        skipped = 0
        no_price = 0
        no_description = 0
        no_address = 0
        no_city = 0
        image_failures = 0
        errors = 0

        for index, raw_item in enumerate(property_items, 1):
            item = self._normalize_item(raw_item)
            title = item["title"]

            self.stdout.write(
                f"[{index:>3}/{len(property_items)}] {title[:90]}"
            )

            if not title:
                self.stdout.write(
                    self.style.WARNING("       ↳ No title — skipped")
                )
                skipped += 1
                continue

            try:
                result = self._import_one(item)

                if result == "imported":
                    imported += 1
                    if item["price"] is None:
                        no_price += 1
                    if not item["description"]:
                        no_description += 1
                    if not item["address"]:
                        no_address += 1
                    if not item["canonical_city"]:
                        no_city += 1

                    self.stdout.write(
                        self.style.SUCCESS("       ↳ ✓ imported")
                    )

                elif result == "updated":
                    updated += 1
                    self.stdout.write(
                        self.style.SUCCESS("       ↳ ↻ updated")
                    )

                elif result == "exists":
                    skipped += 1
                    self.stdout.write(
                        "       ↳ already exists — skipped"
                    )

                elif result == "dry_run":
                    imported += 1
                    self.stdout.write(
                        self.style.WARNING("       ↳ (dry-run preview)")
                    )

            except Exception as exc:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"       ↳ ERROR: {type(exc).__name__}: {exc}"
                    )
                )

        # 4. Summary.
        self.stdout.write("\n" + "─" * 72)
        self.stdout.write(
            self.style.SUCCESS(
                "Done! "
                f"Imported: {imported} | "
                f"Updated: {updated} | "
                f"Skipped: {skipped} | "
                f"Errors: {errors}"
            )
        )

        if no_price:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ {no_price} property/property records have no numeric price."
                )
            )

        if no_description:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ {no_description} property/property records have no description."
                )
            )

        if no_address:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ {no_address} property/property records have no source address."
                )
            )

        if no_city:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ {no_city} property/property records could not be mapped to a canonical City."
                )
            )

    # ------------------------------------------------------------------
    # DATA FETCHING
    # ------------------------------------------------------------------

    def _load_from_file(self, path: str, limit: int) -> list[dict[str, Any]]:
        file_path = Path(path).expanduser().resolve()

        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()

        try:
            if suffix == ".csv":
                return self._load_csv(file_path, limit)

            with file_path.open("r", encoding="utf-8-sig") as handle:
                text = handle.read().strip()

        except OSError as exc:
            raise CommandError(f"Could not read {file_path}: {exc}") from exc

        if not text:
            return []

        # Standard JSON.
        try:
            data = json.loads(text)

            if isinstance(data, dict):
                if isinstance(data.get("items"), list):
                    data = data["items"]
                elif isinstance(data.get("data"), list):
                    data = data["data"]
                else:
                    data = [data]

            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)][:limit]

        except json.JSONDecodeError:
            pass

        # JSON Lines fallback.
        records = []
        for line_number, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CommandError(
                    f"Could not parse JSON/JSONL on line {line_number}: {exc}"
                ) from exc
            if isinstance(record, dict):
                records.append(record)
            if len(records) >= limit:
                break

        return records

    def _load_csv(self, path: Path, limit: int) -> list[dict[str, Any]]:
        records = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                records.append(dict(row))
                if len(records) >= limit:
                    break
        return records

    def _fetch_apify_dataset(
        self,
        dataset_id: str,
        token: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        if not token:
            raise CommandError(
                "Apify API token is required. Set APIFY_API_TOKEN or use --apify-token."
            )

        url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
        params = {
            "token": token,
            "limit": limit,
            "clean": "true",
            "format": "json",
        }

        self.stdout.write(
            f"🌐 Fetching Apify dataset {dataset_id} …"
        )

        try:
            response = requests.get(
                url,
                params=params,
                timeout=90,
                headers={
                    "User-Agent": "NestovaVictoriaCrestImporter/1.0",
                },
            )
            response.raise_for_status()
            data = response.json()

        except requests.RequestException as exc:
            raise CommandError(
                f"Apify API request failed: {exc}"
            ) from exc
        except ValueError as exc:
            raise CommandError(
                f"Apify returned invalid JSON: {exc}"
            ) from exc

        if isinstance(data, dict):
            if isinstance(data.get("items"), list):
                data = data["items"]
            elif isinstance(data.get("data"), list):
                data = data["data"]
            else:
                data = [data]

        if not isinstance(data, list):
            raise CommandError(
                "Unexpected Apify response format; expected a list of dataset items."
            )

        return [item for item in data if isinstance(item, dict)][:limit]

    # ------------------------------------------------------------------
    # ITEM NORMALIZATION
    # ------------------------------------------------------------------

    def _is_property_item(self, item: dict[str, Any]) -> bool:
        page_type = self._string(item.get("page_type")).lower()
        if page_type == "property":
            return True

        url = self._string(item.get("source_url"))
        if not url:
            return False

        try:
            path = urlparse(url).path.rstrip("/")
        except Exception:
            return False

        return bool(
            re.match(r"^/property/[^/]+$", path, flags=re.I)
            and not re.match(r"^/property/page/\d+$", path, flags=re.I)
        )

    def _normalize_item(self, raw: dict[str, Any]) -> dict[str, Any]:
        title = self._string(raw.get("title"))

        description_html = self._string(
            raw.get("description")
        )
        description_text = self._string(
            raw.get("description_text")
        )

        # If HTML was supplied, strip it to create a reliable fallback text.
        if description_html and not description_text:
            description_text = self._html_to_text(description_html)

        address = self._string(raw.get("address"))

        # The old scraper occasionally returned "OPEN ON GOOGLE MAPS".
        if self._is_bad_address(address):
            address = ""

        source_city = self._string(raw.get("city"))
        source_state = self._string(raw.get("state"))
        country = self._string(raw.get("country")) or "Nigeria"
        neighborhood = self._string(raw.get("neighborhood"))

        google_maps_url = self._string(
            raw.get("google_maps_url")
        )

        source_price_text = self._string(
            raw.get("source_price_text")
        )

        price = self._parse_victoria_price(
            raw.get("price"),
            source_price_text,
        )

        bedrooms = self._to_int(raw.get("bedrooms"), default=0)
        bathrooms = self._to_int(raw.get("bathrooms"), default=0)
        rooms = self._to_int(raw.get("rooms"))
        year_built = self._to_int(raw.get("year_built"))
        parking_spaces = self._to_int(
            raw.get("parking_spaces"),
            default=0,
        )

        square_feet = self._to_int(raw.get("square_feet"))
        lot_size = self._to_int(raw.get("lot_size"))

        source_type = self._string(
            raw.get("source_property_type")
        ) or self._string(
            raw.get("property_type")
        )

        source_status = self._string(
            raw.get("source_status")
        ) or self._string(
            raw.get("status")
        )

        type_code = self._map_type(
            source_type,
            title,
            bedrooms,
        )

        status_code = self._map_status(
            self._string(raw.get("status")),
            source_status,
        )

        images = self._parse_images(
            raw.get("images")
        )

        # Some Apify exports have only featured_image.
        featured_image = self._string(
            raw.get("featured_image")
        )
        if featured_image and featured_image not in images:
            images.insert(0, featured_image)

        features = self._parse_features(
            raw.get("features")
        )

        additional_features = raw.get(
            "additional_features"
        )
        if not isinstance(additional_features, dict):
            additional_features = {}
        else:
            additional_features = dict(additional_features)

        # Preserve source-of-truth values exactly.
        additional_features.update({
            "source": SOURCE_NAME,
            "source_url": self._string(raw.get("source_url")),
            "source_property_id": self._string(
                raw.get("source_property_id")
            ),
            "source_property_type": source_type,
            "source_status": source_status,
            "source_price_text": source_price_text,
            "source_address": address,
            "source_state": source_state,
            "source_city": source_city,
            "source_neighborhood": neighborhood,
            "country": country,
            "google_maps_url": google_maps_url,
        })

        if features:
            additional_features["features"] = features

        additional_features["source_images"] = images

        canonical_state_name = self._resolve_state_name(
            source_state,
            country,
            title,
            address,
            description_text,
        )

        canonical_city_name = self._resolve_city_name(
            source_city,
            neighborhood,
            title,
            address,
            description_text,
            canonical_state_name,
            google_maps_url,
        )

        bool_flags = self._extract_bool_features(
            raw,
            features,
            description_text,
            title,
        )

        return {
            "source_property_id": self._string(
                raw.get("source_property_id")
            ),
            "source_url": self._string(
                raw.get("source_url")
            ),
            "title": title,
            "description": description_html or description_text,
            "description_text": description_text,
            "address": address,
            "country": country,
            "source_state": source_state,
            "source_city": source_city,
            "neighborhood": neighborhood,
            "canonical_state": canonical_state_name,
            "canonical_city": canonical_city_name,
            "google_maps_url": google_maps_url,
            "property_type": type_code,
            "source_property_type": source_type,
            "status": status_code,
            "source_status": source_status,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "rooms": rooms,
            "year_built": year_built,
            "parking_spaces": parking_spaces,
            "square_feet": square_feet,
            "lot_size": lot_size,
            "price": price,
            "source_price_text": source_price_text,
            "is_call_for_price": price is None,
            "features": features,
            "images": images,
            "featured_image": images[0] if images else "",
            "additional_features": additional_features,
            **bool_flags,
        }

    # ------------------------------------------------------------------
    # BASIC PARSERS
    # ------------------------------------------------------------------

    @staticmethod
    def _string(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    @staticmethod
    def _is_bad_address(value: str) -> bool:
        """Return True for scraper/UI placeholders that are not real addresses."""
        text = re.sub(r"\s+", " ", (value or "").strip()).lower()
        return text in {
            "", "open on google maps", "open google maps", "view on google maps",
            "google maps", "view map", "map", "n/a", "na", "none", "null", "-",
        }

    @staticmethod
    def _html_to_text(value: str) -> str:
        value = value or ""
        value = value.replace("<br>", "\n")
        value = value.replace("<br/>", "\n")
        value = value.replace("<br />", "\n")
        text = strip_tags(value)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        return text.strip()

    @staticmethod
    def _to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
        if value is None or value == "":
            return default

        try:
            if isinstance(value, bool):
                return int(value)
            return int(float(str(value).replace(",", "").strip()))
        except (TypeError, ValueError):
            match = re.search(r"\d+", str(value))
            if match:
                return int(match.group(0))
            return default

    @staticmethod
    def _parse_price_number(value: Any) -> Optional[Decimal]:
        if value is None or value == "":
            return None

        # Already numeric.
        if isinstance(value, (int, float, Decimal)):
            try:
                result = Decimal(str(value))
                return result if result > 0 else None
            except InvalidOperation:
                return None

        text = str(value).strip()
        if not text:
            return None

        # Remove currency and separators but preserve decimals.
        cleaned = re.sub(r"[^0-9.]", "", text)
        if not cleaned:
            return None

        try:
            result = Decimal(cleaned)
            return result if result > 0 else None
        except InvalidOperation:
            return None

    @classmethod
    def _parse_victoria_price(
        cls,
        value: Any,
        source_text: str = "",
    ) -> Optional[Decimal]:
        """
        Convert Victoria Crest values such as:

            143000000
            N143 M
            Starts From N143 M / With Solar
            N1.2 B
            N90 M / Outright

        into a Decimal naira amount.
        """

        numeric = cls._parse_price_number(value)

        # A numeric Apify value is already normalized.
        if numeric is not None:
            # Protect against the scraper returning 143 rather than 143M
            # only when the source text clearly carries an M/B suffix.
            source_lower = source_text.lower()
            if numeric < 1000000:
                m_match = re.search(
                    r"([0-9]+(?:\.[0-9]+)?)\s*(?:m|million)\b",
                    source_lower,
                )
                if m_match:
                    return Decimal(m_match.group(1)) * Decimal("1000000")

                b_match = re.search(
                    r"([0-9]+(?:\.[0-9]+)?)\s*(?:b|bn|billion)\b",
                    source_lower,
                )
                if b_match:
                    return Decimal(b_match.group(1)) * Decimal("1000000000")

            return numeric

        text = source_text or str(value or "")
        if not text.strip():
            return None

        # Billions first.
        match = re.search(
            r"([0-9]+(?:\.[0-9]+)?)\s*(?:b|bn|billion)\b",
            text,
            flags=re.I,
        )
        if match:
            return Decimal(match.group(1)) * Decimal("1000000000")

        # Millions.
        match = re.search(
            r"([0-9]+(?:\.[0-9]+)?)\s*(?:m|million)\b",
            text,
            flags=re.I,
        )
        if match:
            return Decimal(match.group(1)) * Decimal("1000000")

        # Plain naira amount.
        cleaned = re.sub(r"[^0-9.]", "", text)
        if not cleaned:
            return None

        try:
            result = Decimal(cleaned)
            return result if result > 0 else None
        except InvalidOperation:
            return None

    # ------------------------------------------------------------------
    # TYPE / STATUS
    # ------------------------------------------------------------------

    @classmethod
    def _map_type(
        cls,
        scraped_type: str,
        title: str = "",
        bedrooms: int = 0,
    ) -> str:
        key = (scraped_type or "").strip().lower()
        normalized_key = key.replace("-", " ").replace("_", " ")

        # Direct normalized choices.
        for candidate in (key, normalized_key):
            if candidate in PROPERTY_TYPE_MAP:
                return PROPERTY_TYPE_MAP[candidate]

        combined = f"{scraped_type} {title}".lower()

        # Highest priority first.
        if "semi-detached" in combined or "semi detached" in combined:
            return "semi_detached"

        if "maisonette" in combined:
            return "maisonette"

        if "penthouse" in combined:
            return "penthouse"

        if "villa" in combined:
            return "villa"

        if "bungalow" in combined:
            return "bungalow"

        if "mansion" in combined:
            return "mansion"

        if "warehouse" in combined:
            return "warehouse"

        if "office" in combined:
            return "office"

        if "shop" in combined or "store" in combined:
            return "shop"

        if "land" in combined:
            return "residential_land"

        if "terrace" in combined:
            return "terrace"

        if "duplex" in combined:
            return "duplex"

        if "apartment" in combined or "flat" in combined:
            if bedrooms == 1:
                return "1_bed_flat"
            if bedrooms == 2:
                return "2_bed_flat"
            if bedrooms == 3:
                return "3_bed_flat"
            if bedrooms >= 4:
                return "4_bed_flat"
            return "studio"

        return "estate_house"

    @staticmethod
    def _map_status(status: str, source_status: str = "") -> str:
        text = f"{status} {source_status}".lower().strip()

        if "rented" in text:
            return "rented"
        if "sold" in text:
            return "sold"
        if "pending" in text:
            return "pending"
        if "rent" in text:
            return "for_rent"

        return "for_sale"

    # ------------------------------------------------------------------
    # LOCATION RESOLUTION
    # ------------------------------------------------------------------

    def _resolve_state_name(
        self,
        source_state: str,
        country: str,
        title: str,
        address: str,
        description: str,
    ) -> str:
        value = self._string(source_state)
        key = value.lower()

        if key in STATE_ALIASES:
            return STATE_ALIASES[key]

        if value:
            existing = State.objects.filter(
                name__iexact=value
            ).first()
            if existing:
                return existing.name

        combined = " ".join(
            [title, address, description]
        ).lower()

        for state_name in State.objects.values_list("name", flat=True):
            if state_name.lower() in combined:
                return state_name

        if "lagos" in combined:
            return "Lagos"

        # Current Victoria Crest dataset is Lagos-based. Only use this as a
        # controlled fallback, never as the preferred source value.
        if country.lower() == "nigeria":
            return DEFAULT_STATE_NAME

        return ""

    def _resolve_city_name(
        self,
        source_city: str,
        neighborhood: str,
        title: str,
        address: str,
        description: str,
        state_name: str,
        google_maps_url: str,
    ) -> str:
        if not state_name:
            return ""

        source_key = re.sub(
            r"\s+",
            " ",
            source_city.lower().strip(),
        )

        # 1. Direct canonical City match.
        direct = City.objects.filter(
            state__name__iexact=state_name,
            name__iexact=source_city,
        ).first()

        if direct:
            return direct.name

        # 2. Explicit source alias.
        if source_key in LOCATION_ALIASES:
            alias = LOCATION_ALIASES[source_key]
            canonical = City.objects.filter(
                state__name__iexact=state_name,
                name__iexact=alias,
            ).first()
            if canonical:
                return canonical.name

        # 3. Search the estate/project name in ALL source fields. Victoria Crest
        # frequently puts the estate in the title while leaving City/Town blank.
        haystack = " ".join(
            [
                source_city,
                neighborhood,
                title,
                address,
                description,
                self._map_url_to_search_text(google_maps_url),
            ]
        ).lower()

        normalized_haystack = re.sub(
            r"[^a-z0-9]+",
            " ",
            haystack,
        ).strip()

        # First resolve known Victoria Crest estate/project aliases such as
        # "The Den Heights", "Brum Heights 7", and "Capital Terrace".
        # Longest alias wins to avoid partial matches.
        for alias_key, canonical_name in sorted(
            LOCATION_ALIASES.items(),
            key=lambda pair: len(pair[0]),
            reverse=True,
        ):
            alias_normalized = re.sub(
                r"[^a-z0-9]+",
                " ",
                alias_key.lower(),
            ).strip()

            if not alias_normalized or alias_normalized not in normalized_haystack:
                continue

            canonical = City.objects.filter(
                state__name__iexact=state_name,
                name__iexact=canonical_name,
                is_active=True,
            ).first()
            if canonical:
                return canonical.name

            # _get_city() will create this known canonical city when it is
            # missing from the database, preventing a NULL city_id.
            return canonical_name

        # Then search for any existing canonical City in the source data.
        # Longest names first prevents "Lekki" from winning over "Ibeju-Lekki".
        cities = list(
            City.objects.filter(
                state__name__iexact=state_name,
                is_active=True,
            ).values_list("name", flat=True)
        )

        cities.sort(key=lambda value: len(value), reverse=True)

        for city in cities:
            city_normalized = re.sub(
                r"[^a-z0-9]+",
                " ",
                city.lower(),
            ).strip()

            if city_normalized and city_normalized in normalized_haystack:
                return city

        # 4. Controlled defaults for Lagos listings only.
        if state_name.lower() == "lagos":
            for candidate in DEFAULT_CITY_CANDIDATES:
                exists = City.objects.filter(
                    state__name__iexact=state_name,
                    name__iexact=candidate,
                    is_active=True,
                ).exists()
                if exists:
                    return candidate

        return ""

    @staticmethod
    def _map_url_to_search_text(url: str) -> str:
        if not url:
            return ""

        try:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            values = []
            for key, chunks in query.items():
                values.append(key)
                values.extend(chunks)
            return " ".join(unquote(value) for value in values)
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # FEATURE EXTRACTION
    # ------------------------------------------------------------------

    def _parse_features(self, value: Any) -> list[str]:
        if isinstance(value, list):
            candidates = value
        elif isinstance(value, tuple):
            candidates = list(value)
        elif isinstance(value, str):
            text = value.strip()
            if not text:
                return []

            try:
                decoded = json.loads(text)
                if isinstance(decoded, list):
                    candidates = decoded
                else:
                    candidates = [text]
            except json.JSONDecodeError:
                # Support newline-separated exports.
                candidates = re.split(r"\n+|\s*\|\s*", text)
        else:
            candidates = []

        result = []
        for candidate in candidates:
            text = self._string(candidate)
            if not text:
                continue

            # Never store the scraped metadata block as an amenity.
            if re.match(
                r"^(ID|TYPE|BEDROOMS|BATHROOMS|ROOMS|GARAGES|YEAR BUILT|ADDRESS|COUNTRY|PROVINCE/STATE|CITY/TOWN|PROPERTY ID|PRICE|PROPERTY TYPE|PROPERTY STATUS)\\b",
                text,
                flags=re.I,
            ):
                continue

            result.append(text[:100])

        return list(dict.fromkeys(result))

    def _extract_bool_features(
        self,
        raw: dict[str, Any],
        features: list[str],
        description: str,
        title: str,
    ) -> dict[str, bool]:
        text_parts = [
            description,
            title,
            " ".join(features),
            self._string(raw.get("source_property_type")),
        ]

        combined = " ".join(text_parts).lower()

        def contains(*terms: str) -> bool:
            return any(term in combined for term in terms)

        return {
            "has_pool": contains("swimming pool", " pool"),
            "has_gym": contains("gym", "fitness"),
            "has_security": contains("security", "cctv", "controlled access"),
            "has_balcony": contains("balcony"),
            "has_garden": contains("garden", "landscap", "green park"),
            "has_garage": contains("garage") or self._to_int(raw.get("parking_spaces"), 0) > 0,
            "has_ac": contains("air conditioning", "air-conditioning", " a/c", " ac "),
            "is_furnished": contains("furnished"),
            "has_heating": contains("heating", "heater"),
            "pet_friendly": contains("pet friendly", "pet-friendly"),
        }

    # ------------------------------------------------------------------
    # FK BOOTSTRAP
    # ------------------------------------------------------------------

    def _bootstrap_developer(self) -> Developer:
        developer, created = Developer.objects.get_or_create(
            name=self.developer_name,
            defaults={
                "website": SOURCE_WEBSITE,
                "headquarters": "Lagos, Nigeria",
                "tagline": "Victoria Crest Homes property listings",
                "is_active": True,
                "is_featured": False,
            },
        )

        if created:
            self.stdout.write(
                f"  🏢 Created developer: {developer.name}"
            )

        return developer

    def _get_state(self, state_name: str) -> State:
        state_name = self._string(state_name) or DEFAULT_STATE_NAME

        aliases = STATE_ALIASES.get(
            state_name.lower(),
            state_name,
        )

        state = State.objects.filter(
            name__iexact=aliases
        ).first()

        if state:
            return state

        code = DEFAULT_STATE_CODE if aliases.lower() == "lagos" else "VC"

        state, _ = State.objects.get_or_create(
            name=aliases[:100],
            defaults={
                "code": code,
                "is_active": True,
            },
        )

        return state

    def _get_city(self, city_name: str, state: State) -> Optional[City]:
        city_name = self._string(city_name)

        if not city_name:
            return None

        city = City.objects.filter(
            state=state,
            name__iexact=city_name,
        ).first()

        if city:
            return city

        # Do not create artificial source project names such as
        # "Citadel 1.0 Phase B" as canonical cities.
        alias = LOCATION_ALIASES.get(
            city_name.lower()
        )

        if alias:
            city = City.objects.filter(
                state=state,
                name__iexact=alias,
            ).first()
            if city:
                return city

        # As a last resort, create the city. This is useful for a genuinely
        # new canonical city but is avoided for known estate aliases above.
        city, _ = City.objects.get_or_create(
            state=state,
            name=city_name[:100],
            defaults={"is_active": True},
        )
        return city

    def _get_property_type(self, code: str) -> PropertyType:
        category = TYPE_CATEGORY_MAP.get(
            code,
            "residential",
        )

        property_type = PropertyType.objects.filter(
            name=code
        ).first()

        if property_type:
            # Keep category current if this command is filling an existing seed.
            changed = False
            if property_type.category != category:
                property_type.category = category
                changed = True
            if not property_type.is_active:
                property_type.is_active = True
                changed = True
            if changed:
                property_type.save(update_fields=["category", "is_active"])
            return property_type

        return PropertyType.objects.create(
            name=code,
            category=category,
            is_active=True,
            display_order=0,
        )

    def _get_status(self, code: str) -> PropertyStatus:
        code = code if code in VALID_STATUS else "for_sale"
        status, _ = PropertyStatus.objects.get_or_create(
            name=code
        )
        return status

    # ------------------------------------------------------------------
    # CORE IMPORT
    # ------------------------------------------------------------------

    def _import_one(self, item: dict[str, Any]) -> str:
        title = item["title"]
        source_id = item["source_property_id"]
        source_url = item["source_url"]

        state = None
        city = None
        prop_type = None
        prop_status = None

        if not self.dry_run:
            state = self._get_state(
                item["canonical_state"]
            )
            if item["canonical_city"]:
                city = self._get_city(
                    item["canonical_city"],
                    state,
                )
            prop_type = self._get_property_type(
                item["property_type"]
            )
            prop_status = self._get_status(
                item["status"]
            )

        if self.dry_run:
            price = item["price"]
            price_display = (
                f"₦{price:,.0f}"
                if price is not None
                else "Price TBD"
            )

            self.stdout.write(
                f"       ↳ [{item['status']}] "
                f"{item['property_type']} | "
                f"{price_display} | "
                f"{item['bedrooms']}bd/{item['bathrooms']}ba | "
                f"State={item['canonical_state'] or 'UNKNOWN'} | "
                f"City={item['canonical_city'] or 'UNKNOWN'} | "
                f"Address={item['address'][:80] or 'UNKNOWN'} | "
                f"Images={len(item['images'])} | "
                f"Description={'YES' if item['description'] else 'NO'}"
            )

            return "dry_run"

        # --------------------------------------------------------------
        # DEDUPLICATION
        # --------------------------------------------------------------

        existing = None

        if source_id:
            existing = self._find_existing_by_source_id(
                source_id
            )

        if existing is None and source_url:
            existing = self._find_existing_by_source_url(
                source_url
            )

        if existing is None:
            existing = Property.objects.filter(
                title__iexact=title,
                developer=self.developer,
            ).first()

        if existing and not self.update_existing:
            return "exists"

        # --------------------------------------------------------------
        # EXTRA SOURCE META
        # --------------------------------------------------------------

        # Preserve the previous gallery before overwriting source metadata.
        previous_source_images = []
        if existing is not None:
            old_meta = existing.additional_features or {}
            if isinstance(old_meta, dict):
                candidate_old_images = old_meta.get("source_images")
                if isinstance(candidate_old_images, list):
                    previous_source_images = [
                        self._string(value)
                        for value in candidate_old_images
                        if self._string(value)
                    ]

        meta = dict(
            item["additional_features"]
        )

        meta.update({
            "source": SOURCE_NAME,
            "source_website": SOURCE_WEBSITE,
            "source_property_id": source_id,
            "source_url": source_url,
            "source_state": item["source_state"],
            "source_city": item["source_city"],
            "source_neighborhood": item["neighborhood"],
            "source_address": item["address"],
            "google_maps_url": item["google_maps_url"],
            "source_property_type": item["source_property_type"],
            "source_status": item["source_status"],
            "source_price_text": item["source_price_text"],
            "canonical_state": item["canonical_state"],
            "canonical_city": item["canonical_city"],
        })

        defaults = {
            "title": title,
            "description": item["description"],
            "state": state,
            "city": city,
            "address": (item["address"] or item["source_city"] or title)[:500],
            "property_type": prop_type,
            "status": prop_status,
            "bedrooms": item["bedrooms"],
            "bathrooms": item["bathrooms"],
            "square_feet": item["square_feet"],
            "lot_size": item["lot_size"],
            "year_built": item["year_built"],
            "parking_spaces": item["parking_spaces"],
            "price": item["price"],
            "has_garage": item["has_garage"],
            "has_pool": item["has_pool"],
            "has_garden": item["has_garden"],
            "has_security": item["has_security"],
            "has_gym": item["has_gym"],
            "has_balcony": item["has_balcony"],
            "is_furnished": item["is_furnished"],
            "has_ac": item["has_ac"],
            "has_heating": item["has_heating"],
            "pet_friendly": item["pet_friendly"],
            "additional_features": meta,
            "developer": self.developer,
            "is_active": True,
        }

        with transaction.atomic():
            if existing:
                # Never replace a good description with an empty one.
                if not item["description"]:
                    defaults["description"] = existing.description

                # Never replace a real price with NULL.
                if item["price"] is None:
                    defaults["price"] = existing.price

                # Keep a previously valid address when this run lacks it.
                if not item["address"]:
                    defaults["address"] = existing.address

                for field, value in defaults.items():
                    setattr(existing, field, value)

                existing.save()
                prop = existing
                action = "updated"

            else:
                prop = Property(**defaults)
                prop.save()
                action = "imported"

            # ----------------------------------------------------------
            # IMAGES
            # ----------------------------------------------------------

            if not self.skip_images and item["images"]:
                self._save_images(
                    prop,
                    item["images"],
                    title,
                    replace=self.replace_images and action == "updated",
                    previously_known_urls=previous_source_images,
                )

            # Store the current source gallery only after image processing,
            # so duplicate detection sees the previous run's URLs.
            meta["source_images"] = list(item["images"])
            prop.additional_features = meta
            prop.save(update_fields=["additional_features", "updated_at"])

            # ----------------------------------------------------------
            # AMENITIES
            # ----------------------------------------------------------

            self._save_amenities(
                prop,
                item["features"],
            )

        return action

    def _find_existing_by_source_id(self, source_id: str) -> Optional[Property]:
        if not source_id:
            return None

        # Current source ID is stored in JSONField. Django supports JSON key
        # lookups on JSONField; fall back gracefully if an older DB backend
        # doesn't support it.
        try:
            return Property.objects.filter(
                additional_features__source_property_id=source_id
            ).first()
        except Exception:
            return None

    def _find_existing_by_source_url(self, source_url: str) -> Optional[Property]:
        if not source_url:
            return None

        try:
            return Property.objects.filter(
                additional_features__source_url=source_url
            ).first()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # IMAGES
    # ------------------------------------------------------------------

    def _parse_images(self, value: Any) -> list[str]:
        if isinstance(value, list):
            candidates = value
        elif isinstance(value, tuple):
            candidates = list(value)
        elif isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            try:
                decoded = json.loads(value)
                candidates = decoded if isinstance(decoded, list) else [value]
            except json.JSONDecodeError:
                candidates = re.split(r"\n+|\s*\|\s*", value)
        else:
            candidates = []

        results = []

        for candidate in candidates:
            url = self._string(candidate)
            if not url:
                continue
            if not re.match(r"^https?://", url, flags=re.I):
                continue
            if url not in results:
                results.append(url)

        return results

    def _download_image(
        self,
        url: str,
        filename_base: str,
    ) -> Optional[ContentFile]:
        try:
            response = requests.get(
                url,
                timeout=self.image_timeout,
                stream=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; NestovaVictoriaCrest/1.0; "
                        "+https://nestova.com/)"
                    ),
                    "Referer": SOURCE_WEBSITE + "/",
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                },
            )
            response.raise_for_status()

            content_type = (
                response.headers.get(
                    "content-type",
                    "image/jpeg",
                )
                .split(";", 1)[0]
                .strip()
                .lower()
            )

            ext_map = {
                "image/jpeg": "jpg",
                "image/jpg": "jpg",
                "image/png": "png",
                "image/webp": "webp",
                "image/gif": "gif",
                "image/avif": "avif",
            }

            extension = ext_map.get(
                content_type,
                self._extension_from_url(url) or "jpg",
            )

            filename = f"{filename_base}.{extension}"

            chunks = []
            size = 0
            max_bytes = 15 * 1024 * 1024

            for chunk in response.iter_content(
                chunk_size=64 * 1024
            ):
                if not chunk:
                    continue
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError(
                        "Image exceeds 15 MB download limit"
                    )
                chunks.append(chunk)

            content = b"".join(chunks)
            if not content:
                return None

            return ContentFile(
                content,
                name=filename,
            )

        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(
                    f"       ↳ ⚠ image skipped: {url[:90]} — {exc}"
                )
            )
            return None

    @staticmethod
    def _extension_from_url(url: str) -> str:
        path = urlparse(url).path.lower()
        match = re.search(
            r"\.([a-z0-9]{2,5})$",
            path,
        )
        return match.group(1) if match else ""

    def _save_images(
        self,
        prop: Property,
        image_urls: list[str],
        title: str,
        replace: bool = False,
        previously_known_urls: Optional[list[str]] = None,
    ) -> None:
        if not image_urls:
            return

        if replace:
            PropertyImage.objects.filter(
                property=prop
            ).delete()

            # Remove existing featured image so a new source gallery becomes
            # the source of truth.
            if prop.featured_image:
                prop.featured_image.delete(
                    save=False
                )
                prop.featured_image = None
                prop.save(update_fields=["featured_image"])

        base = slugify(title)[:45] or "victoria-crest-property"
        existing_count = prop.images.count()
        known_urls = set(previously_known_urls or [])

        # Keep the first image as featured_image.
        for index, url in enumerate(
            image_urls[: self.max_images]
        ):
            if not url:
                continue

            # If not replacing and gallery already has images, skip adding the
            # exact same remote path more than once using stored source metadata.
            if not replace and url in known_urls:
                continue

            filename_base = (
                f"victoriacrest_{base}_{index:02d}"
            )

            image_file = self._download_image(
                url,
                filename_base,
            )

            if image_file is None:
                continue

            if (
                index == 0 and
                not prop.featured_image
            ):
                prop.featured_image.save(
                    image_file.name,
                    image_file,
                    save=True,
                )

            else:
                gallery_index = existing_count + index

                gallery = PropertyImage(
                    property=prop,
                    caption=f"{title} — photo {gallery_index + 1}",
                    is_primary=(
                        gallery_index == 0
                    ),
                    order=gallery_index,
                )

                gallery.image.save(
                    image_file.name,
                    image_file,
                    save=False,
                )
                gallery.save()

            if self.image_delay:
                time.sleep(self.image_delay)

    def _image_url_already_known(
        self,
        prop: Property,
        url: str,
    ) -> bool:
        meta = prop.additional_features or {}
        known_urls = meta.get("source_images")

        if isinstance(known_urls, list):
            return url in known_urls

        return False

    # ------------------------------------------------------------------
    # AMENITIES
    # ------------------------------------------------------------------

    def _save_amenities(
        self,
        prop: Property,
        feature_names: list[str],
    ) -> None:
        for raw_name in feature_names:
            name = self._string(raw_name)[:100]
            if not name:
                continue

            # These are prose/features, not metadata labels.
            if re.match(
                r"^(ID|TYPE|BEDROOMS|BATHROOMS|ROOMS|GARAGES|YEAR BUILT|ADDRESS|COUNTRY|PROVINCE/STATE|CITY/TOWN|PROPERTY ID|PRICE|PROPERTY TYPE|PROPERTY STATUS)\b",
                name,
                flags=re.I,
            ):
                continue

            amenity, _ = PropertyAmenity.objects.get_or_create(
                name=name,
                defaults={
                    "icon": "bi bi-check-circle",
                },
            )

            PropertyAmenityLink.objects.get_or_create(
                property=prop,
                amenity=amenity,
                defaults={
                    "is_available": True,
                },
            )
