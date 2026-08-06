"""
Management command: python manage.py process_watermarks

Re-processes ALL scraped listing images on Cloudinary by:
  1. Downloading the current image — tries Cloudinary first, falls back to original image_url
  2. Completely removing the PropertyPro watermark via image_processor.py
  3. Re-uploading the clean image to Cloudinary (overwriting the existing file)

Usage:
    python manage.py process_watermarks            # process all
    python manage.py process_watermarks --limit 5  # process first 5 only (test)
    python manage.py process_watermarks --verbose  # show full URLs and HTTP status codes
    python manage.py process_watermarks --delay 1  # wait 1s between requests
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


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_public_id(url: str) -> str | None:
    """
    Extract the Cloudinary public_id from a Cloudinary URL.

    Example:
      https://res.cloudinary.com/dxmarjmnr/image/upload/v1/media/scraped/abc123.jpg
    Returns:
      media/scraped/abc123
    """
    try:
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
        return public_id or None
    except Exception:
        return None


def _download_via_sdk(public_id: str, verbose: bool = False) -> bytes | None:
    """Download image bytes using a Cloudinary SDK-signed URL (handles auth automatically)."""
    try:
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
    """Plain HTTP download — works for public URLs (Cloudinary public bucket or PropertyPro)."""
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

    # Strategy 1: SDK signed URL (Cloudinary URLs only)
    if public_id:
        if verbose:
            print(f"    Extracted public_id: {public_id}")
        raw = _download_via_sdk(public_id, verbose=verbose)
        if raw:
            return raw

    # Strategy 2: Direct HTTP fallback
    return _download_direct(url, verbose=verbose)


def _ext_from_url(url: str) -> str:
    """Detect extension from URL path."""
    path = url.split('?')[0].lower()
    if path.endswith('.png'):
        return 'png'
    if path.endswith('.webp'):
        return 'webp'
    if path.endswith('.jpg') or path.endswith('.jpeg'):
        return 'jpg'
    return 'jpg'  # safe default for extensionless Cloudinary names


def _ext_from_bytes(data: bytes) -> str:
    """
    Sniff the actual image format from magic bytes.
    More reliable than URL-based detection — Cloudinary stored names
    often lack a file extension entirely.
    """
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'webp'
    if data[:3] == b'\xff\xd8\xff':
        return 'jpg'
    return 'jpg'  # safe default


# ── Management Command ────────────────────────────────────────────────────────

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

        # Verify Cloudinary config is loaded
        cfg = cloudinary.config()
        self.stdout.write(
            f"Cloudinary cloud: {cfg.cloud_name or '(not set — check CLOUDINARY_URL or settings)'}\n"
        )

        saved = failed = skipped = 0

        for i, listing in enumerate(listings, 1):
            title_short = (listing.title or 'Untitled')[:60]
            self.stdout.write(f"\n[{i}/{total}] {title_short}")

            # ── Build a prioritised list of URLs to try ───────────────
            urls_to_try = []

            if listing.image_file:
                try:
                    cf_url = listing.image_file.url
                    urls_to_try.append(('cloudinary', cf_url))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  ⚠ Could not resolve image_file URL: {e}"))

            if listing.image_url:
                urls_to_try.append(('original', listing.image_url))

            if not urls_to_try:
                self.stdout.write(self.style.WARNING("  ✗ No image URL available — skipping"))
                skipped += 1
                continue

            # ── Try each source in order ──────────────────────────────
            raw         = None
            used_url    = None
            used_source = None

            for source, url in urls_to_try:
                display_url = url if verbose else (url[:80] + '...' if len(url) > 80 else url)
                self.stdout.write(f"  [{source}] Downloading: {display_url}")
                raw = _download(url, verbose=verbose)
                if raw:
                    used_url    = url
                    used_source = source
                    self.stdout.write(f"  Downloaded {len(raw):,} bytes from [{source}]")
                    break
                else:
                    self.stdout.write(self.style.WARNING(f"  ✗ [{source}] failed — trying next source..."))

            if not raw:
                self.stdout.write(
                    self.style.ERROR(
                        "  ✗ All sources failed. Possible causes:\n"
                        "     • File deleted from Cloudinary AND original URL is gone\n"
                        "     • Network/firewall blocking outbound requests\n"
                        "    Run with --verbose to see HTTP status codes."
                    )
                )
                failed += 1
                time.sleep(delay)
                continue

            # ── Detect format from magic bytes (not URL) ──────────────
            ext = _ext_from_bytes(raw)
            fmt_map = {'jpg': 'JPEG', 'jpeg': 'JPEG', 'png': 'PNG', 'webp': 'WEBP'}
            fmt = fmt_map.get(ext, 'JPEG')
            self.stdout.write(f"  Detected format: {fmt} (.{ext})")

            # ── Remove watermark ──────────────────────────────────────
            try:
                processed = process_image_bytes(raw, fmt=fmt, stamp_nestova=False)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Processing error: {e}"))
                failed += 1
                time.sleep(delay)
                continue

            # ── Determine output filename ─────────────────────────────
            if used_source == 'cloudinary' and listing.image_file and listing.image_file.name:
                fname = listing.image_file.name.split('/')[-1]
                # Cloudinary names sometimes lack an extension — always ensure one
                if '.' not in os.path.basename(fname):
                    fname = f"{fname}.{ext}"
            else:
                # Fell back to original URL, or image_file had no usable name
                h = hashlib.md5((used_url or '').encode()).hexdigest()
                fname = f"{h}.{ext}"
                # Clear the broken/stale image_file reference before saving fresh
                if listing.image_file:
                    try:
                        listing.image_file.delete(save=False)
                    except Exception:
                        pass

            # Truncate to stay within ImageField max_length=100
            name_base, ext_str = os.path.splitext(fname)
            if len(fname) > 85:
                fname = f"{name_base[:75]}{ext_str}"

            # ── Upload to Cloudinary ──────────────────────────────────
            try:
                if listing.image_file:
                    listing.image_file.delete(save=False)
                listing.image_file.save(fname, ContentFile(processed), save=True)
                saved += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ Cleaned & saved: {fname}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Save error: {e}"))
                failed += 1

            time.sleep(delay)

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'='*60}\n"
                f"Done! {saved} cleaned, {failed} failed, {skipped} skipped (no URL).\n"
                f"{'='*60}"
            )
        )