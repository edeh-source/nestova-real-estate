"""
Django Management Command: import_aibenproperties
=================================================
Imports property data scraped from aibenproperties.com (via Apify) into your
Nestova Django database, fetching directly from the Apify Dataset API.

USAGE
-----
    # Pull straight from Apify (primary)
    python manage.py import_aibenproperties <DATASET_ID>

    # Local JSON fallback (for offline dev / CI)
    python manage.py import_aibenproperties --json-file /path/to/apify_output.json

OPTIONS
-------
    --token TOKEN          Apify API token (default: APIFY_TOKEN env var or settings.APIFY_TOKEN)
    --user USERNAME        Assign properties to this user (default: first superuser)
    --skip-images          Import text data only — skip downloading images
    --update-existing      Re-import properties whose slug already exists
    --dry-run              Preview what would be imported; nothing is saved
    --limit N              Only import the first N properties (useful for testing)
    --json-file PATH       Use a local JSON export instead of the Apify API

FINDING YOUR DATASET ID
-----------------------
    Apify Console → your actor run → "Dataset" tab → ID shown at the top
    e.g.  abc123XYZ...

TOKEN RESOLUTION ORDER
----------------------
    1. --token flag
    2. APIFY_TOKEN environment variable
    3. settings.APIFY_TOKEN  (add to your Django settings / .env)
    4. Error if none found (only when fetching from Apify, not needed for --json-file)

PRICE HANDLING
--------------
    aibenproperties.com shows "Call for price" on most listings.
    This command sets price=0 as a sentinel value.
    In your Django template, check:
        {% if property.price %} → show price
        {% else %}              → show WhatsApp / Call Us CTA
"""

import json
import os
import re
import time
from io import BytesIO
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify


