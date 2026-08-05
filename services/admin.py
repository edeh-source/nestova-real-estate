from django.contrib import admin
from .models import (
    InteriorDesignRequest,
    TourismInquiry,
    AcademyEnrollment,
    BrokerageInquiry,
    BusinessPartnershipInquiry,
)


# ==============================================================
#  INTERIOR DESIGN REQUEST
# ==============================================================

@admin.register(InteriorDesignRequest)
class InteriorDesignRequestAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone', 'service_type', 'budget_range', 'status', 'created_at']
    list_filter = ['status', 'service_type', 'budget_range', 'created_at']
    search_fields = ['full_name', 'email', 'phone', 'property_address', 'project_description']
    readonly_fields = ['created_at', 'updated_at', 'contacted_at', 'completed_at']

    fieldsets = (
        ('Client Information', {
            'fields': ('user', 'full_name', 'email', 'phone')
        }),
        ('Project Details', {
            'fields': ('service_type', 'property_address', 'property_size', 'budget_range')
        }),
        ('Design Preferences', {
            'fields': ('preferred_style', 'project_description', 'reference_images', 'special_requirements')
        }),
        ('Timeline', {
            'fields': ('preferred_start_date', 'project_deadline')
        }),
        ('Status & Tracking', {
            'fields': ('status', 'admin_notes', 'created_at', 'updated_at', 'contacted_at', 'completed_at')
        }),
    )

    actions = ['mark_as_contacted', 'mark_as_in_progress', 'mark_as_completed']

    def mark_as_contacted(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='contacted', contacted_at=timezone.now())
        self.message_user(request, f'{updated} request(s) marked as contacted.')
    mark_as_contacted.short_description = "Mark selected as contacted"

    def mark_as_in_progress(self, request, queryset):
        updated = queryset.update(status='in_progress')
        self.message_user(request, f'{updated} request(s) marked as in progress.')
    mark_as_in_progress.short_description = "Mark selected as in progress"

    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f'{updated} request(s) marked as completed.')
    mark_as_completed.short_description = "Mark selected as completed"


# ==============================================================
#  TOURISM INQUIRY
# ==============================================================

@admin.register(TourismInquiry)
class TourismInquiryAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone', 'inquiry_type', 'destination_preference', 'group_size', 'budget_range', 'status', 'created_at']
    list_filter = ['status', 'inquiry_type', 'destination_preference', 'group_size', 'budget_range', 'created_at']
    search_fields = ['full_name', 'email', 'phone', 'message', 'special_interests']
    readonly_fields = ['created_at', 'updated_at', 'contacted_at']

    fieldsets = (
        ('Contact Information', {
            'fields': ('user', 'full_name', 'email', 'phone')
        }),
        ('Trip Details', {
            'fields': ('inquiry_type', 'destination_preference', 'group_size', 'budget_range', 'preferred_travel_date', 'trip_duration')
        }),
        ('Preferences & Message', {
            'fields': ('special_interests', 'message')
        }),
        ('Status & Admin', {
            'fields': ('status', 'admin_notes', 'created_at', 'updated_at', 'contacted_at')
        }),
    )

    actions = ['mark_as_contacted', 'mark_as_package_sent', 'mark_as_booked']

    def mark_as_contacted(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='contacted', contacted_at=timezone.now())
        self.message_user(request, f'{updated} inquiry(s) marked as contacted.')
    mark_as_contacted.short_description = "Mark selected as contacted"

    def mark_as_package_sent(self, request, queryset):
        updated = queryset.update(status='package_sent')
        self.message_user(request, f'{updated} inquiry(s) marked as package sent.')
    mark_as_package_sent.short_description = "Mark selected as package sent"

    def mark_as_booked(self, request, queryset):
        updated = queryset.update(status='booked')
        self.message_user(request, f'{updated} inquiry(s) marked as booked/confirmed.')
    mark_as_booked.short_description = "Mark selected as booked"


# ==============================================================
#  ACADEMY ENROLLMENT
# ==============================================================

