from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from listings.models import ListingPackage, UserSubscription


class Command(BaseCommand):
    help = (
        "Populate and synchronize subscription listing packages to mirror PropertyPro.ng "
        "with Nestova's competitive advantage (2 days faster auto-boost interval across tiers)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean-legacy',
            action='store_true',
            help='Deactivate legacy/outdated packages that do not match the standard tiers and migrate existing subscriptions.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate the package synchronization without committing any database changes.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        clean_legacy = options.get('clean_legacy', False)

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Nestova Listing Packages Population ==="))
        self.stdout.write("Mirroring PropertyPro.ng tiers with Nestova's 2-day faster auto-boost advantage.\n")

        # ── PropertyPro Packages Configuration ────────────────────────────────
        # Comparison with PropertyPro:
        # - Freemium:  Free     | 5 listings     | No Auto-Boost | 0 Manual | 0 Prem   | 0 Gold | 0 Spon
        # - Manager:   NGN 15,900 | 120 listings   | Every 13d (PP: 15d) | 35 Manual | 20 Prem  | 0 Gold | 0 Spon
        # - Executive: NGN 27,900 | 300 listings   | Every 7d (PP: 9d)  | 65 Manual | 60 Prem  | 0 Gold | 0 Spon
        # - Gold:      NGN 119,900| 3,000 listings | Every 1d (PP: 3d)  | 300 Manual| 350 Prem | 40 Gold| 3 Spon
        # - Platinum:  NGN 169,900| 10,000 listings| Every 1d (PP: 2d)  | 500 Manual| 600 Prem | 80 Gold| 5 Spon + 1 Banner + 2 Social Ads
        packages_data = [
            {
                'name': 'Freemium',
                'slug': 'freemium',
                'description': 'Free starter tier for new real estate agents. List up to 5 properties at zero cost.',
                'price': Decimal('0.00'),
                'duration_days': 30,
                'listing_limit': 5,
                'auto_boost_interval_days': 30,  # Free plan has no automatic interval bumps
                'manual_boosts_per_cycle': 0,
                'premium_slots_per_cycle': 0,
                'premium_gold_slots_per_cycle': 0,
                'sponsored_slots_per_cycle': 0,
                'area_specialist_spots': 0,
                'social_media_ads_per_cycle': 0,
                'banner_ads': 0,
                'homepage_logo': False,
                'is_active': True,
                'is_default': True,
                'features': [
                    "5 Active Property Listings",
                    "Standard Search Placement",
                    "Direct WhatsApp & Phone Leads",
                    "Basic Dashboard Analytics",
                    "Email & SMS Notifications",
                ],
            },
            {
                'name': 'Manager',
                'slug': 'manager',
                'description': 'Ideal for independent agents and boutique realtors growing their active portfolio.',
                'price': Decimal('15900.00'),
                'duration_days': 30,
                'listing_limit': 120,
                'auto_boost_interval_days': 13,  # PropertyPro: 15 days -> Nestova: 13 days (-2 days)
                'manual_boosts_per_cycle': 35,
                'premium_slots_per_cycle': 20,
                'premium_gold_slots_per_cycle': 0,
                'sponsored_slots_per_cycle': 0,
                'area_specialist_spots': 0,
                'social_media_ads_per_cycle': 0,
                'banner_ads': 0,
                'homepage_logo': False,
                'is_active': True,
                'is_default': False,
                'features': [
                    "120 Active Property Listings",
                    "Auto Push-Up Every 13 Days (2 Days Faster Boost)",
                    "35 Manual Push-Up Credits / Cycle",
                    "20 Premium Listing Credits (5x Exposure)",
                    "Direct WhatsApp & Phone Client Leads",
                    "Verified Agent Profile Badge Eligibility",
                    "Standard Agent Support",
                ],
            },
            {
                'name': 'Executive',
                'slug': 'executive',
                'description': 'High-performing agents and growing agencies requiring frequent pushes and premium placement.',
                'price': Decimal('27900.00'),
                'duration_days': 30,
                'listing_limit': 300,
                'auto_boost_interval_days': 7,  # PropertyPro: 9 days -> Nestova: 7 days (-2 days)
                'manual_boosts_per_cycle': 65,
                'premium_slots_per_cycle': 60,
                'premium_gold_slots_per_cycle': 0,
                'sponsored_slots_per_cycle': 0,
                'area_specialist_spots': 1,
                'social_media_ads_per_cycle': 0,
                'banner_ads': 0,
                'homepage_logo': False,
                'is_active': True,
                'is_default': False,
                'features': [
                    "300 Active Property Listings",
                    "Auto Push-Up Every 7 Days (2 Days Faster Boost)",
                    "65 Manual Push-Up Credits / Cycle",
                    "60 Premium Listing Credits (5x Exposure)",
                    "1 Area Specialist Placement",
                    "Priority Search Results Ranking",
                    "Direct WhatsApp & Phone Client Leads",
                    "Priority Agent Support",
                ],
            },
            {
                'name': 'Gold',
                'slug': 'gold',
                'description': 'Top real estate firms and established brokerages with large property inventories.',
                'price': Decimal('119900.00'),
                'duration_days': 30,
                'listing_limit': 3000,
                'auto_boost_interval_days': 1,  # PropertyPro: 3 days -> Nestova: 1 day (Daily Boost, -2 days)
                'manual_boosts_per_cycle': 300,
                'premium_slots_per_cycle': 350,
                'premium_gold_slots_per_cycle': 40,
                'sponsored_slots_per_cycle': 3,
                'area_specialist_spots': 3,
                'social_media_ads_per_cycle': 0,
                'banner_ads': 0,
                'homepage_logo': True,
                'is_active': True,
                'is_default': False,
                'features': [
                    "3,000 Active Property Listings",
                    "Daily Auto Push-Up (Every 1 Day -- Top Freshness)",
                    "300 Manual Push-Up Credits / Cycle",
                    "350 Premium Listing Credits (5x Exposure)",
                    "40 Premium Gold Listing Credits (10x Exposure)",
                    "3 Sponsored Listing Placements (20x Exposure)",
                    "Agency Logo & Branding on Homepage",
                    "3 Area Specialist Spots",
                    "Dedicated Account Manager",
                ],
            },
            {
                'name': 'Platinum',
                'slug': 'platinum',
                'description': 'Enterprise solution for premier corporate agencies and developers seeking maximum market reach.',
                'price': Decimal('169900.00'),
                'duration_days': 30,
                'listing_limit': 10000,  # Unlimited listings capacity
                'auto_boost_interval_days': 1,  # PropertyPro: 2 days -> Nestova: 1 day (Daily Boost, -2 days)
                'manual_boosts_per_cycle': 500,
                'premium_slots_per_cycle': 600,
                'premium_gold_slots_per_cycle': 80,
                'sponsored_slots_per_cycle': 5,
                'area_specialist_spots': 5,
                'social_media_ads_per_cycle': 2,
                'banner_ads': 1,
                'homepage_logo': True,
                'is_active': True,
                'is_default': False,
                'features': [
                    "Unlimited Property Listings (10,000+ capacity)",
                    "Daily Auto Push-Up (Every 1 Day -- Maximum Freshness)",
                    "500 Manual Push-Up Credits / Cycle",
                    "600 Premium Listing Credits (5x Exposure)",
                    "80 Premium Gold Listing Credits (10x Exposure)",
                    "5 Sponsored Listing Placements (20x Exposure)",
                    "1 Premium Web Banner Ad Placement",
                    "2 Dedicated Social Media Ad Campaigns / Cycle",
                    "Agency Logo & Branding on Homepage",
                    "5 Area Specialist Spots",
                    "24/7 VIP Dedicated Account Manager",
                ],
            },
        ]

        # Legacy slug mapping if migrating existing packages
        legacy_slug_map = {
            'free-starter': 'freemium',
            'agent-pro': 'manager',
            'executive-pro': 'executive',
            'advanced-pro': 'gold',
        }

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            save_point = transaction.savepoint()

            for pkg_data in packages_data:
                slug = pkg_data['slug']
                
                package, created = ListingPackage.objects.get_or_create(
                    slug=slug,
                    defaults=pkg_data
                )

                if created:
                    created_count += 1
                    status_text = self.style.SUCCESS(f"[CREATED] {package.name}")
                else:
                    for key, val in pkg_data.items():
                        setattr(package, key, val)
                    package.save()
                    updated_count += 1
                    status_text = self.style.WARNING(f"[UPDATED] {package.name}")

                self.stdout.write(
                    f"{status_text} | NGN {package.price:,.0f} | "
                    f"Listings: {package.listing_limit} | "
                    f"Auto-Boost: Every {package.auto_boost_interval_days}d | "
                    f"Manual: {package.manual_boosts_per_cycle} | "
                    f"Prem: {package.premium_slots_per_cycle} | "
                    f"Gold: {package.premium_gold_slots_per_cycle} | "
                    f"Spon: {package.sponsored_slots_per_cycle}"
                )

            # Ensure only the Freemium plan is marked as default
            ListingPackage.objects.filter(is_default=True).exclude(slug='freemium').update(is_default=False)

            # Handle legacy packages cleanup / migration if requested
            if clean_legacy:
                self.stdout.write(self.style.MIGRATE_HEADING("\n--- Cleaning & Migrating Legacy Packages ---"))
                for old_slug, target_slug in legacy_slug_map.items():
                    old_pkg = ListingPackage.objects.filter(slug=old_slug).first()
                    target_pkg = ListingPackage.objects.filter(slug=target_slug).first()
                    if old_pkg and target_pkg:
                        # Reassign any user subscriptions
                        subs_count = UserSubscription.objects.filter(package=old_pkg).update(package=target_pkg)
                        self.stdout.write(
                            f"  Migrated {subs_count} subscription(s) from '{old_pkg.name}' ({old_slug}) to '{target_pkg.name}' ({target_slug})."
                        )
                        # Deactivate old package
                        old_pkg.is_active = False
                        old_pkg.save(update_fields=['is_active'])
                        self.stdout.write(self.style.NOTICE(f"  Deactivated legacy package: {old_pkg.name} ({old_slug})"))

            if dry_run:
                transaction.savepoint_rollback(save_point)
                self.stdout.write(self.style.NOTICE("\n[DRY RUN] All changes were rolled back. No database modifications saved."))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"\n[OK] Successfully synchronized {len(packages_data)} packages!"
                ))
                self.stdout.write(self.style.SUCCESS(f"  - Created: {created_count}"))
                self.stdout.write(self.style.SUCCESS(f"  - Updated: {updated_count}"))
                self.stdout.write(self.style.SUCCESS(
                    f"  - Active Packages: {ListingPackage.objects.filter(is_active=True).count()}"
                ))

        # ── Output Summary Table ──────────────────────────────────────────────
        self.stdout.write("\n" + "=" * 105)
        self.stdout.write(
            f"{'Plan Name':<12} | {'Price':<12} | {'Listings':<10} | {'PropertyPro Auto':<18} | {'Nestova Auto (-2d)':<20} | {'Manual':<8} | {'Premium':<8} | {'Gold':<6} | {'Spon':<6}"
        )
        self.stdout.write("=" * 105)
        
        comparison = [
            ("Freemium",  "Free",        "5",      "--",            "-- (No Boost)",        "0",   "0",   "0",  "0"),
            ("Manager",   "NGN 15,900",  "120",    "Every 15 days", "Every 13 days",       "35",  "20",  "0",  "0"),
            ("Executive", "NGN 27,900",  "300",    "Every 9 days",  "Every 7 days",        "65",  "60",  "0",  "0"),
            ("Gold",      "NGN 119,900", "3,000",  "Every 3 days",  "Every 1 day (Daily)", "300", "350", "40", "3"),
            ("Platinum",  "NGN 169,900", "Unlimited", "Every 2 days", "Every 1 day (Daily)", "500", "600", "80", "5"),
        ]
        for row in comparison:
            self.stdout.write(
                f"{row[0]:<12} | {row[1]:<12} | {row[2]:<10} | {row[3]:<18} | {row[4]:<20} | {row[5]:<8} | {row[6]:<8} | {row[7]:<6} | {row[8]:<6}"
            )
        self.stdout.write("=" * 105 + "\n")
