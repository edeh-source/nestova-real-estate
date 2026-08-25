from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from .models import (
    ListingPackage, UserSubscription,
    PaymentRecord, SavedProperty, Notification,
)


@admin.register(ListingPackage)
class ListingPackageAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'price_display', 'listing_limit', 'auto_boost_interval_days',
        'manual_boosts_per_cycle', 'premium_slots_per_cycle',
        'premium_gold_slots_per_cycle', 'sponsored_slots_per_cycle',
        'is_active', 'is_default',
    ]
    list_filter       = ['is_active', 'is_default']
    search_fields     = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering          = ['price']

    fieldsets = (
        ('Plan Info', {
            'fields': ('name', 'slug', 'description', 'price', 'duration_days', 'is_active', 'is_default')
        }),
        ('Listing Capacity', {
            'fields': ('listing_limit',)
        }),
        ('Auto Push-Up (fires automatically every N days)', {
            'description': (
                'Nestova gives 2 fewer days than PropertyPro per tier — '
                'meaning more frequent boosts at the same price. '
                'Recommended values: Manager=13, Executive=7, Gold=1, Platinum=1'
            ),
            'fields': ('auto_boost_interval_days',)
        }),
        ('Credits per Billing Cycle', {
            'fields': (
                'manual_boosts_per_cycle',
                'premium_slots_per_cycle',
                'premium_gold_slots_per_cycle',
                'sponsored_slots_per_cycle',
            )
        }),
        ('Extras', {
            'fields': (
                'area_specialist_spots',
                'social_media_ads_per_cycle',
                'banner_ads',
                'homepage_logo',
                'features',
            )
        }),
        ('Deprecated / Backward Compat', {
            'fields': ('slots_count',),
            'classes': ('collapse',),
        }),
    )

    def price_display(self, obj):
        return f"₦{obj.price:,.0f}/mo"
    price_display.short_description = "Price"


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'package', 'listing_usage', 'boost_credits',
        'subscription_status', 'next_auto_boost_at',
    ]
    list_filter   = ['is_active', 'package']
    search_fields = ['user__email', 'user__username', 'user__first_name']
    readonly_fields = [
        'created_at', 'updated_at',
        'listing_usage', 'boost_credits', 'subscription_status',
        'active_listing_count_display',
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Plan', {
            'fields': ('package', 'start_date', 'end_date', 'is_active', 'auto_renew')
        }),
        ('Listing Usage (live)', {
            'fields': ('active_listing_count_display', 'initial_free_slots')
        }),
        ('Boost Credits (current cycle)', {
            'fields': (
                'manual_boosts_remaining',
                'premium_slots_remaining',
                'premium_gold_slots_remaining',
                'sponsored_slots_remaining',
            )
        }),
        ('Auto-Boost Schedule', {
            'fields': ('last_auto_boost_at', 'next_auto_boost_at')
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at')
        }),
        ('Deprecated Fields', {
            'fields': ('total_slots', 'used_slots'),
            'classes': ('collapse',),
        }),
    )

    actions = [
        'fire_auto_boost_now',
        'replenish_cycle_credits',
        'add_5_manual_boosts',
        'add_10_listing_slots',
        'mark_subscriptions_expired',
    ]

    # ── Display helpers ───────────────────────────────────────────────────────

    def listing_usage(self, obj):
        used  = obj.active_listing_count
        total = obj.listing_limit
        pct   = obj.slots_usage_percentage
        color = '#e74c3c' if pct >= 100 else ('#e67e22' if pct >= 80 else '#27ae60')
        return format_html(
            '<span style="color:{}">{}/{} ({}%)</span>',
            color, used, total, pct
        )
    listing_usage.short_description = "Listings used"

    def active_listing_count_display(self, obj):
        return obj.active_listing_count
    active_listing_count_display.short_description = "Active listings (live count)"

    def boost_credits(self, obj):
        return (
            f"Manual: {obj.manual_boosts_remaining} | "
            f"Prem: {obj.premium_slots_remaining} | "
            f"Gold: {obj.premium_gold_slots_remaining} | "
            f"Spon: {obj.sponsored_slots_remaining}"
        )
    boost_credits.short_description = "Boost credits"

    def subscription_status(self, obj):
        if not obj.package:
            return format_html('<span style="color:#999">Free tier</span>')
        if obj.is_expired:
            return format_html('<span style="color:#e74c3c">Expired</span>')
        color = '#27ae60' if obj.remaining_days > 7 else '#e67e22'
        return format_html(
            '<span style="color:{}">{} days left</span>', color, obj.remaining_days
        )
    subscription_status.short_description = "Status"

    # ── Admin actions ─────────────────────────────────────────────────────────

    @admin.action(description='🚀 Fire auto-boost now for selected users')
    def fire_auto_boost_now(self, request, queryset):
        total = 0
        for sub in queryset:
            total += sub.perform_auto_boost()
        self.message_user(
            request,
            f"Auto-boost fired: {total} properties boosted across {queryset.count()} users."
        )

    @admin.action(description='🔄 Replenish current-cycle credits')
    def replenish_cycle_credits(self, request, queryset):
        for sub in queryset:
            sub.replenish_monthly_credits()
        self.message_user(request, f"Credits replenished for {queryset.count()} users.")

    @admin.action(description='➕ Add 5 manual boost credits')
    def add_5_manual_boosts(self, request, queryset):
        for sub in queryset:
            sub.manual_boosts_remaining += 5
            sub.save(update_fields=['manual_boosts_remaining'])
        self.message_user(request, f"Added 5 manual boosts to {queryset.count()} users.")

    @admin.action(description='➕ Add 10 listing slots (to initial_free_slots)')
    def add_10_listing_slots(self, request, queryset):
        for sub in queryset:
            sub.initial_free_slots += 10
            sub.save(update_fields=['initial_free_slots'])
        self.message_user(request, f"Added 10 free slots to {queryset.count()} users.")

    @admin.action(description='⛔ Mark subscriptions as expired')
    def mark_subscriptions_expired(self, request, queryset):
        queryset.update(end_date=timezone.now(), is_active=False)
        self.message_user(request, f"Marked {queryset.count()} subscriptions as expired.")


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display    = ['user', 'package', 'amount_display', 'status', 'reference', 'created_at']
    list_filter     = ['status', 'package']
    search_fields   = ['user__email', 'reference']
    readonly_fields = ['reference', 'paystack_response', 'created_at', 'updated_at']
    ordering        = ['-created_at']

    def amount_display(self, obj):
        return f"₦{obj.amount:,.0f}"
    amount_display.short_description = "Amount"


@admin.register(SavedProperty)
class SavedPropertyAdmin(admin.ModelAdmin):
    list_display  = ['user', 'property', 'saved_at']
    list_filter   = ['saved_at']
    search_fields = ['user__username', 'property__title']
    date_hierarchy = 'saved_at'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ['user', 'title', 'is_read', 'created_at']
    list_filter   = ['is_read', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    date_hierarchy = 'created_at'
    actions = ['mark_as_read', 'mark_as_unread']

    @admin.action(description='Mark selected as read')
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, f"Marked {queryset.count()} notifications as read.")

    @admin.action(description='Mark selected as unread')
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
        self.message_user(request, f"Marked {queryset.count()} notifications as unread.")