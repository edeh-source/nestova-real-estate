"""
Django management command for importing MSHEL Homes properties from an Apify dataset.

Usage:
    python manage.py import_mshel --dataset-id DATASET_ID
    python manage.py import_mshel --dataset-id DATASET_ID --dry-run
    python manage.py import_mshel --dataset-id DATASET_ID --skip-images
    python manage.py import_mshel --dataset-id DATASET_ID --update-existing
    python manage.py import_mshel --from-file mshel.json

Environment:
    APIFY_API_TOKEN=...

Adjust the app import below if your models.py is in another Django app.
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

MSHEL_NAME = "Mshel Homes Limited"
MSHEL_WEBSITE = "https://properties.mshelhomes.com"
MSHEL_HQ = "Abuja, FCT"
APIFY_URL = "https://api.apify.com/v2/datasets/{dataset_id}/items"
REQUEST_TIMEOUT = 60
IMAGE_TIMEOUT = 30
IMAGE_MAX_BYTES = 15 * 1024 * 1024

VALID_STATUS = {"for_sale", "for_rent", "sold", "rented", "pending"}

TYPE_CATEGORY = {
    "detached_house": "residential", "semi_detached": "residential",
    "terrace": "residential", "duplex": "residential",
    "bungalow": "residential", "mansion": "residential",
    "villa": "residential", "cottage": "residential",
    "studio": "residential", "1_bed_flat": "residential",
    "2_bed_flat": "residential", "3_bed_flat": "residential",
    "4_bed_flat": "residential", "penthouse": "residential",
    "maisonette": "residential", "serviced_apt": "residential",
    "self_contain": "residential", "room_parlour": "residential",
    "mini_flat": "residential", "boys_quarters": "residential",
    "estate_house": "residential", "farm_house": "special",
    "student_accommodation": "special", "office": "commercial",
    "shop": "commercial", "mall": "commercial", "showroom": "commercial",
    "warehouse": "commercial", "factory": "commercial", "hotel": "commercial",
    "event_center": "commercial", "filling_station": "commercial",
    "residential_land": "land", "commercial_land": "land",
    "agricultural_land": "land", "industrial_land": "land",
    "mixed_use_land": "land", "compound": "special",
}

VALID_TYPES = set(TYPE_CATEGORY)

STATE_CODES = {
    "Abia": "AB", "Adamawa": "AD", "Akwa Ibom": "AK", "Anambra": "AN",
    "Bauchi": "BA", "Bayelsa": "BY", "Benue": "BE", "Borno": "BO",
    "Cross River": "CR", "Delta": "DE", "Ebonyi": "EB", "Edo": "ED",
    "Ekiti": "EK", "Enugu": "EN", "Gombe": "GO", "Imo": "IM",
    "Jigawa": "JI", "Kaduna": "KD", "Kano": "KN", "Katsina": "KT",
    "Kebbi": "KB", "Kogi": "KO", "Kwara": "KW", "Lagos": "LA",
    "Nasarawa": "NA", "Niger": "NI", "Ogun": "OG", "Ondo": "ON",
    "Osun": "OS", "Oyo": "OY", "Plateau": "PL", "Rivers": "RI",
    "Sokoto": "SO", "Taraba": "TA", "Yobe": "YO", "Zamfara": "ZA",
}


class Command(BaseCommand):
    help = "Import MSHEL Homes properties from an Apify dataset or JSON file"

    def add_arguments(self, parser):
        source = parser.add_mutually_exclusive_group(required=True)
        source.add_argument("--dataset-id", help="Apify Dataset ID")
        source.add_argument("--from-file", metavar="PATH", help="Local Apify JSON export")
        parser.add_argument(
            "--apify-token",
            default=os.environ.get("APIFY_API_TOKEN", ""),
            help="Apify API token or APIFY_API_TOKEN env var",
        )
        parser.add_argument(
            "--limit", type=int, default=0,
            help="Maximum records to import; 0 means all",
        )
        parser.add_argument("--skip-images", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--update-existing", action="store_true")
        parser.add_argument(
            "--replace-images", action="store_true",
            help="Delete current gallery and replace it with the latest Apify images on update",
        )
        parser.add_argument(
            "--replace-amenities", action="store_true",
            help="Replace existing amenity links on update",
        )

    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]
        self.skip_images = options["skip_images"]
        self.update_existing = options["update_existing"]
        self.replace_images = options["replace_images"]
        self.replace_amenities = options["replace_amenities"]

        if self.dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no database writes"))

        items = (
            self._load_file(options["from_file"], options["limit"])
            if options["from_file"]
            else self._fetch_dataset(options["dataset_id"], options["apify_token"], options["limit"])
        )

        if not items:
            raise CommandError("No Apify dataset items found.")

        self.stdout.write(self.style.SUCCESS(f"Loaded {len(items)} item(s)."))
        self.developer = None if self.dry_run else self._get_developer()

        imported = updated = skipped = failed = 0

        for index, raw in enumerate(items, 1):
            item = self._normalize(raw)
            title = (item.get("title") or "").strip()
            self.stdout.write(f"[{index}/{len(items)}] {title[:90] or '(no title)'}")

            if not title:
                skipped += 1
                self.stdout.write(self.style.WARNING("  -> skipped: no title"))
                continue

            try:
                result = self._import_one(item)
                if result == "imported":
                    imported += 1
                elif result == "updated":
                    updated += 1
                elif result == "exists":
                    skipped += 1
                elif result == "dry_run":
                    imported += 1
            except Exception as exc:
                failed += 1
                self.stdout.write(self.style.ERROR(f"  -> ERROR: {exc}"))

        self.stdout.write("=" * 72)
        self.stdout.write(self.style.SUCCESS(
            f"Imported={imported} Updated={updated} Skipped={skipped} Failed={failed}"
        ))

    # -------------------------------------------------------------------------
    # DATA FETCHING
    # -------------------------------------------------------------------------

    def _load_file(self, path: str, limit: int) -> list:
        if not os.path.exists(path):
            raise CommandError(f"File not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON: {exc}") from exc

        if isinstance(data, dict):
            data = data.get("items", data.get("data", data))
        if not isinstance(data, list):
            raise CommandError("Apify JSON export must contain a list of items.")
        return data[:limit] if limit else data

    def _fetch_dataset(self, dataset_id: str, token: str, limit: int) -> list:
        if not token:
            raise CommandError("APIFY_API_TOKEN is required.")
        params = {"token": token, "clean": "true", "format": "json", "desc": "false"}
        if limit:
            params["limit"] = limit
        try:
            response = requests.get(
                APIFY_URL.format(dataset_id=dataset_id),
                params=params,
                timeout=REQUEST_TIMEOUT,
                headers={"Accept": "application/json", "User-Agent": "Nestova-MSHEL-Importer/1.0"},
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise CommandError(f"Apify request failed: {exc}") from exc
        except ValueError as exc:
            raise CommandError(f"Apify returned invalid JSON: {exc}") from exc
        if not isinstance(data, list):
            raise CommandError("Apify dataset response is not a list.")
        return data[:limit] if limit else data

    # -------------------------------------------------------------------------
    # NORMALIZATION
    # -------------------------------------------------------------------------

    def _normalize(self, raw: dict) -> dict:
        item = dict(raw or {})

        for key in (
            "title", "slug", "source_url", "description", "address", "city", "state",
            "property_type", "status", "featured_image", "video_url", "virtual_tour_url",
            "mshel_sale_type",
        ):
            if item.get(key) is not None:
                item[key] = str(item[key]).strip()

        int_fields = (
            "bedrooms", "bathrooms", "square_feet", "lot_size", "parking_spaces",
            "year_built", "mshel_available_units", "mshel_garage_count", "mshel_kitchen_count",
        )
        for key in int_fields:
            item[key] = self._to_int(item.get(key))

        for key in ("price", "price_per_sqft", "mshel_area_sqm", "mshel_lot_size_sqm"):
            item[key] = self._to_decimal(item.get(key))

        item["images"] = self._strings(item.get("images"))
        item["amenities"] = self._strings(item.get("amenities"))
        item["amenities"] = self._unique(item["amenities"])

        if item.get("featured_image") and item["featured_image"] not in item["images"]:
            item["images"].insert(0, item["featured_image"])
        if not item.get("featured_image") and item["images"]:
            item["featured_image"] = item["images"][0]

        item["state"] = item.get("state") or self._infer_state(item.get("address") or "")
        item["city"] = item.get("city") or self._infer_city(item.get("address") or "", item["state"])
        item["address"] = item.get("address") or f"{item['city']}, {item['state']}"

        status = (item.get("status") or "for_sale").lower()
        item["status"] = status if status in VALID_STATUS else "for_sale"
        item["property_type"] = self._map_type(item.get("property_type"), item.get("title"))

        item["boolean_flags"] = self._boolean_flags(item)
        return item

    # -------------------------------------------------------------------------
    # FK OBJECTS
    # -------------------------------------------------------------------------

    def _get_developer(self):
        developer, created = Developer.objects.get_or_create(
            name=MSHEL_NAME,
            defaults={
                "website": MSHEL_WEBSITE,
                "headquarters": MSHEL_HQ,
                "tagline": "Premium Nigerian Real Estate",
                "is_active": True,
            },
        )
        if created:
            self.stdout.write(f"Created developer: {developer.name}")
        return developer

    def _get_state(self, name: str):
        name = (name or "FCT").strip()
        if name.lower() in {"abuja", "fct", "f.c.t", "federal capital territory"}:
            name, code = "FCT", "FCT"
        else:
            code = STATE_CODES.get(name, name[:10].upper())
        state = State.objects.filter(name__iexact=name).first()
        if state:
            return state
        return State.objects.create(name=name[:100], code=code[:10], is_active=True)

    def _get_city(self, name: str, state):
        name = (name or ("Abuja" if state.name == "FCT" else state.name)).strip()[:100]
        city = City.objects.filter(name__iexact=name, state=state).first()
        if city:
            return city
        return City.objects.create(name=name, state=state, is_active=True)

    def _get_type(self, code: str):
        code = code if code in VALID_TYPES else "estate_house"
        category = TYPE_CATEGORY.get(code, "residential")
        obj, _ = PropertyType.objects.get_or_create(
            name=code,
            defaults={"category": category, "is_active": True, "display_order": 0},
        )
        if obj.category != category or not obj.is_active:
            obj.category = category
            obj.is_active = True
            obj.save(update_fields=["category", "is_active"])
        return obj

    def _get_status(self, code: str):
        obj, _ = PropertyStatus.objects.get_or_create(name=code if code in VALID_STATUS else "for_sale")
        return obj

    # -------------------------------------------------------------------------
    # CORE IMPORT
    # -------------------------------------------------------------------------

    def _import_one(self, item: dict) -> str:
        title = item["title"]

        if self.dry_run:
            self.stdout.write(
                f"  -> dry-run: {item['city']}, {item['state']} | "
                f"{item['price'] or 'Price TBD'} | "
                f"images={len(item['images'])} | "
                f"amenities={len(item['amenities'])}"
            )
            return "dry_run"

        state = self._get_state(item["state"])
        city = self._get_city(item["city"], state)
        property_type = self._get_type(item["property_type"])
        status = self._get_status(item["status"])

        slug_base = slugify(item.get("slug") or title) or "mshel-property"
        slug_base = slug_base[:245]

        # Existing by developer + slug, then developer + exact title.
        existing = Property.objects.filter(developer=self.developer, slug=slug_base).first()
        if existing is None:
            existing = Property.objects.filter(developer=self.developer, title=title[:200]).first()

        if existing and not self.update_existing:
            return "exists"

        slug = self._resolve_slug(slug_base, existing)

        defaults = {
            "title": title[:200],
            "slug": slug,
            "description": item.get("description") or "",
            "state": state,
            "city": city,
            "address": (item.get("address") or f"{item['city']}, {item['state']}")[:500],
            "zip_code": "",
            "property_type": property_type,
            "status": status,
            "bedrooms": item.get("bedrooms", 0),
            "bathrooms": item.get("bathrooms", 0),
            "square_feet": item.get("square_feet") or None,
            "lot_size": item.get("lot_size") or None,
            "year_built": item.get("year_built") or None,
            "parking_spaces": item.get("parking_spaces", 0),
            "price": item.get("price"),
            "price_per_sqft": item.get("price_per_sqft"),
            "is_call_for_price": bool(item.get("is_call_for_price")) if item.get("is_call_for_price") is not None else item.get("price") is None,
            "developer": self.developer,
            "is_new": True,
            "is_active": True,
            "video_url": item.get("video_url") or "",
            "virtual_tour_url": item.get("virtual_tour_url") or "",
        }
        defaults.update(item["boolean_flags"])

        with transaction.atomic():
            if existing is None:
                prop = Property.objects.create(**defaults)
                action = "imported"
            else:
                prop = existing
                for field, value in defaults.items():
                    setattr(prop, field, value)
                prop.save()
                action = "updated"

            if not self.skip_images:
                self._save_images(
                    prop,
                    item["images"],
                    title,
                    replace=self.replace_images and action == "updated",
                )

            self._save_amenities(
                prop,
                item["amenities"],
                replace=self.replace_amenities and action == "updated",
            )

        self.stdout.write(
            f"  -> {action}: city={city.name}, state={state.name}, "
            f"images={len(item['images'])}, amenities={len(item['amenities'])}"
        )
        return action

    # -------------------------------------------------------------------------
    # IMAGES
    # -------------------------------------------------------------------------

    def _save_images(self, prop: Property, image_urls: list, title: str, replace: bool):
        image_urls = self._unique(image_urls)
        if not image_urls:
            return

        if replace:
            PropertyImage.objects.filter(property=prop).delete()
            if prop.featured_image:
                prop.featured_image.delete(save=False)
            prop.featured_image = None
            prop.save(update_fields=["featured_image"])
        else:
            existing_orders = set(prop.images.values_list("order", flat=True))
        
        for index, image_url in enumerate(image_urls):
            if not image_url:
                continue
            if not replace and index in existing_orders:
                continue

            content = self._download_image(image_url, f"mshel_{slugify(title)[:45]}_{index + 1}")
            if not content:
                continue

            # Every image is stored in PropertyImage.
            # Read the downloaded bytes once so the same image can be stored
            # in both PropertyImage and Property.featured_image.
            content.seek(0)
            image_bytes = content.read()

            gallery_file = ContentFile(
                image_bytes,
                name=content.name,
            )

            gallery = PropertyImage(
                property=prop,
                caption=f"{title} - image {index + 1}"[:200],
                is_primary=(index == 0),
                order=index,
            )
            gallery.image.save(
                gallery_file.name,
                gallery_file,
                save=False,
            )
            gallery.save()

            # First image is also the property's featured_image.
            if index == 0 and not prop.featured_image:
                featured_file = ContentFile(
                    image_bytes,
                    name=content.name,
                )
                prop.featured_image.save(
                    featured_file.name,
                    featured_file,
                    save=True,
                )

    def _download_image(self, image_url: str, filename_base: str) -> Optional[ContentFile]:
        try:
            response = requests.get(
                image_url,
                timeout=IMAGE_TIMEOUT,
                stream=True,
                allow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/151.0 Safari/537.36"
                    ),
                    "Referer": MSHEL_WEBSITE + "/",
                },
            )
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").split(";")[0].lower()
            ext = {
                "image/jpeg": "jpg",
                "image/jpg": "jpg",
                "image/png": "png",
                "image/webp": "webp",
                "image/gif": "gif",
            }.get(content_type, "jpg")

            buffer = BytesIO()
            total = 0
            for chunk in response.iter_content(16 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > IMAGE_MAX_BYTES:
                    raise ValueError("image exceeded 15MB limit")
                buffer.write(chunk)

            if total == 0:
                raise ValueError("empty response")

            return ContentFile(buffer.getvalue(), name=f"{filename_base}.{ext}")

        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(
                    f"  image skipped: {image_url[:100]} -> {exc}"
                )
            )
            return None

    # -------------------------------------------------------------------------
    # AMENITIES
    # -------------------------------------------------------------------------

    def _save_amenities(self, prop: Property, names: list, replace: bool):
        names = self._unique(names)
        if replace:
            PropertyAmenityLink.objects.filter(property=prop).delete()

        for name in names:
            name = name[:100].strip()
            if not name:
                continue
            amenity, _ = PropertyAmenity.objects.get_or_create(
                name=name,
                defaults={"icon": "bi bi-check-circle"},
            )
            PropertyAmenityLink.objects.get_or_create(
                property=prop,
                amenity=amenity,
                defaults={"is_available": True},
            )

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @staticmethod
    def _to_int(value) -> int:
        try:
            return int(float(str(value).replace(",", ""))) if value not in (None, "") else 0
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _to_decimal(value) -> Optional[Decimal]:
        if value in (None, ""):
            return None
        cleaned = re.sub(r"[^\d.\-]", "", str(value))
        if not cleaned:
            return None
        try:
            result = Decimal(cleaned)
            return result if result > 0 else None
        except InvalidOperation:
            return None

    @staticmethod
    def _strings(value) -> list:
        if not value:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple, set)):
            return []
        return [str(v).strip() for v in value if v is not None and str(v).strip()]

    @staticmethod
    def _unique(values: list) -> list:
        seen = set()
        result = []
        for value in values or []:
            text = str(value).strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result

    @staticmethod
    def _map_type(scraped_type: str, title: str) -> str:
        value = (scraped_type or "").strip().lower().replace("-", "_")
        title_text = (title or "").strip().lower()
        if value in VALID_TYPES:
            return value

        combined = f"{value} {title_text}"
        if re.search(r"semi[- ]detached", combined): return "semi_detached"
        if re.search(r"fully detached|detached", combined): return "detached_house"
        if "terrace" in combined: return "terrace"
        if "duplex" in combined: return "duplex"
        if "penthouse" in combined: return "penthouse"
        if "shop" in combined: return "shop"
        if "office" in combined: return "office"
        if "warehouse" in combined: return "warehouse"
        if "villa" in combined: return "villa"
        if "bungalow" in combined: return "bungalow"
        if "land" in combined:
            if "commercial" in combined: return "commercial_land"
            if "agricultural" in combined: return "agricultural_land"
            if "industrial" in combined: return "industrial_land"
            return "residential_land"

        bedroom = re.search(r"\b([1-6])\s*bedroom\b", combined)
        if bedroom and re.search(r"apartment|flat", combined):
            return {
                "1": "1_bed_flat", "2": "2_bed_flat", "3": "3_bed_flat",
                "4": "4_bed_flat", "5": "4_bed_flat", "6": "4_bed_flat",
            }[bedroom.group(1)]
        return "estate_house"

    @staticmethod
    def _boolean_flags(item: dict) -> dict:
        text = " ".join(item.get("amenities") or []).lower()
        def flag(key, words):
            if key in item and item[key] is not None:
                return bool(item[key])
            return any(word in text for word in words)
        return {
            "has_garage": flag("has_garage", ("garage", "parking")),
            "has_pool": flag("has_pool", ("pool", "swimming")),
            "has_garden": flag("has_garden", ("garden", "landscape", "lawn")),
            "has_security": flag("has_security", ("security", "fence", "gated")),
            "has_gym": flag("has_gym", ("gym", "fitness")),
            "has_balcony": flag("has_balcony", ("balcony", "terrace")),
            "is_furnished": flag("is_furnished", ("furnished",)),
            "has_ac": flag("has_ac", ("air conditioning", "a/c")),
            "has_heating": flag("has_heating", ("heating", "heater")),
            "pet_friendly": flag("pet_friendly", ("pet friendly", "pets allowed")),
        }

    @staticmethod
    def _infer_state(address: str) -> str:
        text = (address or "").lower()
        if "abuja" in text or "fct" in text or "federal capital territory" in text:
            return "FCT"
        for state in STATE_CODES:
            if re.search(rf"\b{re.escape(state.lower())}\b", text):
                return state
        return "FCT"

    @staticmethod
    def _infer_city(address: str, state: str) -> str:
        parts = [p.strip() for p in (address or "").split(",") if p.strip()]
        if state == "FCT":
            parts = [
                p for p in parts
                if not re.search(r"abuja|f\.c\.t|fct|federal capital territory", p, re.I)
            ]
            return parts[-1] if parts else "Abuja"
        return parts[-1] if parts else state

    def _resolve_slug(self, base: str, existing: Optional[Property]) -> str:
        slug = base[:245]
        qs = Property.objects.filter(slug=slug)
        if existing:
            qs = qs.exclude(pk=existing.pk)
        if not qs.exists():
            return slug

        counter = 2
        while True:
            candidate = f"{base[:235]}-{counter}"
            qs = Property.objects.filter(slug=candidate)
            if existing:
                qs = qs.exclude(pk=existing.pk)
            if not qs.exists():
                return candidate
            counter += 1

    @staticmethod
    def _json_value(value):
        return float(value) if isinstance(value, Decimal) else value
