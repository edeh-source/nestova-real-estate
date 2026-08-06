"""
Management command: python manage.py process_watermarks

Re-processes ALL scraped listing images on Cloudinary by:
  1. Downloading the current image via Cloudinary SDK (handles auth automatically)
     with fallback to direct HTTP download
  2. Completely removing the PropertyPro watermark via seam-carving in image_processor.py
  3. Re-uploading the clean image to Cloudinary (overwriting the existing file)

Usage:
    python manage.py process_watermarks            # process all
    python manage.py process_watermarks --limit 5  # process first 5 only (test)
    python manage.py process_watermarks --verbose  # show full URLs and HTTP status codes
"""
import os
import io
import time
import hashlib
import requests
import cloudinary
import cloudinary.uploader
import cloudinary.api

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from bookings.models import ScrapedListing
from bookings.image_processor import process_image_bytes


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}


def _extract_public_id(url: str) -> str | None:
    """
    Extract the Cloudinary public_id from a Cloudinary URL.

    Example URL:
      https://res.cloudinary.com/dxmarjmnr/image/upload/v1/media/scraped/abc123.jpg
    Returns:
      media/scraped/abc123
    """
    try:
        # Strip query string
        url = url.split('?')[0]
        marker = '/image/upload/'
        idx = url.find(marker)
        if idx == -1:
            return None
        after = url[idx + len(marker):]
        # Strip version segment like "v1/" or "v1234567890/"
        parts = after.split('/')
        if parts and parts[0].startswith('v') and parts[0][1:].isdigit():
            parts = parts[1:]
        path = '/'.join(parts)
        # Strip file extension
        public_id, _ = os.path.splitext(path)
        return public_id
    except Exception:
        return None


def _download_via_sdk(public_id: str, verbose: bool = False) -> bytes | None:
    """Download image bytes using Cloudinary SDK (handles signed URLs automatically)."""
    try:
        # Generate a signed download URL valid for 60 seconds
        signed_url = cloudinary.utils.cloudinary_url(
            public_id,
            resource_type='image',
            type='upload',
            sign_url=True,
            attachment=False,
        )[0]
        if verbose:
            print(f"    SDK signed URL: {signed_url}")
        r = requests.get(signed_url, headers=HEADERS, timeout=30)
        if verbose:
            print(f"    SDK HTTP status: {r.status_code}")
        r.raise_for_status()
        return r.content
    except Exception as e:
        if verbose:
            print(f"    SDK download error: {e}")
        return None


