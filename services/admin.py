from django.contrib import admin
from .models import InteriorDesignRequest


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
