from django.contrib import admin
from .models import ListingPackage, UserSubscription, SavedProperty, Notification

@admin.register(ListingPackage)
class ListingPackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'slots_count', 'price', 'price_per_slot_display', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['price']
    
    fieldsets = (
        ('Package Information', {
            'fields': ('name', 'slug', 'description')
        }),
        ('Slot Configuration', {
            'fields': ('slots_count', 'price')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Deprecated Fields (Backward Compatibility)', {
            'fields': ('listing_limit', 'duration_days', 'is_default'),
            'classes': ('collapse',)
        }),
    )
    
    def price_per_slot_display(self, obj):
        """Display price per slot"""
        if obj.price_per_slot > 0:
            return f"₦{obj.price_per_slot:,.0f}"
        return "Free"
    price_per_slot_display.short_description = "Price/Slot"

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_slots', 'used_slots', 'remaining_slots_display', 'slots_percentage', 'package']
    list_filter = ['is_active', 'package']
    search_fields = ['user__email', 'user__username', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'updated_at', 'remaining_slots_display', 'slots_percentage']
    ordering = ['-created_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Slot Management', {
            'fields': ('total_slots', 'used_slots', 'initial_free_slots', 'remaining_slots_display', 'slots_percentage')
        }),
        ('Package Reference', {
            'fields': ('package',)
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
        ('Deprecated Fields', {
            'fields': ('start_date', 'end_date', 'auto_renew'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['recalculate_used_slots', 'add_5_slots', 'add_10_slots', 'reset_used_slots']
    
    def remaining_slots_display(self, obj):
        """Display remaining slots"""
        return f"{obj.remaining_slots} slots"
    remaining_slots_display.short_description = "Remaining"
    
    def slots_percentage(self, obj):
        """Display usage percentage"""
        return f"{obj.slots_usage_percentage}% used"
    slots_percentage.short_description = "Usage"
    
    @admin.action(description='Recalculate used slots from actual properties')
    def recalculate_used_slots(self, request, queryset):
        for sub in queryset:
            sub.recalculate_used_slots()
        self.message_user(request, f"Recalculated slots for {queryset.count()} users")
    
    @admin.action(description='Add 5 slots to selected users')
    def add_5_slots(self, request, queryset):
        for sub in queryset:
            sub.add_slots(5)
        self.message_user(request, f"Added 5 slots to {queryset.count()} users")
    
    @admin.action(description='Add 10 slots to selected users')
    def add_10_slots(self, request, queryset):
        for sub in queryset:
            sub.add_slots(10)
        self.message_user(request, f"Added 10 slots to {queryset.count()} users")
    
    @admin.action(description='Reset used slots to 0')
    def reset_used_slots(self, request, queryset):
        queryset.update(used_slots=0)
        self.message_user(request, f"Reset used slots for {queryset.count()} users")

@admin.register(SavedProperty)
class SavedPropertyAdmin(admin.ModelAdmin):
    list_display = ['user', 'property', 'saved_at']
    list_filter = ['saved_at']
    search_fields = ['user__username', 'property__title']
    date_hierarchy = 'saved_at'

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    date_hierarchy = 'created_at'
    actions = ['mark_as_read', 'mark_as_unread']
    
    @admin.action(description='Mark as read')
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, f"Marked {queryset.count()} notifications as read")
    
    @admin.action(description='Mark as unread')
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
        self.message_user(request, f"Marked {queryset.count()} notifications as unread")
