"""
management/commands/import_gidirealestate.py
--------------------------------------------
Import Gidi Real Estate and Investment Limited properties
from an Apify dataset.

Usage
-----
    python manage.py import_gidirealestate --dataset-id <ID>
    python manage.py import_gidirealestate --dataset-id <ID> --dry-run
    python manage.py import_gidirealestate --dataset-id <ID> --update-existing --replace-images
    python manage.py import_gidirealestate --dataset-id <ID> --skip-images --limit 50

The Apify API token is read from the APIFY_API_TOKEN environment variable
or supplied via --apify-token.
"""

from __future__ import annotations

import io
import json
import os
import re
import ssl
import time
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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

try:
    from PIL import Image
except ImportError:
    Image = None  # pragma: no cover


# ---------------------------------------------------------------------------
# Source constants
# ---------------------------------------------------------------------------
SOURCE_NAME = "Gidi Real Estate and Investment Limited"
SOURCE_WEBSITE = "https://gidirealestateinvestment.com"
DEFAULT_STATE_NAME = "Lagos"
DEFAULT_STATE_CODE = "LA"

# ---------------------------------------------------------------------------
# Description cleaning
# ---------------------------------------------------------------------------
# Apify scrapers sometimes append an "Additional Details" metadata block to
# property descriptions, e.g.:
#
#   Additional Details
#
#   * rooms: 2
#   * source: Victoria Crest Homes
#   * country: Nigeria
#   * garages: 2
#   * features: ['Gym', 'Swimming Pool', ...]
#   * scraped_at: 2026-09-04T01:52:32.892Z
#   * source_url: https://...
#   ...
#
# The regex below strips that block (and everything after it) from both the
# plain-text and HTML variants of the description.
_ADDITIONAL_DETAILS_RE = re.compile(
    r"\n*\bAdditional\s+Details\b[\s\S]*$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Status / type constants
# ---------------------------------------------------------------------------
VALID_STATUS = {"for_sale", "for_rent", "sold", "rented", "pending"}

TYPE_CATEGORY_MAP: dict[str, str] = {
    "detached_house": "residential",
    "semi_detached": "residential",
    "terrace": "residential",
    "duplex": "residential",
    "bungalow": "residential",
    "mansion": "residential",
    "villa": "residential",
    "penthouse": "residential",
    "maisonette": "residential",
    "serviced_apt": "residential",
    "self_contain": "residential",
    "room_parlour": "residential",
    "mini_flat": "residential",
    "studio": "residential",
    "estate_house": "residential",
    "1_bed_flat": "residential",
    "2_bed_flat": "residential",
    "3_bed_flat": "residential",
    "4_bed_flat": "residential",
    "residential_land": "land",
    "commercial_land": "land",
    "agricultural_land": "land",
    "mixed_use_land": "land",
    "office": "commercial",
    "shop": "commercial",
    "mall": "commercial",
    "showroom": "commercial",
    "warehouse": "commercial",
    "hotel": "commercial",
    "event_center": "commercial",
    "filling_station": "commercial",
    "compound": "special",
    "farm_house": "special",
    "student_accommodation": "special",
}

# Gidi's raw property_type values mapped to our internal codes.
# Extend this as new types appear in the dataset.
GIDI_TYPE_MAP: dict[str, str] = {
    "commercial": "mall",
    "estate": "estate_house",
    "semi_detached": "semi_detached",
    "residential_land": "residential_land",
    "commercial_land": "commercial_land",
    "terrace": "terrace",
    "duplex": "duplex",
    "bungalow": "bungalow",
    "penthouse": "penthouse",
    "villa": "villa",
    "apartment": "2_bed_flat",
    "studio": "studio",
    "detached": "detached_house",
    "detached_house": "detached_house",
    "maisonette": "maisonette",
    "office": "office",
    "shop": "shop",
    "warehouse": "warehouse",
    "hotel": "hotel",
}

# ---------------------------------------------------------------------------
# Location resolution
# ---------------------------------------------------------------------------
# The Gidi scraper stores raw city / state values that are sometimes
# imprecise (e.g. "Nigeria" as a state, or a neighbourhood as a city).
# STATE_ALIASES normalises the raw state field.
STATE_ALIASES: dict[str, str] = {
    "lagos": "Lagos",
    "lagos state": "Lagos",
    "ogun": "Ogun",
    "ogun state": "Ogun",
    "fct": "Federal Capital Territory",
    "abuja": "Federal Capital Territory",
    # Gidi quirks – state field occasionally carries a city/country name
    "nigeria": "Lagos",
    "epe": "Lagos",
    "epe.": "Lagos",
    "ibeju-lekki. lagos state.": "Lagos",
}

# Each rule: (regex_pattern, canonical_state, canonical_city, neighbourhood)
# Patterns are tested against a concatenation of raw city, state, address
# and title – first match wins.
LOCATION_RULES: list[tuple[str, str, str, Optional[str]]] = [
    (r"\bajah[- ]?sangotedo\b", "Lagos", "Ajah",           "Sangotedo"),
    (r"\bsangotedo\b",          "Lagos", "Ajah",           "Sangotedo"),
    (r"\bajah\b",               "Lagos", "Ajah",            None),
    (r"\bibeju[- ]?lekki\b",    "Lagos", "Ibeju-Lekki",    None),
    (r"\bibeju\b",              "Lagos", "Ibeju-Lekki",    None),
    (r"\babijo\b",              "Lagos", "Ibeju-Lekki",    "Abijo"),
    (r"\bketu[,\s]+epe\b",      "Lagos", "Epe",            "Ketu"),
    (r"\bigbonla\b",            "Lagos", "Epe",            "Igbonla"),
    (r"\bilara\b",              "Lagos", "Epe",            "Ilara"),
    (r"\bfowosheje\b",          "Lagos", "Epe",            "Fowosheje"),
    (r"\bepe\b",                "Lagos", "Epe",             None),
    (r"\blekki\b",              "Lagos", "Lekki",           None),
    (r"\bikate\b",              "Lagos", "Lekki",          "Ikate"),
    (r"\bmowe\b",               "Ogun",  "Mowe",            None),
    (r"\bikoyi\b",              "Lagos", "Ikoyi",           None),
    (r"\bvictoria island\b",    "Lagos", "Victoria Island", None),
    (r"\bikeja\b",              "Lagos", "Ikeja",           None),
    (r"\bgbagada\b",            "Lagos", "Gbagada",         None),
    (r"\byaba\b",               "Lagos", "Yaba",            None),
    (r"\bsurulere\b",           "Lagos", "Surulere",        None),
    (r"\bmagodo\b",             "Lagos", "Magodo",          None),
]

# Raw city → canonical city (exact-match fallback after LOCATION_RULES)
CITY_ALIASES: dict[str, str] = {
    "ajah": "Ajah",
    "ajah-sangotedo": "Ajah",
    "sangotedo": "Ajah",
    "lekki": "Lekki",
    "ibeju-lekki": "Ibeju-Lekki",
    "ibeju lekki": "Ibeju-Lekki",
    "abijo": "Ibeju-Lekki",
    "epe": "Epe",
    "ketu": "Epe",
    "ilara": "Epe",
    "fowosheje": "Epe",
    "igbonla": "Epe",
    "mowe": "Mowe",
    "ikeja": "Ikeja",
    "yaba": "Yaba",
    "surulere": "Surulere",
    "gbagada": "Gbagada",
    "ikoyi": "Ikoyi",
    "victoria island": "Victoria Island",
    "vi": "Victoria Island",
}


# ---------------------------------------------------------------------------
# SSL / HTTP helpers
# ---------------------------------------------------------------------------

class _LegacySSLAdapter(HTTPAdapter):
    """
    Requests transport adapter that works around the
    ``[SSL: UNEXPECTED_EOF_WHILE_READING]`` error produced by some WordPress /
    cPanel shared-hosting servers whose TLS stack closes the connection before
    Python's OpenSSL finishes the handshake.

    Root cause: those servers advertise TLS 1.3 but then terminate the
    connection before the handshake completes.  Setting
    ``OP_LEGACY_SERVER_CONNECT`` (OpenSSL 3.x flag, value 0x4) tells OpenSSL
    to tolerate the early EOF and fall back gracefully.

    The adapter also bundles a Retry policy so transient failures are
    automatically retried with exponential back-off before we give up.
    """

    def __init__(self, max_retries: int = 3, **kwargs):
        retry = Retry(
            total=max_retries,
            backoff_factor=1.5,          # waits 0 s, 1.5 s, 3 s between attempts
            status_forcelist={429, 500, 502, 503, 504},
            allowed_methods={"GET", "HEAD"},
            raise_on_status=False,
        )
        super().__init__(max_retries=retry, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        # OP_LEGACY_SERVER_CONNECT: accept premature EOF during TLS handshake.
        # The constant was added in OpenSSL 3.0; fall back to its raw value
        # (0x4) on older builds so the code still runs everywhere.
        legacy_flag = getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
        ctx.options |= legacy_flag
        kwargs["ssl_context"] = ctx
        super().init_poolmanager(*args, **kwargs)


def _build_image_session(max_retries: int = 3) -> requests.Session:
    """Return a requests.Session pre-configured with the legacy SSL adapter."""
    session = requests.Session()
    adapter = _LegacySSLAdapter(max_retries=max_retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ===========================================================================
# Command
# ===========================================================================

class Command(BaseCommand):
    help = "Import Gidi Real Estate properties from an Apify dataset (by dataset ID)."

    # -----------------------------------------------------------------------
    # Arguments
    # -----------------------------------------------------------------------

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset-id",
            required=True,
            help="Apify Dataset ID to pull items from.",
        )
        parser.add_argument(
            "--apify-token",
            default=os.environ.get("APIFY_API_TOKEN", ""),
            help="Apify API token (or set APIFY_API_TOKEN environment variable).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=1000,
            help="Maximum number of dataset items to fetch (default: 1000).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be imported without writing to the database.",
        )
        parser.add_argument(
            "--skip-images",
            action="store_true",
            help="Skip downloading and saving property images.",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update properties that already exist in the database.",
        )
        parser.add_argument(
            "--replace-images",
            action="store_true",
            help="Delete and re-download images when updating existing properties.",
        )
        parser.add_argument(
            "--max-images",
            type=int,
            default=20,
            help="Maximum number of images to import per property (default: 20).",
        )
        parser.add_argument(
            "--image-timeout",
            type=int,
            default=30,
            help="HTTP timeout in seconds for image downloads (default: 30).",
        )
        parser.add_argument(
            "--image-delay",
            type=float,
            default=0.15,
            help="Delay in seconds between image downloads (default: 0.15).",
        )
        parser.add_argument(
            "--developer-name",
            default=SOURCE_NAME,
            help=f'Developer name override (default: "{SOURCE_NAME}").',
        )

    # -----------------------------------------------------------------------
    # Entry point
    # -----------------------------------------------------------------------

    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]
        self.skip_images = options["skip_images"]
        self.update_existing = options["update_existing"]
        self.replace_images = options["replace_images"]
        self.max_images = max(0, options["max_images"])
        self.image_timeout = max(5, options["image_timeout"])
        self.image_delay = max(0.0, options["image_delay"])
        self.developer_name = options["developer_name"]
        # One session shared across all image downloads — keeps TCP connections
        # alive and applies the legacy-SSL adapter + retry policy consistently.
        self._image_session = _build_image_session(max_retries=3)

        if self.dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database changes will be made\n"))

        items = self._fetch_apify_dataset(
            options["dataset_id"],
            options["apify_token"],
            options["limit"],
        )

        property_items = [item for item in items if self._is_property_item(item)]
        self.stdout.write(
            f"Loaded {len(items)} dataset rows; "
            f"{len(property_items)} property rows; "
            f"{len(items) - len(property_items)} non-property rows ignored\n"
        )

        if not property_items:
            raise CommandError("No Gidi Real Estate property records found in the dataset.")

        self.developer = None if self.dry_run else self._bootstrap_developer()

        imported = updated = skipped = errors = 0

        for index, raw_item in enumerate(property_items, start=1):
            item = self._normalize_item(raw_item)
            self.stdout.write(f"[{index:>3}/{len(property_items)}] {item['title']}")

            if not item["title"]:
                self.stdout.write(self.style.WARNING("       -> no title; skipped"))
                skipped += 1
                continue

            try:
                result = self._import_one(item)
                if result == "imported":
                    imported += 1
                    self.stdout.write(self.style.SUCCESS("       -> imported"))
                elif result == "updated":
                    updated += 1
                    self.stdout.write(self.style.SUCCESS("       -> updated"))
                elif result == "exists":
                    skipped += 1
                    self.stdout.write("       -> already exists; skipped")
                else:
                    imported += 1
                    self.stdout.write(self.style.WARNING("       -> dry-run preview"))
            except Exception as exc:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f"       -> ERROR: {type(exc).__name__}: {exc}")
                )

        self.stdout.write("\n" + "-" * 72)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done! Imported: {imported} | Updated: {updated} | "
                f"Skipped: {skipped} | Errors: {errors}"
            )
        )

    # ============================================================
    # DATA SOURCE
    # ============================================================

    def _fetch_apify_dataset(
        self, dataset_id: str, token: str, limit: int
    ) -> list[dict[str, Any]]:
        if not token:
            raise CommandError(
                "Apify API token is required. "
                "Set APIFY_API_TOKEN or use --apify-token."
            )

        url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
        params = {
            "token": token,
            "limit": limit,
            "clean": "true",
            "format": "json",
        }

        self.stdout.write(f"Fetching Apify dataset {dataset_id!r} ...")
        try:
            response = requests.get(
                url,
                params=params,
                timeout=90,
                headers={"User-Agent": "NestovaGidiImporter/1.0"},
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise CommandError(f"Apify API request failed: {exc}") from exc
        except ValueError as exc:
            raise CommandError(f"Apify returned invalid JSON: {exc}") from exc

        if isinstance(data, dict):
            data = data.get("items") or data.get("data") or [data]
        if not isinstance(data, list):
            raise CommandError("Unexpected Apify response format (expected a JSON array).")
        return [x for x in data if isinstance(x, dict)][:limit]

    def _is_property_item(self, item: dict[str, Any]) -> bool:
        """Return True for individual property listings only."""
        # Gidi scraper sets page_type = "property" on individual listings.
        if self._string(item.get("page_type")).lower() == "property":
            return True
        # Fallback: URL path matches /portfolio/<slug>/
        url = self._string(item.get("source_url"))
        try:
            path = urlparse(url).path.rstrip("/")
        except Exception:
            return False
        return bool(re.match(r"^/portfolio/[^/]+$", path, flags=re.I))

    # ============================================================
    # NORMALIZATION
    # ============================================================

    @staticmethod
    def _string(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _normalize_item(self, raw: dict[str, Any]) -> dict[str, Any]:
        # --- Identity / URL -------------------------------------------------
        source_url = self._string(raw.get("source_url"))
        slug = self._slug_from_url(source_url) or self._string(raw.get("property_id"))
        source_property_id = self._string(raw.get("property_id")) or slug

        # --- Title ----------------------------------------------------------
        title = self._string(raw.get("title"))[:200]

        # --- Location -------------------------------------------------------
        raw_city = self._string(raw.get("city"))
        raw_state = self._string(raw.get("state"))
        address = self._string(raw.get("address"))
        country = self._string(raw.get("country")) or "Nigeria"

        inferred = self._infer_location(raw_city, raw_state, address, title)
        state_name = inferred["state"] or self._resolve_state(raw_state) or DEFAULT_STATE_NAME
        city_name = inferred["city"] or self._resolve_city(raw_city)
        neighborhood = inferred["neighborhood"]

        # --- Bedrooms / bathrooms / dimensions ------------------------------
        bedrooms_min = self._to_int(raw.get("bedrooms_min"), 0) or 0
        bedrooms_max = self._to_int(raw.get("bedrooms_max"), 0) or 0
        # Use minimum as the headline bedroom count; fall back to max.
        bedrooms = bedrooms_min or bedrooms_max
        bathrooms = self._to_int(raw.get("bathrooms"), 0) or 0
        parking_spaces = self._to_int(raw.get("parking_spaces"), 0) or 0
        square_feet = self._to_int(raw.get("square_feet"))

        # --- Property type / status -----------------------------------------
        raw_type = self._string(raw.get("property_type")).lower()
        property_type = GIDI_TYPE_MAP.get(raw_type, "estate_house")
        raw_status = self._string(raw.get("status"))
        status = self._map_status(raw_status)

        # --- Price ----------------------------------------------------------
        price_raw = raw.get("price")
        price_max_raw = raw.get("price_max")
        source_price_text = self._string(raw.get("source_price"))
        price = self._parse_price(price_raw, source_price_text)
        price_max = self._parse_price(price_max_raw) if price_max_raw not in (None, "") else None
        is_call_for_price = self._truthy(raw.get("is_call_for_price")) or price is None

        # --- Description (strip injected metadata block) --------------------
        description_html = self._string(
            raw.get("description_html") or raw.get("description")
        )
        description_text = self._string(raw.get("description_text"))

        if not description_text and description_html:
            description_text = self._strip_html(description_html)

        description_html = self._strip_additional_details(description_html)
        description_text = self._strip_additional_details(description_text)

        # --- Images / media -------------------------------------------------
        images = self._parse_images(raw.get("images"))
        featured_image = self._string(raw.get("featured_image"))
        if featured_image and re.match(r"^https?://", featured_image) and featured_image not in images:
            images.insert(0, featured_image)

        # --- Features & extra fields ----------------------------------------
        features = self._parse_features(raw.get("features"))
        nearby_landmarks = self._parse_features(raw.get("nearby_landmarks"))
        google_maps_url = self._string(raw.get("google_maps_url"))
        youtube_url = self._string(raw.get("youtube_url"))
        legal_title = self._string(raw.get("legal_title"))
        is_off_plan = self._truthy(raw.get("is_off_plan"))
        is_gated = self._truthy(raw.get("is_gated"))
        scraped_at = self._string(raw.get("scraped_at"))

        try:
            latitude = float(raw["latitude"]) if raw.get("latitude") not in (None, "") else None
        except (TypeError, ValueError):
            latitude = None
        try:
            longitude = float(raw["longitude"]) if raw.get("longitude") not in (None, "") else None
        except (TypeError, ValueError):
            longitude = None

        flags = self._bool_flags(raw, features, description_text, title)

        # --- additional_features dict (persisted as JSON) -------------------
        additional: dict[str, Any] = {
            "source": SOURCE_NAME,
            "source_website": SOURCE_WEBSITE,
            "source_url": source_url,
            "source_slug": slug,
            "source_property_id": source_property_id,
            "source_title": title,
            "source_property_type": raw_type,
            "source_status": raw_status,
            "source_price_text": source_price_text,
            "source_address": address,
            "source_city": raw_city,
            "source_state": raw_state,
            "country": country,
            "google_maps_url": google_maps_url,
            "youtube_url": youtube_url,
            "legal_title": legal_title,
            "latitude": latitude,
            "longitude": longitude,
            "nearby_landmarks": nearby_landmarks,
            "features": features,
            "is_off_plan": is_off_plan,
            "is_gated": is_gated,
            "bedrooms_min": bedrooms_min,
            "bedrooms_max": bedrooms_max,
            "price_max": str(price_max) if price_max is not None else None,
            "canonical_state": state_name,
            "canonical_city": city_name,
            "scraped_at": scraped_at,
            # source_images is populated later in _import_one after dedup
        }

        return {
            "source_url": source_url,
            "source_property_id": source_property_id,
            "slug": slug,
            "title": title,
            "description": description_html or description_text,
            "description_text": description_text,
            "address": address,
            "country": country,
            "source_state": raw_state,
            "source_city": raw_city,
            "neighborhood": neighborhood,
            "canonical_state": state_name,
            "canonical_city": city_name,
            "google_maps_url": google_maps_url,
            "youtube_url": youtube_url,
            "property_type": property_type,
            "source_property_type": raw_type,
            "status": status,
            "source_status": raw_status,
            "bedrooms": bedrooms,
            "bedrooms_min": bedrooms_min,
            "bedrooms_max": bedrooms_max,
            "bathrooms": bathrooms,
            "parking_spaces": parking_spaces,
            "square_feet": square_feet,
            "lot_size": None,
            "year_built": None,
            "price": price,
            "price_max": price_max,
            "source_price_text": source_price_text,
            "is_call_for_price": is_call_for_price,
            "is_off_plan": is_off_plan,
            "is_gated": is_gated,
            "legal_title": legal_title,
            "latitude": latitude,
            "longitude": longitude,
            "features": features,
            "nearby_landmarks": nearby_landmarks,
            "images": images,
            "additional_features": additional,
            **flags,
        }

    # -----------------------------------------------------------------------
    # Description helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _slug_from_url(url: str) -> str:
        try:
            return urlparse(url).path.rstrip("/").split("/")[-1].strip().lower()
        except Exception:
            return ""

    @classmethod
    def _strip_additional_details(cls, text: str) -> str:
        """
        Remove the 'Additional Details' metadata block that Apify scrapers
        inject at the end of some property descriptions.

        The block starts with the literal heading 'Additional Details'
        (case-insensitive) and continues as a bullet list to end-of-string.
        """
        if not text:
            return text
        return _ADDITIONAL_DETAILS_RE.sub("", text).rstrip()

    @staticmethod
    def _strip_html(value: str) -> str:
        text = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    # ============================================================
    # LOCATION
    # ============================================================

    def _infer_location(
        self,
        raw_city: str,
        raw_state: str,
        address: str,
        title: str,
    ) -> dict[str, Optional[str]]:
        """
        Run LOCATION_RULES against a concatenation of available location
        fields and the property title. Returns the first match.
        """
        text = " ".join([raw_city, raw_state, address, title]).lower()
        for pattern, state, city, neighbourhood in LOCATION_RULES:
            if re.search(pattern, text, flags=re.I):
                return {"state": state, "city": city, "neighborhood": neighbourhood}
        return {"state": None, "city": None, "neighborhood": None}

    @staticmethod
    def _resolve_state(raw: str) -> str:
        """Map a raw state string to a canonical state name."""
        key = raw.strip(" .").lower()
        return STATE_ALIASES.get(key, "Lagos" if raw.strip() else "")

    @staticmethod
    def _resolve_city(raw: str) -> str:
        """Map a raw city string to a canonical city name."""
        return CITY_ALIASES.get(raw.strip().lower(), raw.strip())

    # ============================================================
    # PROPERTY TYPE / STATUS
    # ============================================================

    @staticmethod
    def _map_status(value: str) -> str:
        text = value.lower()
        if "rented" in text:
            return "rented"
        if "sold" in text:
            return "sold"
        if "pending" in text:
            return "pending"
        if "rent" in text:
            return "for_rent"
        return "for_sale"

    # ============================================================
    # PRICES / PARSERS
    # ============================================================

    @staticmethod
    def _to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
        if value in (None, ""):
            return default
        try:
            return int(float(str(value).replace(",", "").strip()))
        except (TypeError, ValueError):
            match = re.search(r"\d+", str(value))
            return int(match.group()) if match else default

    @classmethod
    def _parse_price(cls, value: Any, source_text: str = "") -> Optional[Decimal]:
        """
        Parse a price from either a raw numeric value or a display string
        such as '₦85M', 'N15M', '2.1M', '78M'.
        """
        if isinstance(value, (int, float)):
            try:
                num = Decimal(str(value))
                return num if num > 0 else None
            except InvalidOperation:
                return None
        if isinstance(value, Decimal):
            return value if value > 0 else None

        text = (source_text or cls._string(value)).strip()
        if not text:
            return None

        # Strip leading currency symbols / codes (₦, N, NGN, $, £, €)
        text = re.sub(r"(?i)^(₦|NGN|N(?=\d)|\$|£|€)\s*", "", text)
        # Strip embedded commas and stray currency symbols
        text = re.sub(r"[₦,]", "", text)

        match = re.search(
            r"(\d+(?:\.\d+)?)\s*(bn|b|billion|million|m|thousand|k)?",
            text,
            flags=re.I,
        )
        if not match:
            return None

        amount = Decimal(match.group(1))
        unit = (match.group(2) or "").lower()
        if unit in {"bn", "b", "billion"}:
            amount *= Decimal("1_000_000_000")
        elif unit in {"million", "m"}:
            amount *= Decimal("1_000_000")
        elif unit in {"thousand", "k"}:
            amount *= Decimal("1_000")

        return amount if amount > 0 else None

    # ============================================================
    # IMAGES
    # ============================================================

    def _parse_images(self, value: Any) -> list[str]:
        if isinstance(value, list):
            candidates = value
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
            return []

        results: list[str] = []
        for candidate in candidates:
            url = self._string(candidate)
            if re.match(r"^https?://", url, flags=re.I) and url not in results:
                results.append(url)
        return results

    def _download_image(self, url: str, filename_base: str) -> Optional[ContentFile]:
        try:
            response = self._image_session.get(
                url,
                timeout=self.image_timeout,
                stream=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; NestovaGidi/1.0)",
                    "Referer": SOURCE_WEBSITE + "/",
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                },
            )
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            extension = self._extension_from_url(url)

            if content_type == "image/avif" or extension == "avif":
                return self._convert_avif_to_jpeg(content, filename_base)

            ext_map = {
                "image/jpeg": "jpg",
                "image/jpg": "jpg",
                "image/png": "png",
                "image/webp": "webp",
                "image/gif": "gif",
            }
            extension = ext_map.get(content_type, extension or "jpg")
            return ContentFile(content, name=f"{filename_base}.{extension}")
        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(f"       -> image skipped: {url[:100]} — {exc}")
            )
            return None

    def _convert_avif_to_jpeg(self, content: bytes, filename_base: str) -> ContentFile:
        if Image is None:
            raise RuntimeError(
                "Pillow is required for AVIF→JPEG conversion. "
                "Run: pip install -U Pillow"
            )
        image = Image.open(io.BytesIO(content))
        if image.mode in ("RGBA", "LA"):
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=image.getchannel("A"))
            image = background
        else:
            image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=92, optimize=True)
        return ContentFile(output.getvalue(), name=f"{filename_base}.jpg")

    @staticmethod
    def _extension_from_url(url: str) -> str:
        path = urlparse(url).path.lower()
        match = re.search(r"\.([a-z0-9]{2,5})$", path)
        return match.group(1) if match else ""

    # ============================================================
    # FEATURES / FLAGS
    # ============================================================

    def _parse_features(self, value: Any) -> list[str]:
        if isinstance(value, list):
            candidates = value
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
            return []

        result: list[str] = []
        for candidate in candidates:
            text = self._string(candidate)
            if text and text not in result:
                result.append(text[:100])
        return result

    def _bool_flags(
        self,
        raw: dict[str, Any],
        features: list[str],
        description: str,
        title: str,
    ) -> dict[str, bool]:
        combined = " ".join([description, title, " ".join(features)]).lower()

        # Gidi uses has_parking (not has_garage), so map accordingly.
        has_parking_flag = (
            self._truthy(raw.get("has_parking"))
            or bool(self._to_int(raw.get("parking_spaces"), 0))
            or bool(re.search(r"\bgarage\b|\bparking\b", combined))
        )

        return {
            "has_garage": has_parking_flag,
            "has_pool": (
                self._truthy(raw.get("has_pool"))
                or bool(re.search(r"\bpool\b|swimming pool", combined))
            ),
            "has_garden": (
                self._truthy(raw.get("has_garden"))
                or "garden" in combined
            ),
            "has_security": (
                self._truthy(raw.get("has_security"))
                or bool(re.search(r"security|cctv|access control|guard", combined))
            ),
            "has_gym": (
                self._truthy(raw.get("has_gym"))
                or bool(re.search(r"\bgym\b|gymnasium|fitness", combined))
            ),
            "has_balcony": (
                self._truthy(raw.get("has_balcony"))
                or "balcony" in combined
            ),
            "is_furnished": (
                self._truthy(raw.get("is_furnished"))
                or "furnished" in combined
            ),
            "has_ac": (
                self._truthy(raw.get("has_ac"))
                or bool(re.search(r"air.?conditioning", combined))
            ),
            "has_heating": False,
            "pet_friendly": False,
        }

    @staticmethod
    def _truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    # ============================================================
    # DJANGO OBJECTS
    # ============================================================

    def _bootstrap_developer(self) -> Developer:
        developer, created = Developer.objects.get_or_create(
            name=self.developer_name,
            defaults={
                "website": SOURCE_WEBSITE,
                "headquarters": "Lagos, Nigeria",
                "tagline": "Gidi Real Estate property listings",
                "is_active": True,
            },
        )
        if created:
            self.stdout.write(f"Created developer: {developer.name}")
        return developer

    def _get_state(self, name: str) -> State:
        name = name or DEFAULT_STATE_NAME
        state = State.objects.filter(name__iexact=name).first()
        if state:
            return state
        code = DEFAULT_STATE_CODE if name.lower() == "lagos" else name[:2].upper()
        return State.objects.create(name=name[:100], code=code, is_active=True)

    def _get_city(self, name: str, state: State) -> City:
        if not name:
            name = "Lekki" if state.name.lower() == "lagos" else state.name
        city = City.objects.filter(state=state, name__iexact=name).first()
        if city:
            return city
        return City.objects.create(state=state, name=name[:100], is_active=True)

    def _get_property_type(self, code: str) -> PropertyType:
        category = TYPE_CATEGORY_MAP.get(code, "residential")
        obj, _ = PropertyType.objects.get_or_create(
            name=code,
            defaults={"category": category, "is_active": True, "display_order": 0},
        )
        changed = False
        if obj.category != category:
            obj.category = category
            changed = True
        if not obj.is_active:
            obj.is_active = True
            changed = True
        if changed:
            obj.save(update_fields=["category", "is_active"])
        return obj

    def _get_status(self, code: str) -> PropertyStatus:
        code = code if code in VALID_STATUS else "for_sale"
        obj, _ = PropertyStatus.objects.get_or_create(name=code)
        return obj

    # ============================================================
    # IMPORT
    # ============================================================

    def _import_one(self, item: dict[str, Any]) -> str:
        if self.dry_run:
            price_display = f"₦{item['price']:,.0f}" if item["price"] else "Price TBD"
            self.stdout.write(
                f"       -> [{item['status']}] {item['property_type']} | "
                f"{price_display} | {item['bedrooms']}bd/{item['bathrooms']}ba | "
                f"State={item['canonical_state'] or 'UNKNOWN'} | "
                f"City={item['canonical_city'] or 'UNKNOWN'} | "
                f"Address={item['address'] or 'UNKNOWN'} | "
                f"Images={len(item['images'])}"
            )
            return "dry_run"

        state = self._get_state(item["canonical_state"])
        city = self._get_city(item["canonical_city"], state)
        prop_type = self._get_property_type(item["property_type"])
        prop_status = self._get_status(item["status"])

        # Try to find an existing property via multiple strategies.
        existing = None
        source_id = item["source_property_id"]
        source_url = item["source_url"]

        if source_id:
            existing = self._find_existing_by_source_id(source_id)
        if existing is None and source_url:
            existing = self._find_existing_by_source_url(source_url)
        if existing is None:
            existing = Property.objects.filter(
                title__iexact=item["title"],
                developer=self.developer,
            ).first()

        if existing and not self.update_existing:
            return "exists"

        # Carry forward the previously stored image URLs so we don't
        # re-download images that are already saved.
        previous_source_images: list[str] = []
        if existing and isinstance(existing.additional_features, dict):
            old = existing.additional_features.get("source_images")
            if isinstance(old, list):
                previous_source_images = [self._string(x) for x in old if self._string(x)]

        meta = dict(item["additional_features"])
        meta["source_images"] = list(item["images"])

        values: dict[str, Any] = {
            "title": item["title"],
            "description": item["description"],
            "state": state,
            "city": city,
            "address": (item["address"] or item["canonical_city"] or item["title"])[:500],
            "property_type": prop_type,
            "status": prop_status,
            "bedrooms": item["bedrooms"],
            "bathrooms": item["bathrooms"],
            "square_feet": item["square_feet"],
            "lot_size": item["lot_size"],
            "year_built": item["year_built"],
            "parking_spaces": item["parking_spaces"],
            "price": item["price"],
            "is_call_for_price": item["is_call_for_price"],
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
                # Preserve existing values for fields the scraper left empty.
                if not item["description"]:
                    values["description"] = existing.description
                if item["price"] is None:
                    values["price"] = existing.price
                if not item["address"]:
                    values["address"] = existing.address
                for field, value in values.items():
                    setattr(existing, field, value)
                existing.save()
                prop = existing
                action = "updated"
            else:
                prop = Property(**values)
                prop.save()
                action = "imported"

            if not self.skip_images and item["images"]:
                self._save_images(
                    prop,
                    item["images"],
                    item["title"],
                    replace=self.replace_images and action == "updated",
                    previously_known_urls=previous_source_images,
                )

            # Persist meta after images so source_images list is complete.
            prop.additional_features = meta
            prop.save(update_fields=["additional_features", "updated_at"])

            self._save_amenities(prop, item["features"])

        return action

    def _find_existing_by_source_id(self, source_id: str) -> Optional[Property]:
        try:
            return Property.objects.filter(
                additional_features__source_property_id=source_id
            ).first()
        except Exception:
            return None

    def _find_existing_by_source_url(self, source_url: str) -> Optional[Property]:
        try:
            return Property.objects.filter(
                additional_features__source_url=source_url
            ).first()
        except Exception:
            return None

    # ============================================================
    # IMAGE STORAGE
    # ============================================================

    def _save_images(
        self,
        prop: Property,
        image_urls: list[str],
        title: str,
        replace: bool = False,
        previously_known_urls: Optional[list[str]] = None,
    ) -> None:
        if replace:
            PropertyImage.objects.filter(property=prop).delete()
            if prop.featured_image:
                prop.featured_image.delete(save=False)
                prop.featured_image = None
                prop.save(update_fields=["featured_image"])

        known = set(previously_known_urls or [])
        base = slugify(title)[:45] or "gidi-property"
        existing_count = prop.images.count()

        for index, url in enumerate(image_urls[: self.max_images]):
            if not url or url in known:
                continue

            image_file = self._download_image(url, f"gidi_{base}_{index:02d}")
            if image_file is None:
                continue

            if index == 0 and not prop.featured_image:
                prop.featured_image.save(image_file.name, image_file, save=True)
            else:
                gallery_index = existing_count + index
                gallery = PropertyImage(
                    property=prop,
                    caption=f"{title} — photo {gallery_index + 1}",
                    is_primary=(gallery_index == 0),
                    order=gallery_index,
                )
                gallery.image.save(image_file.name, image_file, save=False)
                gallery.save()

            if self.image_delay:
                time.sleep(self.image_delay)

    # ============================================================
    # AMENITIES
    # ============================================================

    def _save_amenities(self, prop: Property, features: list[str]) -> None:
        for feature in features:
            name = self._string(feature)[:100]
            if not name:
                continue
            amenity, _ = PropertyAmenity.objects.get_or_create(name=name)
            PropertyAmenityLink.objects.get_or_create(
                property=prop,
                amenity=amenity,
                defaults={"is_available": True},
            )