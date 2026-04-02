from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Category, Product, ProductImage, ProductSpecification,
    Review, CustomerProfile, Cart, CartItem, Order, OrderItem,
    Wishlist, Newsletter
)


# ===========================
# Inline Admin Classes
# ===========================

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'alt_text', 'order']


class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 1
    fields = ['spec_name', 'spec_value', 'order']


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'product_name', 'product_sku', 'quantity', 'unit_price', 'total_price']
    can_delete = False


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'added_at']


# ===========================
# Model Admin Classes
# ===========================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'product_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'sku', 'category', 'product_type', 'price_display',
        'stock_status', 'is_featured', 'is_bestseller', 'created_at'
    ]
    list_filter = [
        'product_type', 'category', 'is_available', 'is_featured',
        'is_bestseller', 'connectivity', 'created_at'
    ]
    search_fields = ['name', 'sku', 'brand', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['id', 'views_count', 'created_at', 'updated_at', 'average_rating']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'slug', 'category', 'product_type', 'sku')
        }),
        ('Description', {
            'fields': ('short_description', 'description', 'features')
        }),
        ('Pricing', {
            'fields': ('price', 'discount_price')
        }),
        ('Technical Specifications', {
            'fields': ('brand', 'model_number', 'connectivity', 'power_source', 'warranty_period')
        }),
        ('Inventory', {
            'fields': ('stock_quantity', 'is_available', 'low_stock_threshold')
        }),
        ('Media', {
            'fields': ('main_image',)
        }),
        ('Marketing', {
            'fields': ('is_featured', 'is_bestseller')
        }),
        ('Statistics', {
            'fields': ('views_count', 'average_rating', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [ProductImageInline, ProductSpecificationInline]
    
    def price_display(self, obj):
        if obj.discount_price:
            return format_html(
                '<span style="text-decoration: line-through;">₦{}</span> <span style="color: red;">₦{}</span>',
                obj.price, obj.discount_price
            )
        return f'₦{obj.price}'
    price_display.short_description = 'Price'
    
    def stock_status(self, obj):
        if not obj.is_available:
            return format_html('<span style="color: red;">Unavailable</span>')
        elif obj.stock_quantity == 0:
            return format_html('<span style="color: red;">Out of Stock</span>')
        elif obj.is_low_stock():
            return format_html('<span style="color: orange;">Low Stock ({})</span>', obj.stock_quantity)
        else:
            return format_html('<span style="color: green;">In Stock ({})</span>', obj.stock_quantity)
    stock_status.short_description = 'Stock'
    
    def average_rating(self, obj):
        rating = obj.get_average_rating()
        if rating > 0:
            return f'{rating} / 5.0'
        return 'No ratings'
    average_rating.short_description = 'Rating'


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'image', 'order', 'created_at']
    list_filter = ['created_at']
    search_fields = ['product__name', 'alt_text']


@admin.register(ProductSpecification)
class ProductSpecificationAdmin(admin.ModelAdmin):
    list_display = ['product', 'spec_name', 'spec_value', 'order']
    list_filter = ['product']
    search_fields = ['product__name', 'spec_name', 'spec_value']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'user', 'rating', 'title', 'is_approved',
        'is_verified_purchase', 'created_at'
    ]
    list_filter = ['is_approved', 'is_verified_purchase', 'rating', 'created_at']
    search_fields = ['product__name', 'user__username', 'title', 'comment']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['approve_reviews', 'disapprove_reviews']
    
    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} review(s) approved.')
    approve_reviews.short_description = 'Approve selected reviews'
    
    def disapprove_reviews(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} review(s) disapproved.')
    disapprove_reviews.short_description = 'Disapprove selected reviews'


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'city', 'state', 'country', 'created_at']
    list_filter = ['country', 'state', 'created_at']
    search_fields = ['user__username', 'user__email', 'phone', 'city']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_display', 'item_count', 'total_price', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username', 'session_key']
    readonly_fields = ['id', 'created_at', 'updated_at']
    inlines = [CartItemInline]
    
    def user_display(self, obj):
        return obj.user.username if obj.user else f'Guest ({obj.session_key[:8]}...)'
    user_display.short_description = 'User'
    
    def item_count(self, obj):
        return obj.get_total_items()
    item_count.short_description = 'Items'
    
    def total_price(self, obj):
        return f'₦{obj.get_total_price():,.2f}'
    total_price.short_description = 'Total'


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['cart', 'product', 'quantity', 'total_price', 'added_at']
    list_filter = ['added_at']
    search_fields = ['cart__user__username', 'product__name']
    readonly_fields = ['added_at', 'updated_at']
    
    def total_price(self, obj):
        return f'₦{obj.get_total_price():,.2f}'
    total_price.short_description = 'Total'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'user', 'status', 'payment_status',
        'total_amount', 'created_at'
    ]
    list_filter = ['status', 'payment_status', 'created_at', 'updated_at']
    search_fields = [
        'order_number', 'user__username', 'user__email',
        'shipping_name', 'shipping_phone', 'transaction_id'
    ]
    readonly_fields = [
        'id', 'order_number', 'subtotal', 'shipping_cost', 'tax',
        'total_amount', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('id', 'order_number', 'user', 'status', 'payment_status')
        }),
        ('Pricing', {
            'fields': ('subtotal', 'shipping_cost', 'tax', 'total_amount')
        }),
        ('Shipping Information', {
            'fields': (
                'shipping_name', 'shipping_phone', 'shipping_address_line1',
                'shipping_address_line2', 'shipping_city', 'shipping_state',
                'shipping_postal_code', 'shipping_country'
            )
        }),
        ('Payment Information', {
            'fields': ('payment_method', 'transaction_id')
        }),
        ('Tracking', {
            'fields': ('tracking_number',)
        }),
        ('Notes', {
            'fields': ('customer_notes', 'admin_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'paid_at', 'shipped_at', 'delivered_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [OrderItemInline]
    actions = ['mark_as_processing', 'mark_as_shipped', 'mark_as_delivered']
    
    def mark_as_processing(self, request, queryset):
        updated = queryset.update(status='processing')
        self.message_user(request, f'{updated} order(s) marked as processing.')
    mark_as_processing.short_description = 'Mark as Processing'
    
    def mark_as_shipped(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='shipped', shipped_at=timezone.now())
        self.message_user(request, f'{updated} order(s) marked as shipped.')
    mark_as_shipped.short_description = 'Mark as Shipped'
    
    def mark_as_delivered(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='delivered', delivered_at=timezone.now())
        self.message_user(request, f'{updated} order(s) marked as delivered.')
    mark_as_delivered.short_description = 'Mark as Delivered'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product_name', 'product_sku', 'quantity', 'unit_price', 'total_price']
    list_filter = ['order__created_at']
    search_fields = ['order__order_number', 'product_name', 'product_sku']
    readonly_fields = ['order', 'product', 'product_name', 'product_sku', 'quantity', 'unit_price', 'total_price']


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'added_at']
    list_filter = ['added_at']
    search_fields = ['user__username', 'product__name']
    readonly_fields = ['added_at']


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ['email', 'name', 'is_active', 'subscribed_at', 'unsubscribed_at']
    list_filter = ['is_active', 'subscribed_at']
    search_fields = ['email', 'name']
    readonly_fields = ['subscribed_at', 'unsubscribed_at']
    actions = ['activate_subscriptions', 'deactivate_subscriptions']
    
    def activate_subscriptions(self, request, queryset):
        updated = queryset.update(is_active=True, unsubscribed_at=None)
        self.message_user(request, f'{updated} subscription(s) activated.')
    activate_subscriptions.short_description = 'Activate subscriptions'
    
    def deactivate_subscriptions(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(is_active=False, unsubscribed_at=timezone.now())
        self.message_user(request, f'{updated} subscription(s) deactivated.')
    deactivate_subscriptions.short_description = 'Deactivate subscriptions'