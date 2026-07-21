"""
Management command: python manage.py remove_all_watermarks

Removes ALL watermarks (PropertyPro + NESTOVA) from every scraped listing image:

  Strategy A — preferred:
      Re-downloads the original image straight from the PropertyPro CDN URL
      stored in listing.image_url.  Only one inpainting pass is needed
      (to erase the PropertyPro watermark).  Produces the best quality.

  Strategy B — automatic fallback:
      If the original CDN URL is unreachable or stale, downloads the current
      Cloudinary image.  Since NESTOVA is white centred text in the same
      40-60 % height band the inpainting already targets, the same OpenCV pass
      removes it too.  Slightly lower quality but still clean.

  In both cases the NESTOVA stamp is NEVER re-applied (stamp_nestova=False).
  The clean image overwrites the existing Cloudinary file in place.

Usage
-----
    # Dry run on 3 listings to verify quality before committing
    python manage.py remove_all_watermarks --limit 3

    # Process everything (92 listings — takes ~3-5 min)
    python manage.py remove_all_watermarks

    # Skip re-download from PropertyPro; always use Cloudinary image as source
    python manage.py remove_all_watermarks --cloudinary-only
"""

import hashlib
import requests

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from bookings.image_processor import process_image_bytes
from bookings.models import ScrapedListing


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://propertypro.ng/",
}


def _download(url: str) -> bytes | None:
    """Download a URL; return bytes or None on any failure."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        # Guard against redirect-to-placeholder / tiny error pages
        if len(r.content) < 2_000:
            return None
        return r.content
    except Exception:
        return None


def _ext_from_url(url: str) -> str:
    """Guess the file extension from a URL path."""
    path = url.split("?")[0].lower()
    if path.endswith(".png"):
        return "png"
    if path.endswith(".webp"):
        return "webp"
    return "jpg"


class Command(BaseCommand):
    help = "Remove all watermarks (PropertyPro + NESTOVA) from scraped listing images"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Process only this many listings (useful for a test run)",
        )
        parser.add_argument(
            "--cloudinary-only",
            action="store_true",
            default=False,
            help=(
                "Skip re-download from PropertyPro CDN; always use the current "
                "Cloudinary image as the source.  Inpainting will remove NESTOVA too."
            ),
        )

    def handle(self, *args, **kwargs):
        limit          = kwargs["limit"]
        cloudinary_only = kwargs["cloudinary_only"]

        # Only process listings that already have a Cloudinary image
        qs = (
            ScrapedListing.objects
            .exclude(image_file="")
            .exclude(image_file__isnull=True)
            .order_by("id")
        )

        listings = list(qs[:limit] if limit else qs)
        total    = len(listings)

        if total == 0:
            self.stdout.write(self.style.WARNING("No listings with image_file found."))
            return

        self.stdout.write(
            f"\n{'='*64}\n"
            f"Removing watermarks from {total} listing image(s)...\n"
            f"Strategy: {'Cloudinary-only' if cloudinary_only else 'PropertyPro CDN first, then Cloudinary fallback'}\n"
            f"{'='*64}"
        )

        saved = failed = 0

        for idx, listing in enumerate(listings, 1):
            short_title = (listing.title or "Untitled")[:60]
            self.stdout.write(f"\n[{idx}/{total}] {short_title}")

            raw         = None
            source_used = None
            ext         = "jpg"

            # ── Strategy A: re-download from original PropertyPro CDN ──────
            if not cloudinary_only and listing.image_url:
                self.stdout.write(
                    f"  → Source A: {listing.image_url[:80]}"
                )
                raw = _download(listing.image_url)
                if raw:
                    source_used = "PropertyPro CDN"
                    ext         = _ext_from_url(listing.image_url)
                    self.stdout.write(
                        f"  ✓ Downloaded {len(raw) // 1024} KB"
                    )
                else:
                    self.stdout.write(
                        "  ✗ CDN URL unreachable — falling back to Cloudinary"
                    )

            # ── Strategy B: fallback to current Cloudinary image ─────────
            if raw is None:
                try:
                    cloudinary_url = listing.image_file.url
                    self.stdout.write(
                        f"  → Source B: {cloudinary_url[:80]}"
                    )
                    raw = _download(cloudinary_url)
                    if raw:
                        source_used = "Cloudinary"
                        ext         = _ext_from_url(cloudinary_url)
                        self.stdout.write(
                            f"  ✓ Downloaded {len(raw) // 1024} KB"
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING("  ✗ Cloudinary download also failed")
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"  ✗ Cloudinary URL error: {e}")
                    )

            if raw is None:
                self.stdout.write(
                    self.style.WARNING("  ✗ No source available — skipping")
                )
                failed += 1
                continue

            # ── Process: erase watermark(s), do NOT re-stamp ─────────────
            fmt_map = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
            fmt     = fmt_map.get(ext, "JPEG")

            try:
                clean_bytes = process_image_bytes(
                    raw,
                    fmt=fmt,
                    stamp_nestova=False,    # ← clean output — no watermark
                )
                self.stdout.write(
                    f"  ✓ Watermark erased (source: {source_used})"
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Processing error: {e}"))
                failed += 1
                continue

            # ── Save clean image back to Cloudinary ───────────────────────
            # Reuse the same filename so the Cloudinary public_id is preserved
            if listing.image_file and listing.image_file.name:
                fname = listing.image_file.name.split("/")[-1]
                if "." not in fname:
                    fname = f"{fname}.{ext}"
            else:
                h     = hashlib.md5((listing.image_url or str(listing.pk)).encode()).hexdigest()
                fname = f"clean_{h}.{ext}"

            try:
                listing.image_file.delete(save=False)   # remove old Cloudinary asset
                listing.image_file.save(fname, ContentFile(clean_bytes), save=True)
                saved += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Saved clean image → {fname}")
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Cloudinary save error: {e}"))
                failed += 1

        # ── Summary ───────────────────────────────────────────────────────
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'='*64}\n"
                f"Finished.  {saved} images cleaned,  {failed} failed.\n"
                f"{'='*64}"
            )
        )