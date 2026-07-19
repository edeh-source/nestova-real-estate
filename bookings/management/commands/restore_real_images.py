"""
Management command: python manage.py restore_real_images

Reads the original Apify dataset, matches existing ScrapedListings by URL,
downloads the real PropertyPro image for each, strips the PropertyPro watermark,
stamps Nestova, then saves as image_file.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.base import ContentFile
from bookings.models import ScrapedListing
from bookings.tasks import download_image

try:
    from apify_client import ApifyClient
    HAS_APIFY = True
except ImportError:
    HAS_APIFY = False


class Command(BaseCommand):
    help = (
        'Re-fetch real apartment images from the Apify dataset, '
        'strip PropertyPro watermark and stamp Nestova.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dataset-id',
            default=getattr(settings, 'APIFY_DATASET_ID', ''),
            help='Apify dataset ID to pull images from',
        )

    def handle(self, *args, **kwargs):
        dataset_id = kwargs['dataset_id']

        if not HAS_APIFY:
            self.stderr.write("apify_client not installed.")
            return

        if not dataset_id:
            self.stderr.write("No dataset ID provided. Check APIFY_DATASET_ID in settings.")
            return

        self.stdout.write(f"Reading Apify dataset: {dataset_id}")
        client = ApifyClient(token=settings.APIFY_API_TOKEN)

        items = list(client.dataset(dataset_id).iterate_items())
        self.stdout.write(f"Found {len(items)} items in dataset.\n")

        saved = skipped = failed = 0

        for item in items:
            url   = item.get('url', '')
            img_url = item.get('image', '')

            if not url or not img_url:
                continue

            try:
                listing = ScrapedListing.objects.get(url=url)
            except ScrapedListing.DoesNotExist:
                continue

            # Download, strip PropertyPro watermark, stamp Nestova
            self.stdout.write(f"  Processing: {listing.title[:70]}")
            filename, content = download_image(img_url)

            if filename and content:
                # Clear old file reference and save new processed image
                listing.image_file.delete(save=False)
                listing.image_url = img_url   # keep original URL as backup reference
                listing.image_file.save(filename, content, save=True)
                saved += 1
                self.stdout.write(self.style.SUCCESS(f"    ✓ Saved: {filename}"))
            else:
                failed += 1
                self.stdout.write(self.style.WARNING(f"    ✗ Failed to download image"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {saved} images processed, {failed} failed, {skipped} skipped."
            )
        )
