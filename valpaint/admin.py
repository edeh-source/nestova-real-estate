from django.contrib import admin
from .models import Finish, ProductCategory, ValpaintProduct, ValpaintEnquiry


@admin.register(Finish)
class FinishAdmin(admin.ModelAdmin):
    list_display  = ('name', 'slug', 'icon', 'sort_order')
    list_editable = ('sort_order',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display  = ('name', 'use_type', 'slug', 'sort_order')
    list_editable = ('sort_order',)
    list_filter   = ('use_type',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(ValpaintProduct)
class ValpaintProductAdmin(admin.ModelAdmin):
    list_display   = ('name', 'category', 'is_featured', 'is_active',
                      'in_stock', 'price_ngn', 'updated_at')
    list_editable  = ('is_featured', 'is_active', 'in_stock')
    list_filter    = ('category', 'finishes', 'is_featured', 'is_active', 'in_stock')
    search_fields  = ('name', 'sku', 'short_desc')
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ('finishes',)
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Identity', {
            'fields': ('name', 'slug', 'sku', 'category', 'finishes')
        }),
        ('Content', {
            'fields': ('short_desc', 'description', 'applications')
        }),
        ('Media', {
            'fields': ('image', 'image_alt')
        }),
        ('Pricing', {
            'fields': ('price_ngn', 'price_label')
        }),
        ('Status & SEO', {
            'fields': ('is_featured', 'is_active', 'in_stock',
                       'meta_title', 'meta_description', 'valpaint_url')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ValpaintEnquiry)
class ValpaintEnquiryAdmin(admin.ModelAdmin):
    list_display  = ('full_name', 'email', 'phone', 'product',
                     'location', 'status', 'created_at')
    list_editable = ('status',)
    list_filter   = ('status', 'created_at')
    search_fields = ('full_name', 'email', 'phone', 'message')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'