def _download_direct(url: str, verbose: bool = False) -> bytes | None:
    """Plain HTTP download — works for public Cloudinary images."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if verbose:
            print(f"    Direct HTTP status: {r.status_code} | Content-Type: {r.headers.get('content-type')}")
        r.raise_for_status()
        return r.content
    except requests.HTTPError as e:
        if verbose:
            print(f"    Direct HTTP error: {e.response.status_code} {e.response.reason}")
        return None
    except Exception as e:
        if verbose:
            print(f"    Direct download error: {e}")
        return None


def _download(url: str, verbose: bool = False) -> bytes | None:
    """
    Try to download an image with two strategies:
      1. Cloudinary SDK signed URL (handles private/authenticated resources)
      2. Direct plain HTTP (works for public resources)
    """
    public_id = _extract_public_id(url)

    # Strategy 1: SDK signed URL (only for Cloudinary URLs)
    if public_id:
        if verbose:
            print(f"    Extracted public_id: {public_id}")
        raw = _download_via_sdk(public_id, verbose=verbose)
        if raw:
            return raw

    # Strategy 2: Direct HTTP
    raw = _download_direct(url, verbose=verbose)
    return raw


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
        parser.add_argument(
            '--verbose',
            action='store_true',
            default=False,
            help='Print full URLs and HTTP status codes for debugging',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.5,
            help='Seconds to wait between requests (default: 0.5) — avoids rate limiting',
        )

    def handle(self, *args, **kwargs):
        limit   = kwargs['limit']
        verbose = kwargs['verbose']
        delay   = kwargs['delay']

        # Listings already on Cloudinary
        qs_cloudinary = ScrapedListing.objects.exclude(
            image_file=''
        ).exclude(image_file__isnull=True)

        # Listings with only an external image_url (not yet downloaded)
        qs_url_only = ScrapedListing.objects.filter(
            image_file=''
        ).exclude(image_url='').exclude(image_url__isnull=True)

        listings = list(qs_cloudinary) + list(qs_url_only)

        if limit:
            listings = listings[:limit]

        total = len(listings)
        self.stdout.write(f"\nFound {total} listings to process.\n{'='*60}")

        if total == 0:
            self.stdout.write(
                "Nothing to process. No listings have image_file or image_url set."
            )
            return

        # Quick connectivity check — print Cloudinary config so you can verify it's loaded
        cfg = cloudinary.config()
        self.stdout.write(
            f"Cloudinary cloud: {cfg.cloud_name or '(not set — check CLOUDINARY_URL or settings)'}\n"
        )

        saved = failed = skipped = 0

        for i, listing in enumerate(listings, 1):
            title_short = (listing.title or 'Untitled')[:60]
            self.stdout.write(f"\n[{i}/{total}] {title_short}")

            # Determine source URL
            src_url = None
            if listing.image_file:
                try:
                    src_url = listing.image_file.url
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  ✗ Could not resolve image_file URL: {e}"))

            if not src_url:
                src_url = listing.image_url or None

            if not src_url:
                self.stdout.write(self.style.WARNING("  ✗ No image URL available — skipping"))
                skipped += 1
                continue

            display_url = src_url if verbose else (src_url[:80] + '...' if len(src_url) > 80 else src_url)
            self.stdout.write(f"  Downloading: {display_url}")

            raw = _download(src_url, verbose=verbose)

            if not raw:
                self.stdout.write(
                    self.style.ERROR(
                        "  ✗ Download failed. Possible causes:\n"
                        "     • Image is in a private/authenticated Cloudinary bucket\n"
                        "     • CLOUDINARY_URL env var not set or wrong cloud name\n"
                        "     • Image was deleted from Cloudinary\n"
                        "    Try running with --verbose for HTTP status codes."
                    )
                )
                failed += 1
                time.sleep(delay)
                continue

            self.stdout.write(f"  Downloaded {len(raw):,} bytes")

            # Detect format
            ext = _ext_from_url(src_url)
            fmt_map = {'jpg': 'JPEG', 'jpeg': 'JPEG', 'png': 'PNG', 'webp': 'WEBP'}
            fmt = fmt_map.get(ext, 'JPEG')

            # Remove watermark
            try:
                processed = process_image_bytes(raw, fmt=fmt, stamp_nestova=False)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Processing error: {e}"))
                failed += 1
                time.sleep(delay)
                continue

            # Determine filename
            if listing.image_file and listing.image_file.name:
                fname = listing.image_file.name.split('/')[-1]
                if '.' not in fname:
                    fname = f"{fname}.{ext}"
            else:
                h = hashlib.md5(src_url.encode()).hexdigest()
                fname = f"{h}.{ext}"

            # Truncate to stay within ImageField max_length=100
            name_base, ext_str = os.path.splitext(fname)
            if len(fname) > 85:
                fname = f"{name_base[:75]}{ext_str}"

            # Delete old file and re-upload
            try:
                if listing.image_file:
                    listing.image_file.delete(save=False)
                listing.image_file.save(fname, ContentFile(processed), save=True)
                saved += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ Cleaned & saved: {fname}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Save error: {e}"))
                failed += 1

            time.sleep(delay)  # Be polite to Cloudinary's API

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'='*60}\n"
                f"Done! {saved} cleaned, {failed} failed, {skipped} skipped (no URL).\n"
                f"{'='*60}"
            )
        )