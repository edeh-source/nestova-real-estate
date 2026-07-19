"""
Management command: python manage.py process_watermarks

For all ScrapedListings where image_url is NOT empty:
  1. Download the real image from PropertyPro CDN
  2. Strip PropertyPro watermark using OpenCV inpainting
  3. Stamp Nestova watermark in its place
  4. Save to Django storage (local filesystem in dev, Cloudinary in production)

Safe to run multiple times - skips listings that already have image_file set
unless --force flag is used.

Usage:
    python manage.py process_watermarks            # process only missing
    python manage.py process_watermarks --force    # reprocess all
    python manage.py process_watermarks --limit 10 # process first 10
"""

from django.core.management.base import BaseCommand
from bookings.models import ScrapedListing
from bookings.tasks import download_image


class Command(BaseCommand):
    help = 'Download PropertyPro images, remove their watermark, stamp Nestova'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            default=False,
            help='Re-process listings that already have image_file (overwrite)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Only process this many listings (useful for testing)',
        )

    def handle(self, *args, **kwargs):
        force = kwargs['force']
        limit = kwargs['limit']

        qs = ScrapedListing.objects.exclude(image_url='').exclude(image_url__isnull=True)

        if not force:
            qs = qs.filter(image_file='')

        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(f"Found {total} listings to process.\n")

        if total == 0:
            self.stdout.write(
                "Nothing to do. All listings with image_url already have image_file set.\n"
                "Run with --force to reprocess, or check that image_url is populated in your database."
            )
            return

        saved = failed = 0

        for i, listing in enumerate(qs, 1):
            self.stdout.write(f"[{i}/{total}] {listing.title[:65]}")
            filename, content = download_image(listing.image_url)

            if filename and content:
                if listing.image_file:
                    listing.image_file.delete(save=False)
                listing.image_file.save(filename, content, save=True)
                saved += 1
                self.stdout.write(self.style.SUCCESS(f"         ✓ {filename}"))
            else:
                failed += 1
                self.stdout.write(self.style.WARNING(f"         ✗ Download failed"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'='*60}\n"
                f"Done. {saved} images processed successfully, {failed} failed.\n"
                f"All processed images have PropertyPro watermark removed\n"
                f"and Nestova branded watermark added.\n"
                f"{'='*60}"
            )
        )
