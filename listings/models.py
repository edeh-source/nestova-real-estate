from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


# ── Boost tier choices ────────────────────────────────────────────────────────
BOOST_TIER_CHOICES = [
    ('standard',     'Standard'),
    ('premium',      'Premium (5× exposure)'),
    ('premium_gold', 'Premium Gold (10× exposure)'),
    ('sponsored',    'Sponsored (20× exposure)'),
]


class ListingPackage(models.Model):
    """
    Monthly subscription plan that mirrors PropertyPro.ng's structure.

    Each plan grants:
      - listing_limit            : max active properties allowed simultaneously
      - auto_boost_interval_days : system pushes ALL user listings to top every N days
      - manual_boosts_per_cycle  : credits to manually push a specific listing
      - premium_slots_per_cycle  : credits to upgrade a listing to Premium (5× rank)
      - premium_gold_slots_per_cycle : credits for Premium Gold (10× rank)
      - sponsored_slots_per_cycle    : credits for Sponsored placement (20× rank)

    ┌──────────────┬────────────┬────────────────┬──────────────────────┐
    │ Plan         │ Price/mo   │ PropertyPro    │ Nestova (−2 days)    │
    ├──────────────┼────────────┼────────────────┼──────────────────────┤
    │ Freemium     │ Free       │ —              │ —                    │
    │ Manager      │ ₦15,900    │ Every 15 days  │ Every 13 days        │
    │ Executive    │ ₦27,900    │ Every 9 days   │ Every 7 days         │
    │ Gold         │ ₦119,900   │ Every 3 days   │ Every 1 day          │
    │ Platinum     │ ₦169,900   │ Every 2 days   │ Every 1 day (floor)  │
    └──────────────┴────────────┴────────────────┴──────────────────────┘

    Prices are identical to PropertyPro. Nestova's edge is 2 more boost days
    per cycle across all tiers.
    """
    name          = models.CharField(max_length=50)
    slug          = models.SlugField(unique=True)
    description   = models.TextField(blank=True)
    price         = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    duration_days = models.PositiveIntegerField(
        default=30,
        help_text="Subscription cycle length in days (30 = monthly)"
    )

    # ── Listing capacity ──────────────────────────────────────────────────────
    listing_limit = models.PositiveIntegerField(
        default=5,
        help_text="Max active listings allowed simultaneously under this plan"
    )

    # ── Auto push-up ──────────────────────────────────────────────────────────
    auto_boost_interval_days = models.PositiveIntegerField(
        default=13,
        help_text=(
            "Auto push-up fires every N days. "
            "Nestova offers 2 days fewer than PropertyPro per tier — "
            "meaning more frequent boosts at the same price: "
            "Manager=13d, Executive=7d, Gold=1d, Platinum=1d "
            "(PropertyPro equivalents: 15d, 9d, 3d, 2d)"
        )
    )

    # ── Credits replenished each billing cycle ────────────────────────────────
    manual_boosts_per_cycle       = models.PositiveIntegerField(
        default=0, help_text="Manual push-up credits per billing cycle"
    )
    premium_slots_per_cycle       = models.PositiveIntegerField(
        default=0, help_text="Premium listing (5×) slot credits per cycle"
    )
    premium_gold_slots_per_cycle  = models.PositiveIntegerField(
        default=0, help_text="Premium Gold listing (10×) slot credits per cycle"
    )
    sponsored_slots_per_cycle     = models.PositiveIntegerField(
        default=0, help_text="Sponsored listing (20×) slot credits per cycle"
    )

    # ── Extras shown on pricing page ──────────────────────────────────────────
    area_specialist_spots      = models.PositiveIntegerField(default=0)
    social_media_ads_per_cycle = models.PositiveIntegerField(default=0)
    banner_ads                 = models.PositiveIntegerField(default=0)
    homepage_logo              = models.BooleanField(default=False)

    features   = models.JSONField(
        default=list, blank=True,
        help_text="Extra feature bullet points displayed on the pricing page"
    )
    is_active  = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Assign this plan automatically to new users (free tier)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # ── Deprecated / backward-compat ──────────────────────────────────────────
    slots_count = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Deprecated — use listing_limit instead"
    )

    class Meta:
        ordering = ['price']

    def __str__(self):
        return f"{self.name} — ₦{self.price:,.0f}/month ({self.listing_limit} listings)"

    @property
    def price_per_listing(self):
        if self.listing_limit > 0 and self.price > 0:
            return self.price / self.listing_limit
        return 0

    # Alias for templates that still reference price_per_slot
    @property
    def price_per_slot(self):
        return self.price_per_listing


