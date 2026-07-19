"""
Management command: python manage.py backfill_images [--reprocess]

--reprocess   Also strip PropertyPro watermark from images already downloaded.
              Without this flag only listings missing image_file are processed.
"""

from django.core.management.base import BaseCommand
from bookings.models import ScrapedListing
from bookings.tasks import download_image
from bookings.image_processor import reprocess_local_image


class Command(BaseCommand):
    help = 'Download and store images for existing ScrapedListings (strips PropertyPro watermark, stamps Nestova)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reprocess',
            action='store_true',
            default=False,
            help='Also reprocess images that were already downloaded (re-run watermark removal)',
        )

    def handle(self, *args, **kwargs):
        reprocess = kwargs['reprocess']

        # ── 1. Download missing images (with watermark processing) ──────────
        qs_missing = ScrapedListing.objects.filter(
            image_file='',
            image_url__isnull=False
        ).exclude(image_url='')

        self.stdout.write(f"Backfilling {qs_missing.count()} listings missing local images...")

        success = failed = 0
        for listing in qs_missing:
            filename, content = download_image(listing.image_url)
            if filename and content:
                listing.image_file.save(filename, content, save=True)
                success += 1
                self.stdout.write(f"  ✓ {listing.title[:70]}")
            else:
                failed += 1
                self.stdout.write(f"  ✗ Failed: {listing.title[:70]}")

        self.stdout.write(
            self.style.SUCCESS(f"\nDownloaded: {success} saved, {failed} failed.")
        )

        # ── 2. Optionally reprocess already-downloaded images ────────────────
        if reprocess:
            qs_existing = ScrapedListing.objects.exclude(image_file='').exclude(image_file__isnull=True)
            self.stdout.write(f"\nReprocessing {qs_existing.count()} existing local images...")

            ok = err = 0
            for listing in qs_existing:
                try:
                    file_path = listing.image_file.path   # local filesystem path
                    if reprocess_local_image(file_path):
                        ok += 1
                        self.stdout.write(f"  ✓ {listing.title[:70]}")
                    else:
                        err += 1
                        self.stdout.write(f"  ✗ Failed: {listing.title[:70]}")
                except Exception as e:
                    err += 1
                    self.stdout.write(f"  ✗ Error ({listing.id}): {e}")

            self.stdout.write(
                self.style.SUCCESS(f"\nReprocessed: {ok} OK, {err} errors.")
            )