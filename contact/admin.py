from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import ContactMessage, Newsletter, ContactInfo


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'status_badge', 'created_at', 'action_buttons']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message']
    readonly_fields = ['created_at', 'updated_at', 'ip_address', 'user_agent']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Message Information', {
            'fields': ('name', 'email', 'subject', 'message')
        }),
        ('Status & Management', {
            'fields': ('status', 'admin_notes', 'replied_at')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'new': '#ef4444',
            'read': '#3b82f6',
            'replied': '#10b981',
            'archived': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def action_buttons(self, obj):
        buttons = []
        
        if obj.status == 'new':
            mark_read_url = reverse('admin:contact_contactmessage_change', args=[obj.pk])
            buttons.append(
                f'<a class="button" href="{mark_read_url}" '
                f'style="background-color: #3b82f6; color: white; padding: 5px 10px; '
                f'border-radius: 4px; text-decoration: none; font-size: 12px;">Mark Read</a>'
            )
        
        if obj.status in ['new', 'read']:
            buttons.append(
                f'<a href="mailto:{obj.email}?subject=Re: {obj.subject}" '
                f'style="background-color: #10b981; color: white; padding: 5px 10px; '
                f'border-radius: 4px; text-decoration: none; font-size: 12px; '
                f'margin-left: 5px;">Reply</a>'
            )
        
        return mark_safe(' '.join(buttons)) if buttons else '-'
    action_buttons.short_description = 'Actions'
    
    actions = ['mark_as_read', 'mark_as_replied', 'mark_as_archived']
    
    def mark_as_read(self, request, queryset):
        updated = queryset.filter(status='new').update(status='read')
        self.message_user(request, f'{updated} message(s) marked as read.')
    mark_as_read.short_description = 'Mark selected as read'
    
    def mark_as_replied(self, request, queryset):
        from django.utils import timezone
        updated = queryset.exclude(status='replied').update(
            status='replied',
            replied_at=timezone.now()
        )
        self.message_user(request, f'{updated} message(s) marked as replied.')
    mark_as_replied.short_description = 'Mark selected as replied'
    
    def mark_as_archived(self, request, queryset):
        updated = queryset.update(status='archived')
        self.message_user(request, f'{updated} message(s) archived.')
    mark_as_archived.short_description = 'Archive selected messages'


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ['email', 'status_badge', 'subscribed_at', 'action_buttons']
    list_filter = ['is_active', 'subscribed_at']
    search_fields = ['email']
    readonly_fields = ['subscribed_at', 'unsubscribed_at', 'ip_address']
    date_hierarchy = 'subscribed_at'
    
    fieldsets = (
        ('Subscription Information', {
            'fields': ('email', 'is_active')
        }),
        ('Metadata', {
            'fields': ('subscribed_at', 'unsubscribed_at', 'ip_address'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        if obj.is_active:
            color = '#10b981'
            text = 'Active'
        else:
            color = '#ef4444'
            text = 'Unsubscribed'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            text
        )
    status_badge.short_description = 'Status'
    
    def action_buttons(self, obj):
        if obj.is_active:
            return format_html(
                '<a href="mailto:{}?subject=Newsletter" '
                'style="background-color: #3b82f6; color: white; padding: 5px 10px; '
                'border-radius: 4px; text-decoration: none; font-size: 12px;">Send Email</a>',
                obj.email
            )
        return '-'
    action_buttons.short_description = 'Actions'
    
    actions = ['export_emails', 'unsubscribe_selected']
    
    def export_emails(self, request, queryset):
        emails = list(queryset.filter(is_active=True).values_list('email', flat=True))
        emails_str = ', '.join(emails)
        self.message_user(request, f'Emails: {emails_str}')
    export_emails.short_description = 'Export selected emails'
    
    def unsubscribe_selected(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(is_active=True).update(
            is_active=False,
            unsubscribed_at=timezone.now()
        )
        self.message_user(request, f'{updated} subscription(s) cancelled.')
    unsubscribe_selected.short_description = 'Unsubscribe selected'


@admin.register(ContactInfo)
class ContactInfoAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'email', 'phone', 'is_active', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['company_name', 'email', 'phone']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Company Information', {
            'fields': ('company_name', 'tagline', 'description', 'is_active')
        }),
        ('Address', {
            'fields': (
                'address_line1', 'address_line2', 'city', 
                'state', 'postal_code', 'country'
            )
        }),
        ('Contact Details', {
            'fields': ('phone', 'email', 'support_email')
        }),
        ('Business Hours', {
            'fields': ('weekday_hours', 'weekend_hours')
        }),
        ('Map & Location', {
            'fields': ('google_maps_embed_url', 'latitude', 'longitude')
        }),
        ('Social Media', {
            'fields': (
                'facebook_url', 'twitter_url', 'linkedin_url',
                'youtube_url', 'github_url', 'instagram_url'
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one active contact info
        if ContactInfo.objects.filter(is_active=True).exists():
            return False
        return super().has_add_permission(request)
    
    def save_model(self, request, obj, form, change):
        if obj.is_active:
            # Deactivate all other contact info when this one is set to active
            ContactInfo.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)