class UserSubscription(models.Model):
    """
    Tracks an agent's current subscription plan, validity window,
    and all boost / premium credit balances.

    Key shift from the old model
    ────────────────────────────
    Old model: permanent slots bought once, never expire.
    New model: monthly subscription with auto-renewable credits.
               Listing capacity is tied to the active plan;
               boost credits reset every billing cycle.
    """
    user    = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscription'
    )
    package = models.ForeignKey(
        ListingPackage,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="Currently active plan"
    )

    # ── Subscription window ───────────────────────────────────────────────────
    start_date = models.DateTimeField(default=timezone.now)
    end_date   = models.DateTimeField(
        null=True, blank=True,
        help_text="When the current subscription expires (null = free tier)"
    )
    is_active  = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=False)

    # ── Boost credits (replenished each billing cycle) ────────────────────────
    manual_boosts_remaining      = models.PositiveIntegerField(default=0)
    premium_slots_remaining      = models.PositiveIntegerField(default=0)
    premium_gold_slots_remaining = models.PositiveIntegerField(default=0)
    sponsored_slots_remaining    = models.PositiveIntegerField(default=0)

    # ── Auto-boost scheduling ─────────────────────────────────────────────────
    last_auto_boost_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the last system auto-boost ran for this user"
    )
    next_auto_boost_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the next auto-boost should fire"
    )

    # ── Free-tier config ──────────────────────────────────────────────────────
    initial_free_slots = models.PositiveIntegerField(
        default=1,
        help_text="Free listing slots given on sign-up (admin-configurable)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Deprecated fields (kept so old migrations don't break) ───────────────
    total_slots = models.PositiveIntegerField(
        default=1,
        help_text="Deprecated — listing capacity now comes from the package"
    )
    used_slots = models.PositiveIntegerField(
        default=0,
        help_text="Deprecated — use active_listing_count property instead"
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Core capacity helpers
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def listing_limit(self) -> int:
        """Max active listings the user is allowed under their current plan."""
        if self.package:
            return self.package.listing_limit
        return self.initial_free_slots

    @property
    def active_listing_count(self) -> int:
        """Real-time count of properties the user currently has listed."""
        from property.models import Property
        return Property.objects.filter(listed_by=self.user).count()

    @property
    def remaining_listings(self) -> int:
        return max(0, self.listing_limit - self.active_listing_count)

    # Backward-compat aliases used in existing views / templates
    @property
    def remaining_slots(self) -> int:
        return self.remaining_listings

    @property
    def slots_usage_percentage(self) -> int:
        if self.listing_limit == 0:
            return 100
        return int((self.active_listing_count / self.listing_limit) * 100)

    def has_remaining_slots(self) -> bool:
        return self.remaining_listings > 0

    def has_remaining_listings(self) -> bool:
        return self.remaining_listings > 0

    def get_used_slots(self) -> int:
        """Backward-compat alias."""
        return self.active_listing_count

    # ─────────────────────────────────────────────────────────────────────────
    # Subscription validity
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def is_valid(self) -> bool:
        """True if the subscription is active and not expired."""
        if not self.is_active:
            return False
        if self.end_date and timezone.now() > self.end_date:
            return False
        return True

    @property
    def is_expired(self) -> bool:
        return not self.is_valid

    @property
    def remaining_days(self) -> int:
        if self.end_date:
            delta = self.end_date - timezone.now()
            return max(0, delta.days)
        return 9999  # free tier — no expiry

    # ─────────────────────────────────────────────────────────────────────────
    # Package activation & credit replenishment
    # ─────────────────────────────────────────────────────────────────────────

    def activate_package(self, package: 'ListingPackage') -> None:
        """
        Called after a successful payment is verified.
        Sets the new plan, replenishes all credits, and schedules the
        first auto-boost based on Nestova's -2 day interval.
        """
        now             = timezone.now()
        self.package    = package
        self.start_date = now
        self.end_date   = now + timedelta(days=package.duration_days)
        self.is_active  = True

        # Replenish boost credits for the new cycle
        self.manual_boosts_remaining      = package.manual_boosts_per_cycle
        self.premium_slots_remaining      = package.premium_slots_per_cycle
        self.premium_gold_slots_remaining = package.premium_gold_slots_per_cycle
        self.sponsored_slots_remaining    = package.sponsored_slots_per_cycle

        # Schedule first auto-boost using Nestova's interval (PropertyPro − 2 days)
        self.next_auto_boost_at = now + timedelta(days=package.auto_boost_interval_days)
        self.last_auto_boost_at = None  # reset so dashboard shows "not yet run"

        self.save()

    def replenish_monthly_credits(self) -> None:
        """
        Called when a subscription renews.
        Resets boost credits without touching the package reference.
        """
        if self.package:
            self.manual_boosts_remaining      = self.package.manual_boosts_per_cycle
            self.premium_slots_remaining      = self.package.premium_slots_per_cycle
            self.premium_gold_slots_remaining = self.package.premium_gold_slots_per_cycle
            self.sponsored_slots_remaining    = self.package.sponsored_slots_per_cycle
            self.save()

    # ─────────────────────────────────────────────────────────────────────────
    # Auto-boost
    # ─────────────────────────────────────────────────────────────────────────

    def needs_auto_boost(self) -> bool:
        """True when the next scheduled auto-boost is overdue."""
        if not self.package or not self.is_valid:
            return False
        if self.next_auto_boost_at is None:
            return True
        return timezone.now() >= self.next_auto_boost_at

    def perform_auto_boost(self) -> int:
        """
        Push ALL of the user's listings to the top of search results by
        refreshing their boosted_at timestamp.  Then schedule the next run.

        Returns the number of properties boosted.
        """
        from property.models import Property
        now   = timezone.now()
        count = Property.objects.filter(listed_by=self.user).update(boosted_at=now)

        self.last_auto_boost_at = now
        if self.package:
            self.next_auto_boost_at = now + timedelta(
                days=self.package.auto_boost_interval_days
            )
        self.save(update_fields=['last_auto_boost_at', 'next_auto_boost_at'])
        return count

    # ─────────────────────────────────────────────────────────────────────────
    # Manual boost (single property)
    # ─────────────────────────────────────────────────────────────────────────

    def use_manual_boost(self, property_obj) -> bool:
        """
        Spend one manual boost credit to push a specific property to the top.
        Returns True on success, False if no credits remain.
        """
        if self.manual_boosts_remaining <= 0:
            return False

        property_obj.boosted_at = timezone.now()
        property_obj.save(update_fields=['boosted_at'])

        self.manual_boosts_remaining -= 1
        self.save(update_fields=['manual_boosts_remaining'])
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Premium tier upgrades
    # ─────────────────────────────────────────────────────────────────────────

    def apply_premium_tier(self, property_obj, tier: str) -> bool:
        """
        Spend a premium-slot credit to upgrade a specific property's
        visibility tier (premium / premium_gold / sponsored).

        Tier ranking (search sort priority):
            sponsored    → top  (20× exposure)
            premium_gold → 2nd  (10× exposure)
            premium      → 3rd  (5× exposure)
            standard     → default

        Returns True on success, False if insufficient credits.
        """
        CREDIT_MAP = {
            'premium':      'premium_slots_remaining',
            'premium_gold': 'premium_gold_slots_remaining',
            'sponsored':    'sponsored_slots_remaining',
        }
        if tier not in CREDIT_MAP:
            return False

        credit_field = CREDIT_MAP[tier]
        remaining    = getattr(self, credit_field)
        if remaining <= 0:
            return False

        property_obj.boost_tier = tier
        property_obj.boosted_at = timezone.now()
        property_obj.save(update_fields=['boost_tier', 'boosted_at'])

        setattr(self, credit_field, remaining - 1)
        self.save(update_fields=[credit_field])
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Deprecated helpers (kept for backward compat)
    # ─────────────────────────────────────────────────────────────────────────

    def add_slots(self, count: int) -> None:
        """Deprecated — slot capacity now comes from the package."""
        self.total_slots += count
        self.save()

    def use_slot(self) -> bool:
        """Deprecated — tracking is now via property count, not manual increment."""
        return self.has_remaining_listings()

    def release_slot(self) -> None:
        """Deprecated — slot release is automatic (property count is live)."""
        pass

    def recalculate_used_slots(self) -> None:
        """Sync the deprecated used_slots field with actual property count."""
        self.used_slots = self.active_listing_count
        self.save(update_fields=['used_slots'])

    def __str__(self):
        plan = self.package.name if self.package else "Free"
        return (
            f"{self.user.username} — {plan} | "
            f"{self.active_listing_count}/{self.listing_limit} listings | "
            f"boosts: manual={self.manual_boosts_remaining}"
        )


class PaymentRecord(models.Model):
    """
    Audit trail for every Paystack transaction attempt.
    Prevents double-activation on duplicate verify callbacks.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed',  'Failed'),
    ]

    user              = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    package           = models.ForeignKey(
        ListingPackage,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    reference         = models.CharField(max_length=120, unique=True, db_index=True)
    amount            = models.DecimalField(max_digits=12, decimal_places=2)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    paystack_response = models.JSONField(default=dict, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} | {self.reference} | {self.status}"


class SavedProperty(models.Model):
    """User's saved / wishlisted properties."""
    user     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_properties'
    )
    property = models.ForeignKey(
        'property.Property',
        on_delete=models.CASCADE,
        related_name='saved_by'
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'property']
        ordering        = ['-saved_at']

    def __str__(self):
        return f"{self.user} saved {self.property.title}"


class Notification(models.Model):
    """Simple in-app notification."""
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    title      = models.CharField(max_length=200)
    message    = models.TextField()
    is_read    = models.BooleanField(default=False)
    link       = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification → {self.user}: {self.title}"