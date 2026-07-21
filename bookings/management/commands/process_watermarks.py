"""
Management command: python manage.py process_watermarks

Re-processes ALL scraped listing images on Cloudinary by:
  1. Downloading the current image (from image_file Cloudinary URL or image_url PropertyPro URL)
  2. Completely removing the PropertyPro watermark via seam-carving in image_processor.py
  3. Re-uploading the clean image to Cloudinary (overwriting the existing file)

Usage:
    python manage.py process_watermarks            # process all with image_file
    python manage.py process_watermarks --limit 5  # process first 5 only (test)
"""

import io
import requests
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from bookings.models import ScrapedListing
from bookings.image_processor import process_image_bytes


HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Nestova/1.0)'}


def _download(url: str) -> bytes | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception as e:
        return None


def _ext_from_url(url: str) -> str:
    url = url.split('?')[0].lower()
    if url.endswith('.png'):
        return 'png'
    if url.endswith('.webp'):
        return 'webp'
    return 'jpg'


class Command(BaseCommand):
    help = 'Remove PropertyPro watermarks from all scraped listing images on Cloudinary'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Only process this many listings (useful for testing)',
        )

    def handle(self, *args, **kwargs):
        limit = kwargs['limit']

        # Get all listings that have an image_file already uploaded to Cloudinary
        qs = ScrapedListing.objects.exclude(image_file='').exclude(image_file__isnull=True)

        # Also include listings that only have image_url (not yet downloaded)
        qs_url_only = ScrapedListing.objects.filter(
            image_file=''
        ).exclude(image_url='').exclude(image_url__isnull=True)

        listings = list(qs) + list(qs_url_only)

        if limit:
            listings = listings[:limit]

        total = len(listings)
        self.stdout.write(f"\nFound {total} listings to process.\n{'='*60}")

        if total == 0:
            self.stdout.write(
                "Nothing to process. No listings have image_file or image_url set."
            )
            return

        saved = failed = 0

        for i, listing in enumerate(listings, 1):
            title_short = (listing.title or 'Untitled')[:60]
            self.stdout.write(f"\n[{i}/{total}] {title_short}")

            # Determine source URL
            if listing.image_file:
                # Build the Cloudinary URL from the image_file field
                try:
                    src_url = listing.image_file.url
                except Exception:
                    src_url = None
            else:
                src_url = listing.image_url or None

            if not src_url:
                self.stdout.write(self.style.WARNING("  ✗ No image URL available"))
                failed += 1
                continue

            self.stdout.write(f"  Downloading: {src_url[:80]}...")
            raw = _download(src_url)

            if not raw:
                self.stdout.write(self.style.WARNING("  ✗ Download failed"))
                failed += 1
                continue

            # Detect format
            ext = _ext_from_url(src_url)
            fmt_map = {'jpg': 'JPEG', 'jpeg': 'JPEG', 'png': 'PNG', 'webp': 'WEBP'}
            fmt = fmt_map.get(ext, 'JPEG')

            # Remove PropertyPro watermark completely (no stamp added)
            try:
                processed = process_image_bytes(raw, fmt=fmt, stamp_nestova=False)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Processing error: {e}"))
                failed += 1
                continue

            # Determine filename
            if listing.image_file and listing.image_file.name:
                # Keep the same Cloudinary filename so it overwrites in place
                fname = listing.image_file.name.split('/')[-1]
                if '.' not in fname:
                    fname = f"{fname}.{ext}"
            else:
                import hashlib
                h = hashlib.md5(src_url.encode()).hexdigest()
                fname = f"{h}.{ext}"

            # Delete old Cloudinary file and re-upload with watermark
            try:
                if listing.image_file:
                    listing.image_file.delete(save=False)
                listing.image_file.save(fname, ContentFile(processed), save=True)
                saved += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ Cleaned & Saved: {fname}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Save error: {e}"))
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'='*60}\n"
                f"Done! {saved} images cleaned successfully, {failed} failed.\n"
                f"{'='*60}"
            )
        )