@admin.register(AcademyEnrollment)
class AcademyEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone', 'program', 'experience_level', 'preferred_format', 'status', 'created_at']
    list_filter = ['status', 'program', 'experience_level', 'preferred_format', 'created_at']
    search_fields = ['full_name', 'email', 'phone', 'occupation', 'location', 'goals']
    readonly_fields = ['created_at', 'updated_at', 'accepted_at', 'completed_at']

    fieldsets = (
        ('Personal Information', {
            'fields': ('user', 'full_name', 'email', 'phone', 'age', 'occupation', 'location')
        }),
        ('Program Details', {
            'fields': ('program', 'experience_level', 'preferred_format')
        }),
        ('Goals & Background', {
            'fields': ('goals', 'how_heard', 'referral_name')
        }),
        ('Status & Admin', {
            'fields': ('status', 'admin_notes', 'created_at', 'updated_at', 'accepted_at', 'completed_at')
        }),
    )

    actions = ['mark_as_accepted', 'mark_as_enrolled', 'mark_as_completed']

    def mark_as_accepted(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='accepted', accepted_at=timezone.now())
        self.message_user(request, f'{updated} enrollment(s) accepted.')
    mark_as_accepted.short_description = "Mark selected as accepted"

    def mark_as_enrolled(self, request, queryset):
        updated = queryset.update(status='enrolled')
        self.message_user(request, f'{updated} enrollment(s) set to active.')
    mark_as_enrolled.short_description = "Mark selected as enrolled/active"

    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f'{updated} enrollment(s) marked as completed.')
    mark_as_completed.short_description = "Mark selected as completed"


# ==============================================================
#  BROKERAGE INQUIRY
# ==============================================================

@admin.register(BrokerageInquiry)
class BrokerageInquiryAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone', 'service_requested', 'location', 'timeline', 'status', 'created_at']
    list_filter = ['status', 'service_requested', 'location', 'timeline', 'created_at']
    search_fields = ['full_name', 'email', 'phone', 'message', 'budget']
    readonly_fields = ['created_at', 'updated_at', 'contacted_at']

    fieldsets = (
        ('Contact Information', {
            'fields': ('user', 'full_name', 'email', 'phone')
        }),
        ('Service Details', {
            'fields': ('service_requested', 'location', 'timeline', 'budget', 'message')
        }),
        ('Status & Admin', {
            'fields': ('status', 'admin_notes', 'created_at', 'updated_at', 'contacted_at')
        }),
    )

    actions = ['mark_as_contacted', 'mark_as_in_progress', 'mark_as_completed']

    def mark_as_contacted(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='contacted', contacted_at=timezone.now())
        self.message_user(request, f'{updated} inquiry(s) marked as contacted.')
    mark_as_contacted.short_description = "Mark selected as contacted"

    def mark_as_in_progress(self, request, queryset):
        updated = queryset.update(status='in_progress')
        self.message_user(request, f'{updated} inquiry(s) set to in progress.')
    mark_as_in_progress.short_description = "Mark selected as in progress"

    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='completed', contacted_at=timezone.now())
        self.message_user(request, f'{updated} inquiry(s) marked as completed.')
    mark_as_completed.short_description = "Mark selected as completed"


# ==============================================================
#  BUSINESS PARTNERSHIP INQUIRY
# ==============================================================

@admin.register(BusinessPartnershipInquiry)
class BusinessPartnershipInquiryAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'business_name', 'email', 'phone', 'partnership_type', 'business_size', 'status', 'created_at']
    list_filter = ['status', 'partnership_type', 'business_size', 'created_at']
    search_fields = ['full_name', 'business_name', 'email', 'phone', 'location', 'message']
    readonly_fields = ['created_at', 'updated_at', 'contacted_at']

    fieldsets = (
        ('Contact Information', {
            'fields': ('full_name', 'business_name', 'email', 'phone', 'location', 'website')
        }),
        ('Partnership Details', {
            'fields': ('partnership_type', 'business_size', 'message')
        }),
        ('Status & Admin', {
            'fields': ('status', 'admin_notes', 'created_at', 'updated_at', 'contacted_at')
        }),
    )

    actions = ['mark_as_contacted', 'mark_as_negotiation', 'mark_as_active']

    def mark_as_contacted(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='contacted', contacted_at=timezone.now())
        self.message_user(request, f'{updated} inquiry(s) marked as contacted.')
    mark_as_contacted.short_description = "Mark selected as contacted"

    def mark_as_negotiation(self, request, queryset):
        updated = queryset.update(status='negotiation')
        self.message_user(request, f'{updated} inquiry(s) moved to negotiation.')
    mark_as_negotiation.short_description = "Mark selected as in negotiation"

    def mark_as_active(self, request, queryset):
        updated = queryset.update(status='active_partner')
        self.message_user(request, f'{updated} inquiry(s) marked as active partner.')
    mark_as_active.short_description = "Mark selected as active partner"
