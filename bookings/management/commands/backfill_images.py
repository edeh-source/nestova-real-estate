from django.core.management.base import BaseCommand
from bookings.models import ScrapedListing
from bookings.tasks import download_image


class Command(BaseCommand):
    help = 'Download and store images for existing ScrapedListings'

    def handle(self, *args, **kwargs):
        qs = ScrapedListing.objects.filter(
            image_file='',
            image_url__isnull=False
        ).exclude(image_url='')

        self.stdout.write(f"Backfilling {qs.count()} listings...")

        success = 0
        failed = 0

        for listing in qs:
            filename, content = download_image(listing.image_url)
            if filename and content:
                listing.image_file.save(filename, content, save=True)
                success += 1
                self.stdout.write(f"  ✓ {listing.title[:60]}")
            else:
                failed += 1
                self.stdout.write(f"  ✗ Failed: {listing.title[:60]}")

        self.stdout.write(self.style.SUCCESS(f"\nDone. {success} saved, {failed} failed."))