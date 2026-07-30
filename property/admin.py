# admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    State, City, PropertyType, PropertyStatus, Property,
    PropertyImage, PropertyAmenity, PropertyAmenityLink,
    Developer,
)

# ── Developer ────────────────────────────────────────────────────────────

class DeveloperPropertyInline(admin.TabularInline):
    model = Property
    fk_name = 'developer'
    extra = 0
    fields = ['title', 'status', 'price', 'is_active']
    readonly_fields = ['title', 'status', 'price']
    show_change_link = True
    verbose_name = "Linked Property"
    verbose_name_plural = "Linked Properties"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Developer)
class DeveloperAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'headquarters', 'founded_year', 'property_count_display',
        'is_featured', 'is_active', 'created_at'
    ]
    list_filter = ['is_featured', 'is_active', 'created_at']
    search_fields = ['name', 'tagline', 'headquarters', 'email']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at', 'logo_preview', 'banner_preview', 'founder_preview']

    fieldsets = (
        ('Identity', {
            'fields': ('name', 'slug', 'tagline', 'description')
        }),
        ('Media', {
            'fields': ('logo', 'logo_preview', 'banner_image', 'banner_preview', 'founder_image', 'founder_preview')
        }),
        ('Contact & Location', {
            'fields': ('headquarters', 'email', 'phone', 'website')
        }),
        ('Social Media', {
            'fields': ('facebook_page', 'instagram_page', 'linkedin_page', 'x_page'),
            'classes': ('collapse',)
        }),
        ('Stats', {
            'fields': ('founded_year', 'total_units_delivered')
        }),
        ('Visibility', {
            'fields': ('is_featured', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [DeveloperPropertyInline]

    def property_count_display(self, obj):
        count = obj.property_count
        return format_html(
            '<span style="font-weight:bold;color:#2e7d32">{}</span>', count
        )
    property_count_display.short_description = 'Active Properties'

    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" style="max-height:80px;border-radius:6px;" />', obj.logo.url
            )
        return "No logo uploaded"
    logo_preview.short_description = 'Logo Preview'

    def banner_preview(self, obj):
        if obj.banner_image:
            return format_html(
                '<img src="{}" style="max-height:120px;border-radius:6px;" />', obj.banner_image.url
            )
        return "No banner uploaded"
    banner_preview.short_description = 'Banner Preview'

    def founder_preview(self, obj):
        if obj.founder_image:
            return format_html(
                '<img src="{}" style="max-height:100px;border-radius:50%;border:2px solid #C9A84C;" />', obj.founder_image.url
            )
        return "No image uploaded"
    founder_preview.short_description = 'Founder Preview'


# ─────────────────────────────────────────────────────────────────────────────

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'city_count']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    
    def city_count(self, obj):
        return obj.cities.count()
    city_count.short_description = 'Cities'


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name', 'state', 'is_active', 'property_count']
    list_filter = ['state', 'is_active']
    search_fields = ['name', 'state__name']
    
    def property_count(self, obj):
        return obj.properties.count()
    property_count.short_description = 'Properties'


@admin.register(PropertyType)
class PropertyTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']


@admin.register(PropertyStatus)
class PropertyStatusAdmin(admin.ModelAdmin):
    list_display = ['name']


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ['image', 'caption', 'is_primary', 'order']


class PropertyAmenityLinkInline(admin.TabularInline):
    model = PropertyAmenityLink
    extra = 1


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'developer', 'state', 'city', 'property_type', 'status',
        'price', 'bedrooms', 'bathrooms', 'is_featured',
        'views_count', 'created_at'
    ]
    list_filter = [
        'developer', 'property_type', 'status', 'state', 'is_featured',
        'is_premium', 'is_hot', 'created_at'
    ]
    search_fields = ['title', 'description', 'address', 'city__name', 'state__name']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['views_count', 'created_at', 'updated_at', 'price_per_sqft']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'description', 'listed_by', 'agent', 'developer')
        }),
        ('Location', {
            'fields': ('state', 'city', 'address', 'zip_code')
        }),
        ('Property Details', {
            'fields': (
                'property_type', 'status', 'bedrooms', 'bathrooms', 
                'square_feet', 'lot_size', 'year_built', 'parking_spaces'
            )
        }),
        ('Pricing', {
            'fields': ('price', 'price_per_sqft')
        }),
        ('Features', {
            'fields': (
                'has_garage', 'has_pool', 'has_garden', 'has_security',
                'has_gym', 'has_balcony', 'is_furnished', 'has_ac',
                'has_heating', 'pet_friendly'
            )
        }),
        ('Media', {
            'fields': ('featured_image', 'video_url', 'virtual_tour_url')
        }),
        ('Badges & Visibility', {
            'fields': (
                'is_featured', 'is_premium', 'is_hot', 'is_new', 'is_exclusive'
            )
        }),
        ('Statistics', {
            'fields': ('views_count', 'saved_count', 'created_at', 'updated_at')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [PropertyImageInline, PropertyAmenityLinkInline]
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new property
            obj.listed_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ['property', 'caption', 'is_primary', 'order', 'uploaded_at']
    list_filter = ['is_primary', 'uploaded_at']
    search_fields = ['property__title', 'caption']


@admin.register(PropertyAmenity)
class PropertyAmenityAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'description']
    search_fields = ['name']




