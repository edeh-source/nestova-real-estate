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
from urllib.parse import unquote, urlparse

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.core.files.images import ImageFile
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
except ImportError as exc:  # pragma: no cover
    Image = None


SOURCE_NAME = "Adozillion Homes NG"
SOURCE_WEBSITE = "https://adozillionhomesng.com"
DEFAULT_STATE_NAME = "Lagos"
DEFAULT_STATE_CODE = "LA"

VALID_STATUS = {
    "for_sale",
    "for_rent",
    "sold",
    "rented",
    "pending",
}

TYPE_CATEGORY_MAP = {
    "detached_house": "residential",
    "semi_detached": "residential",
    "terrace": "residential",
    "duplex": "residential",
    "bungalow": "residential",
    "mansion": "residential",
    "villa": "residential",
    "cottage": "residential",
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

PROPERTY_TYPE_MAP = {
    "detached": "detached_house",
    "detached house": "detached_house",
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
    "self contain": "self_contain",
    "mini flat": "mini_flat",
    "room and parlour": "room_parlour",
    "boys quarters": "boys_quarters",
    "office": "office",
    "shop": "shop",
    "store": "shop",
    "showroom": "showroom",
    "mall": "mall",
    "warehouse": "warehouse",
    "factory": "factory",
    "hotel": "hotel",
    "residential land": "residential_land",
    "commercial land": "commercial_land",
    "agricultural land": "agricultural_land",
    "industrial land": "industrial_land",
    "mixed use land": "mixed_use_land",
    "estate house": "estate_house",
}

STATE_ALIASES = {
    "lagos": "Lagos",
    "lagos state": "Lagos",
    "edo": "Edo",
    "edo state": "Edo",
    "fct": "Federal Capital Territory",
    "abuja": "Federal Capital Territory",
}

# Adozillion pages currently expose useful location data in the address field.
# Keep source wording in JSON, but resolve it to canonical Nestova cities.
LOCATION_RULES = [
    (r"\bikate\b", "Lagos", "Lekki", "Ikate"),
    (r"\blekki\b", "Lagos", "Lekki", None),
    (r"\bibeju\b", "Lagos", "Ibeju-Lekki", None),
    (r"\bepe\b", "Lagos", "Epe", None),
    (r"\bimodi[- ]ijasi\b", "Lagos", "Epe", "Imodi-Ijasi"),
    (r"\bbenin city\b", "Edo", "Benin City", None),
    (r"\bugbokun\b", "Edo", "Benin City", "Ugbokun"),
]


class Command(BaseCommand):
    help = "Import Adozillion Homes NG properties from an Apify dataset or local export."

    def add_arguments(self, parser):
        source_group = parser.add_mutually_exclusive_group(required=True)
        source_group.add_argument("--dataset-id", help="Apify Dataset ID")
        source_group.add_argument("--from-file", help="JSON, JSONL, or CSV export")

        parser.add_argument(
            "--apify-token",
            default=os.environ.get("APIFY_API_TOKEN", ""),
            help="Apify API token or APIFY_API_TOKEN environment variable",
        )
        parser.add_argument("--limit", type=int, default=1000)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--skip-images", action="store_true")
        parser.add_argument("--update-existing", action="store_true")
        parser.add_argument("--replace-images", action="store_true")
        parser.add_argument("--max-images", type=int, default=20)
        parser.add_argument("--image-timeout", type=int, default=30)
        parser.add_argument("--image-delay", type=float, default=0.15)
        parser.add_argument("--developer-name", default=SOURCE_NAME)

    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]
        self.skip_images = options["skip_images"]
        self.update_existing = options["update_existing"]
        self.replace_images = options["replace_images"]
        self.max_images = max(0, options["max_images"])
        self.image_timeout = max(5, options["image_timeout"])
        self.image_delay = max(0.0, options["image_delay"])
        self.developer_name = options["developer_name"]

        if self.dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database changes will be made\n"))

        if options["from_file"]:
            items = self._load_from_file(options["from_file"], options["limit"])
        else:
            items = self._fetch_apify_dataset(
                options["dataset_id"],
                options["apify_token"],
                options["limit"],
            )

        property_items = [item for item in items if self._is_property_item(item)]
        self.stdout.write(
            f"Loaded {len(items)} dataset rows; {len(property_items)} property rows; "
            f"{len(items) - len(property_items)} non-property rows ignored\n"
        )

        if not property_items:
            raise CommandError("No Adozillion property records found.")

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
                    self.style.ERROR(
                        f"       -> ERROR: {type(exc).__name__}: {exc}"
                    )
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

    def _load_from_file(self, path: str, limit: int) -> list[dict[str, Any]]:
        file_path = Path(path).expanduser().resolve()
        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        if file_path.suffix.lower() == ".csv":
            with file_path.open("r", encoding="utf-8-sig", newline="") as fh:
                return [dict(row) for row in list(csv.DictReader(fh))[:limit]]

        text = file_path.read_text(encoding="utf-8-sig").strip()
        if not text:
            return []

        try:
            data = json.loads(text)
            if isinstance(data, dict):
                data = data.get("items") or data.get("data") or [data]
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)][:limit]
        except json.JSONDecodeError:
            pass

        records = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if isinstance(record, dict):
                records.append(record)
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

        self.stdout.write(f"Fetching Apify dataset {dataset_id} ...")
        try:
            response = requests.get(
                url,
                params=params,
                timeout=90,
                headers={"User-Agent": "NestovaAdozillionImporter/1.0"},
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
            raise CommandError("Unexpected Apify response format.")
        return [x for x in data if isinstance(x, dict)][:limit]

    def _is_property_item(self, item: dict[str, Any]) -> bool:
        page_type = self._string(item.get("page_type")).lower()
        if page_type == "property":
            return True

        url = self._string(item.get("source_url"))
        try:
            path = urlparse(url).path.rstrip("/")
        except Exception:
            return False
        return bool(re.match(r"^/product/[^/]+$", path, flags=re.I))

    # ============================================================
    # NORMALIZATION
    # ============================================================

    @staticmethod
    def _string(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _normalize_item(self, raw: dict[str, Any]) -> dict[str, Any]:
        source_url = self._string(raw.get("source_url"))
        slug = self._slug_from_url(source_url)

        raw_title = self._string(raw.get("title"))
        title = self._clean_title(raw_title, slug)

        source_address = self._string(raw.get("address"))
        source_country = self._string(raw.get("country")) or "Nigeria"

        inferred = self._infer_location(source_address, raw, title)
        state_name = inferred["state"] or self._string(raw.get("state"))
        city_name = inferred["city"] or self._string(raw.get("city"))
        neighborhood = (
            inferred["neighborhood"]
            or self._string(raw.get("neighborhood"))
        )

        if not state_name:
            state_name = self._infer_state_from_text(
                " ".join([title, source_address, source_country])
            )

        if not city_name:
            city_name = self._infer_city_from_text(
                " ".join([title, source_address, neighborhood])
            )

        bedrooms = self._to_int(raw.get("bedrooms"), 0) or 0
        bathrooms = self._to_int(raw.get("bathrooms"), 0) or 0
        rooms = self._to_int(raw.get("rooms"))
        year_built = self._to_int(raw.get("year_built"))
        parking_spaces = self._to_int(raw.get("parking_spaces"), 0) or 0
        square_feet = self._to_int(raw.get("square_feet"))
        lot_size = self._to_int(raw.get("lot_size"))

        source_type = self._string(raw.get("source_property_type"))
        scraped_type = self._string(raw.get("property_type"))
        status_source = self._string(raw.get("source_status")) or self._string(raw.get("status"))

        property_type = self._map_property_type(
            source_type or scraped_type,
            title,
            slug,
            bedrooms,
        )
        status = self._map_status(status_source or self._string(raw.get("status")))

        source_price_text = self._string(raw.get("source_price_text"))
        price = self._parse_price(raw.get("price"), source_price_text)

        description_html = self._string(raw.get("description"))
        description_text = self._string(raw.get("description_text"))
        if not description_text and description_html:
            description_text = self._strip_html(description_html)

        images = self._parse_images(raw.get("images"))
        featured_image = self._string(raw.get("featured_image"))
        if featured_image and featured_image not in images:
            images.insert(0, featured_image)

        features = self._parse_features(raw.get("features"))
        google_maps_url = self._string(raw.get("google_maps_url"))
        youtube_url = self._string(raw.get("youtube_url"))

        flags = self._bool_flags(raw, features, description_text, title)

        additional = raw.get("additional_features")
        if not isinstance(additional, dict):
            additional = {}
        else:
            additional = dict(additional)

        additional.update(
            {
                "source": SOURCE_NAME,
                "source_website": SOURCE_WEBSITE,
                "source_url": source_url,
                "source_slug": slug,
                "source_property_id": self._string(raw.get("source_property_id")),
                "source_title": raw_title,
                "source_property_type": source_type or scraped_type,
                "source_status": status_source,
                "source_price_text": source_price_text,
                "source_address": source_address,
                "source_state": self._string(raw.get("state")),
                "source_city": self._string(raw.get("city")),
                "source_neighborhood": self._string(raw.get("neighborhood")),
                "country": source_country,
                "google_maps_url": google_maps_url,
                "youtube_url": youtube_url,
                "rooms": rooms,
                "garages": parking_spaces,
                "features": features,
                "canonical_state": state_name,
                "canonical_city": city_name,
                "source_images": images,
            }
        )

        return {
            "source_url": source_url,
            "source_property_id": self._string(raw.get("source_property_id")) or slug,
            "slug": slug,
            "title": title,
            "description": description_html or description_text,
            "description_text": description_text,
            "address": source_address,
            "country": source_country,
            "source_state": self._string(raw.get("state")),
            "source_city": self._string(raw.get("city")),
            "neighborhood": neighborhood,
            "canonical_state": state_name,
            "canonical_city": city_name,
            "google_maps_url": google_maps_url,
            "youtube_url": youtube_url,
            "property_type": property_type,
            "source_property_type": source_type or scraped_type,
            "status": status,
            "source_status": status_source,
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
            "additional_features": additional,
            **flags,
        }

    @staticmethod
    def _slug_from_url(url: str) -> str:
        try:
            return urlparse(url).path.rstrip("/").split("/")[-1].strip().lower()
        except Exception:
            return ""

    def _clean_title(self, raw_title: str, slug: str) -> str:
        generic = {
            "adozillion homes",
            "adozillion homes ng",
            "adozillion homes | real estate",
        }
        if raw_title and raw_title.strip().lower() not in generic:
            return raw_title[:200]
        if not slug:
            return raw_title[:200]

        text = re.sub(r"[-_]+", " ", unquote(slug)).strip()
        replacements = {
            "residential land": "Residential Land",
            "lagos": "Lagos",
        }
        return replacements.get(text.lower(), text.title())[:200]

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
        address: str,
        raw: dict[str, Any],
        title: str,
    ) -> dict[str, Optional[str]]:
        text = " ".join(
            [
                address,
                self._string(raw.get("city")),
                self._string(raw.get("neighborhood")),
                title,
            ]
        ).lower()

        for pattern, state, city, neighborhood in LOCATION_RULES:
            if re.search(pattern, text, flags=re.I):
                return {
                    "state": state,
                    "city": city,
                    "neighborhood": neighborhood,
                }

        # Address formats like "Epe, Lagos" / "Ikate, Lekki"
        parts = [p.strip(" .,") for p in address.split(",") if p.strip()]
        if len(parts) >= 2:
            known_cities = [
                "Lekki",
                "Ibeju-Lekki",
                "Epe",
                "Benin City",
                "Ajah",
            ]
            for part in parts:
                for known in known_cities:
                    if part.lower() == known.lower():
                        return {
                            "state": "Lagos" if known != "Benin City" else "Edo",
                            "city": known,
                            "neighborhood": parts[0] if parts[0].lower() != known.lower() else None,
                        }

        return {"state": None, "city": None, "neighborhood": None}

    def _infer_state_from_text(self, text: str) -> str:
        normalized = text.lower()
        for alias, canonical in STATE_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", normalized):
                return canonical
        if "benin city" in normalized or "ugbokun" in normalized:
            return "Edo"
        if normalized.strip():
            return "Lagos"
        return ""

    def _infer_city_from_text(self, text: str) -> str:
        normalized = text.lower()
        if "benin city" in normalized or "ugbokun" in normalized:
            return "Benin City"
        if "ibeju" in normalized:
            return "Ibeju-Lekki"
        if "epe" in normalized or "imodi-ijasi" in normalized:
            return "Epe"
        if "lekki" in normalized or "ikate" in normalized:
            return "Lekki"
        return ""

    # ============================================================
    # PROPERTY TYPE / STATUS
    # ============================================================

    @classmethod
    def _map_property_type(
        cls,
        source_type: str,
        title: str,
        slug: str,
        bedrooms: int,
    ) -> str:
        text = f"{source_type} {title} {slug}".lower()
        normalized_source = source_type.lower().replace("_", " ").strip()

        if normalized_source in PROPERTY_TYPE_MAP:
            return PROPERTY_TYPE_MAP[normalized_source]

        if re.search(r"semi[- ]detached", text):
            return "semi_detached"
        if "maisonette" in text:
            return "maisonette"
        if "penthouse" in text:
            return "penthouse"
        if "villa" in text:
            return "villa"
        if "bungalow" in text:
            return "bungalow"
        if "mansion" in text:
            return "mansion"
        if "warehouse" in text:
            return "warehouse"
        if "office" in text:
            return "office"
        if "shop" in text or "store" in text:
            return "shop"
        if "land" in text:
            return "residential_land"
        if "terrace" in text:
            return "terrace"
        if "duplex" in text:
            return "duplex"

        if "apartment" in text or "flat" in text:
            effective_beds = bedrooms
            if effective_beds == 0:
                match = re.search(r"(\d+)\s*bed", text, flags=re.I)
                if match:
                    effective_beds = int(match.group(1))
            if effective_beds == 1:
                return "1_bed_flat"
            if effective_beds == 2:
                return "2_bed_flat"
            if effective_beds == 3:
                return "3_bed_flat"
            if effective_beds >= 4:
                return "4_bed_flat"
            return "studio"

        # Adozillion's current dataset contains some estate/project pages
        # with no narrower property type exposed in the source JSON.
        return "estate_house"

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
        if isinstance(value, (int, float, Decimal)):
            try:
                num = Decimal(str(value))
                return num if num > 0 else None
            except InvalidOperation:
                return None

        text = (source_text or cls._string(value)).strip()
        if not text:
            return None

        match = re.search(
            r"(\d+(?:\.\d+)?)\s*(bn|b|million|m|thousand|k)?\b",
            text,
            flags=re.I,
        )
        if not match:
            return None

        amount = Decimal(match.group(1))
        unit = (match.group(2) or "").lower()

        if unit in {"bn", "b"}:
            amount *= Decimal("1000000000")
        elif unit in {"million", "m"}:
            amount *= Decimal("1000000")
        elif unit in {"thousand", "k"}:
            amount *= Decimal("1000")

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

        results = []
        for candidate in candidates:
            url = self._string(candidate)
            if not re.match(r"^https?://", url, flags=re.I):
                continue
            if url not in results:
                results.append(url)
        return results

    def _download_image(self, url: str, filename_base: str) -> Optional[ContentFile]:
        try:
            response = requests.get(
                url,
                timeout=self.image_timeout,
                stream=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; NestovaAdozillion/1.0)",
                    "Referer": SOURCE_WEBSITE + "/",
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                },
            )
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()

            extension = self._extension_from_url(url)
            is_avif = content_type == "image/avif" or extension == "avif"

            # AVIF handling:
            # Convert AVIF to JPEG so the Django ImageField has a broadly
            # compatible stored format. Pillow must have AVIF support enabled.
            if is_avif:
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
                self.style.WARNING(
                    f"       -> image skipped: {url[:100]} — {exc}"
                )
            )
            return None

    def _convert_avif_to_jpeg(self, content: bytes, filename_base: str) -> ContentFile:
        if Image is None:
            raise RuntimeError(
                "Pillow is required for AVIF conversion. Run: pip install -U Pillow"
            )

        try:
            image = Image.open(io.BytesIO(content))
        except Exception as exc:
            raise RuntimeError(
                "Pillow could not decode this AVIF image. Install/upgrade a Pillow build "
                "with AVIF support."
            ) from exc

        # JPEG does not support alpha; flatten onto white when needed.
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
    # FEATURES
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

        result = []
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
        combined = " ".join(
            [description, title, " ".join(features)]
        ).lower()

        return {
            "has_garage": self._truthy(raw.get("has_garage")) or bool(
                self._to_int(raw.get("parking_spaces"), 0)
            ) or "garage" in combined,
            "has_pool": self._truthy(raw.get("has_pool")) or bool(re.search(r"\bpool\b|swimming pool", combined)),
            "has_garden": self._truthy(raw.get("has_garden")) or "garden" in combined,
            "has_security": self._truthy(raw.get("has_security")) or bool(re.search(r"security|cctv|access control", combined)),
            "has_gym": self._truthy(raw.get("has_gym")) or bool(re.search(r"\bgym\b|gymnasium|fitness", combined)),
            "has_balcony": self._truthy(raw.get("has_balcony")) or "balcony" in combined,
            "is_furnished": self._truthy(raw.get("is_furnished")) or "furnished" in combined,
            "has_ac": self._truthy(raw.get("has_ac")) or bool(re.search(r"air conditioning|air-conditioning", combined)),
            "has_heating": self._truthy(raw.get("has_heating")) or "heating" in combined,
            "pet_friendly": self._truthy(raw.get("pet_friendly")) or bool(re.search(r"pet friendly|pet-friendly", combined)),
        }

    @staticmethod
    def _truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
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
                "tagline": "Adozillion Homes property listings",
                "is_active": True,
            },
        )
        if created:
            self.stdout.write(f"Created developer: {developer.name}")
        return developer

    def _get_state(self, name: str) -> State:
        name = name or DEFAULT_STATE_NAME
        canonical = STATE_ALIASES.get(name.lower(), name)
        state = State.objects.filter(name__iexact=canonical).first()
        if state:
            return state
        code = DEFAULT_STATE_CODE if canonical.lower() == "lagos" else "ADO"
        return State.objects.create(name=canonical[:100], code=code, is_active=True)

    def _get_city(self, name: str, state: State) -> City:
        canonical = self._canonical_city_name(name)
        if not canonical:
            canonical = self._default_city_for_state(state.name)
        city = City.objects.filter(state=state, name__iexact=canonical).first()
        if city:
            return city
        return City.objects.create(state=state, name=canonical[:100], is_active=True)

    @staticmethod
    def _canonical_city_name(name: str) -> str:
        key = name.strip().lower()
        aliases = {
            "ibeju": "Ibeju-Lekki",
            "ibeju lekki": "Ibeju-Lekki",
            "ibeju-lekki": "Ibeju-Lekki",
            "epe": "Epe",
            "lekki": "Lekki",
            "ajah": "Ajah",
            "benin": "Benin City",
            "benin city": "Benin City",
        }
        return aliases.get(key, name.strip())

    @staticmethod
    def _default_city_for_state(state_name: str) -> str:
        return "Lekki" if state_name.lower() == "lagos" else "Benin City"

    def _get_property_type(self, code: str) -> PropertyType:
        category = TYPE_CATEGORY_MAP.get(code, "residential")
        obj, _ = PropertyType.objects.get_or_create(
            name=code,
            defaults={
                "category": category,
                "is_active": True,
                "display_order": 0,
            },
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
            price_display = f"₦{item['price']:,.0f}" if item["price"] is not None else "Price TBD"
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

        previous_source_images = []
        if existing and isinstance(existing.additional_features, dict):
            old = existing.additional_features.get("source_images")
            if isinstance(old, list):
                previous_source_images = [self._string(x) for x in old if self._string(x)]

        meta = dict(item["additional_features"])
        meta["source_images"] = list(item["images"])

        values = {
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
            "is_call_for_price": item["price"] is None,
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
        base = slugify(title)[:45] or "adozillion-property"
        existing_count = prop.images.count()

        for index, url in enumerate(image_urls[: self.max_images]):
            if not url or url in known:
                continue

            image_file = self._download_image(
                url,
                f"adozillion_{base}_{index:02d}",
            )
            if image_file is None:
                continue

            if index == 0 and not prop.featured_image:
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
                    is_primary=(gallery_index == 0),
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