class Command(BaseCommand):
    help = "Import properties scraped from aibenproperties.com via Apify Dataset API"

    # ── Nigerian state code lookup ─────────────────────────────────────────────
    STATE_CODES = {
        "FCT":     "FCT",
        "Lagos":   "LAG",
        "Rivers":  "RIV",
        "Kano":    "KAN",
        "Ogun":    "OGU",
        "Oyo":     "OYO",
        "Delta":   "DEL",
        "Anambra": "ANA",
        "Enugu":   "ENU",
        "Abuja":   "FCT",   # alias
    }

    APIFY_DATASET_URL = "https://api.apify.com/v2/datasets/{dataset_id}/items"

    def add_arguments(self, parser):
        # Primary source: Apify dataset ID  (optional — can use --json-file instead)
        parser.add_argument(
            "dataset_id",
            nargs="?",
            type=str,
            default=None,
            help="Apify Dataset ID to fetch from (find it in the Apify Console run page)",
        )
        parser.add_argument(
            "--token",
            type=str,
            default=None,
            metavar="TOKEN",
            help="Apify API token (default: APIFY_TOKEN env var or settings.APIFY_TOKEN)",
        )
        # Fallback source: local JSON file
        parser.add_argument(
            "--json-file",
            type=str,
            default=None,
            metavar="PATH",
            help="Use a local JSON export instead of fetching from Apify",
        )
        parser.add_argument(
            "--user",
            type=str,
            default=None,
            metavar="USERNAME",
            help="User to assign as listed_by (default: first superuser)",
        )
        parser.add_argument(
            "--skip-images",
            action="store_true",
            default=False,
            help="Skip downloading property images (import data only)",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            default=False,
            help="Update already-imported properties (matched by slug)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would be imported without saving anything",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            metavar="N",
            help="Only import the first N properties (useful for testing)",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Entry point
    # ══════════════════════════════════════════════════════════════════════════

    def handle(self, *args, **options):
        User = get_user_model()

        # ── Validate source args ─────────────────────────────────────────────
        if not options["dataset_id"] and not options["json_file"]:
            raise CommandError(
                "Provide either a dataset_id positional argument or --json-file PATH.\n"
                "  Example (Apify):     python manage.py import_aibenproperties abc123XYZ\n"
                "  Example (local):     python manage.py import_aibenproperties --json-file data.json"
            )
        if options["dataset_id"] and options["json_file"]:
            raise CommandError("Pass either dataset_id or --json-file, not both.")

        # ── Load data ────────────────────────────────────────────────────────
        if options["json_file"]:
            items = self._load_from_json(options["json_file"])
            self.stdout.write(f"Source: local file → {options['json_file']}")
        else:
            token = self._resolve_token(options["token"])
            items = self._fetch_from_apify(options["dataset_id"], token)
            self.stdout.write(f"Source: Apify dataset → {options['dataset_id']}")

        # Drop null / empty items (listing pages return null from the actor)
        items = [i for i in items if i and i.get("title")]

        if options["limit"]:
            items = items[: options["limit"]]

        self.stdout.write(
            self.style.SUCCESS(f"Loaded {len(items)} properties")
        )

        # ── Resolve assigned user ────────────────────────────────────────────
        if options["user"]:
            try:
                user = User.objects.get(username=options["user"])
            except User.DoesNotExist:
                raise CommandError(f'User "{options["user"]}" not found.')
        else:
            user = User.objects.filter(is_superuser=True).first() or User.objects.first()
            if not user:
                raise CommandError("No users found. Create a superuser first.")

        self.stdout.write(f"Assigning listed_by → {user.username}\n")

        # ── Import loop ──────────────────────────────────────────────────────
        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

        for idx, item in enumerate(items, 1):
            title = item.get("title", "Unknown")
            self.stdout.write(f"[{idx}/{len(items)}] {title}")

            if options["dry_run"]:
                self._dry_run_display(item)
                continue

            try:
                result = self._import_property(
                    item,
                    user,
                    skip_images=options["skip_images"],
                    update_existing=options["update_existing"],
                )
                stats[result] += 1
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  ✗ ERROR: {exc}"))
                stats["errors"] += 1

        # ── Summary ──────────────────────────────────────────────────────────
        self.stdout.write("\n" + "─" * 50)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created: {stats['created']}  |  Updated: {stats['updated']}  "
                f"|  Skipped: {stats['skipped']}  |  Errors: {stats['errors']}"
            )
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Data source helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _resolve_token(self, cli_token: str | None) -> str:
        """
        Resolve Apify API token in priority order:
          1. --token flag
          2. APIFY_TOKEN environment variable
          3. settings.APIFY_TOKEN
        """
        token = (
            cli_token
            or os.environ.get("APIFY_TOKEN")
            or getattr(settings, "APIFY_TOKEN", None)
        )
        if not token:
            raise CommandError(
                "No Apify token found.\n"
                "  Set one of:\n"
                "    --token YOUR_TOKEN\n"
                "    export APIFY_TOKEN=YOUR_TOKEN\n"
                "    APIFY_TOKEN = 'YOUR_TOKEN'  in your Django settings"
            )
        return token

    def _fetch_from_apify(self, dataset_id: str, token: str) -> list:
        """
        Fetch all items from an Apify dataset, paginating automatically.
        Apify's default page size is 250; we loop until we have everything.
        """
        url        = self.APIFY_DATASET_URL.format(dataset_id=dataset_id)
        all_items  = []
        offset     = 0
        page_size  = 250

        self.stdout.write("Fetching from Apify API…")

        while True:
            resp = requests.get(
                url,
                params={
                    "token":  token,
                    "format": "json",
                    "clean":  "true",   # omits empty/null items on Apify's side
                    "limit":  page_size,
                    "offset": offset,
                },
                timeout=60,
            )

            if resp.status_code == 401:
                raise CommandError("Apify returned 401 Unauthorized — check your API token.")
            if resp.status_code == 404:
                raise CommandError(
                    f"Dataset '{dataset_id}' not found on Apify — check the ID."
                )
            resp.raise_for_status()

            batch = resp.json()
            if not batch:
                break  # no more items

            all_items.extend(batch)
            self.stdout.write(f"  … fetched {len(all_items)} items so far")

            if len(batch) < page_size:
                break  # last page
            offset += page_size

        return all_items

    def _load_from_json(self, path: str) -> list:
        """Load items from a local Apify JSON export."""
        if not os.path.exists(path):
            raise CommandError(f"File not found: {path}")

        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)

        # Apify exports a plain list; some wrappers add {"items": [...]}
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict) and "items" in raw:
            return raw["items"]
        return [raw]

    # ══════════════════════════════════════════════════════════════════════════
    # Single property import
    # ══════════════════════════════════════════════════════════════════════════

    def _import_property(self, item, user, skip_images=False, update_existing=False):
        from property.models import (
            City, Property, PropertyImage, PropertyStatus, PropertyType, State,
        )

        # ── 1. Related objects (get-or-create) ────────────────────────────────

        state_name = (item.get("state") or "FCT").strip()
        state, _ = State.objects.get_or_create(
            name=state_name,
            defaults={
                "code":      self.STATE_CODES.get(state_name, state_name[:3].upper()),
                "is_active": True,
            },
        )

        city_name = (item.get("city") or "Abuja").strip()
        city, _ = City.objects.get_or_create(
            name=city_name,
            state=state,
            defaults={"is_active": True},
        )

        type_name = (item.get("property_type") or "Estate").strip()
        prop_type, _ = PropertyType.objects.get_or_create(name=type_name)

        status_name = (item.get("status") or "for_sale").strip()
        prop_status, _ = PropertyStatus.objects.get_or_create(name=status_name)

        # ── 2. Slug & existence check ─────────────────────────────────────────

        base_slug = (item.get("slug") or slugify(item.get("title", ""))).strip()
        if not base_slug:
            base_slug = slugify(item.get("title", "property"))

        existing = Property.objects.filter(slug=base_slug).first()

        if existing and not update_existing:
            self.stdout.write(f"  ↷ Skipping (already imported): {base_slug}")
            return "skipped"

        prop   = existing if existing else Property(slug=base_slug)
        action = "update" if existing else "create"
        self.stdout.write(f"  {'↻ Updating' if existing else '✓ Creating'}: {base_slug}")

        # ── 3. Core fields ────────────────────────────────────────────────────

        prop.title         = item.get("title", "").strip()
        prop.description   = (item.get("description") or "").strip()
        prop.address       = (item.get("address") or f"{city_name}, {state_name}").strip()
        prop.state         = state
        prop.city          = city
        prop.property_type = prop_type
        prop.status        = prop_status
        prop.listed_by     = user
        prop.is_active     = item.get("is_active", True)
        prop.is_featured   = item.get("is_featured", False)

        raw_beds  = item.get("bedrooms")
        raw_baths = item.get("bathrooms")
        prop.bedrooms  = int(raw_beds)  if raw_beds  else 0
        prop.bathrooms = int(raw_baths) if raw_baths else 0

        raw_sqft = item.get("square_feet")
        prop.square_feet = float(raw_sqft) if raw_sqft else None

        # ── PRICE ─────────────────────────────────────────────────────────────
        # aibenproperties.com shows "Call for price" — stored as 0 (sentinel).
        # Template: {% if property.price %} show price {% else %} show CTA {% endif %}
        prop.price = None
        prop.is_call_for_price = True

        # ── SEO ───────────────────────────────────────────────────────────────
        prop.meta_title       = prop.title[:70]
        prop.meta_description = (item.get("description") or "")[:160]

        prop.save()

        # ── 4. Images ─────────────────────────────────────────────────────────

        if not skip_images:
            images       = item.get("images") or []
            featured_url = item.get("featured_image") or (images[0] if images else None)

            if featured_url and not prop.featured_image:
                img_data = self._download_image(featured_url)
                if img_data:
                    fname = self._safe_filename(featured_url, f"{base_slug}-cover")
                    prop.featured_image.save(fname, img_data, save=True)
                    self.stdout.write(f"  📷 Featured image: {fname}")

            if prop.images.count() == 0:
                saved = 0
                for i, img_url in enumerate(images[:10]):
                    time.sleep(0.4)
                    img_data = self._download_image(img_url)
                    if img_data:
                        fname = self._safe_filename(img_url, f"{base_slug}-{i + 1}")
                        pi = PropertyImage(
                            property=prop,
                            is_primary=(i == 0),
                            order=i + 1,
                            caption=prop.title,
                        )
                        pi.image.save(fname, img_data, save=True)
                        saved += 1
                self.stdout.write(f"  🖼  Gallery: {saved} image(s) saved")

        return "updated" if existing else "created"

    # ══════════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _download_image(self, url: str):
        """Download an image URL and return a ContentFile, or None on failure."""
        try:
            resp = requests.get(
                url,
                timeout=30,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; NestovaBot/1.0)",
                    "Referer":    "https://nestovaproperty.com/",
                },
                stream=True,
            )
            resp.raise_for_status()
            if "image" not in resp.headers.get("Content-Type", ""):
                self.stdout.write(
                    self.style.WARNING(f"  ⚠  Not an image: {url}")
                )
                return None
            return ContentFile(resp.content)
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"  ⚠  Download failed: {exc}"))
            return None

    @staticmethod
    def _safe_filename(url: str, prefix: str = "img") -> str:
        """Generate a clean, filesystem-safe filename from a URL."""
        parsed = urlparse(url)
        _, ext = os.path.splitext(parsed.path)
        ext    = ext.lower() if ext else ".jpg"
        safe   = re.sub(r"[^a-z0-9\-]", "-", prefix.lower())
        return f"{safe}{ext}"

    def _dry_run_display(self, item):
        self.stdout.write(
            f"  [DRY RUN]\n"
            f"    slug:    {item.get('slug')}\n"
            f"    city:    {item.get('city')}, {item.get('state')}\n"
            f"    type:    {item.get('property_type')}\n"
            f"    status:  {item.get('status')}\n"
            f"    beds:    {item.get('bedrooms')}\n"
            f"    baths:   {item.get('bathrooms')}\n"
            f"    images:  {len(item.get('images') or [])}\n"
        )