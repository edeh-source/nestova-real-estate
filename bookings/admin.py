from django.contrib import admin
from .models import Apartment, ApartmentImage, Booking, Review, Payment, ApartmentChoice



@admin.register(ApartmentChoice)
class ApartmentChoiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'city', 'property_type', 'price_per_night', 'bedrooms', 'status', 'created_at']
    list_filter = ['status', 'property_type', 'city', 'created_at']
    search_fields = ['title', 'description', 'city', 'address']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'property_type', 'status', 'owner')
        }),
        ('Location', {
            'fields': ('address', 'city', 'state', 'zip_code')
        }),
        ('Property Details', {
            'fields': ('bedrooms', 'bathrooms', 'square_feet', 'floor_number', 'max_guests')
        }),
        ('Pricing', {
            'fields': ('price_per_night', 'price_per_month', 'security_deposit')
        }),
        ('Amenities', {
            'fields': (
                'has_wifi', 'has_parking', 'has_pool', 'has_gym',
                'has_ac', 'has_heating', 'is_pet_friendly',
                'has_balcony', 'has_elevator'
            )
        }),
        ('Media', {
            'fields': ('main_image',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(ApartmentImage)
class ApartmentImageAdmin(admin.ModelAdmin):
    list_display = ['apartment', 'caption', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['apartment__title', 'caption']


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        'booking_number', 'apartment', 'user', 'check_in_date',
        'check_out_date', 'booking_status', 'payment_status', 'total_price'
    ]
    list_filter = [
        'booking_status', 'payment_status', 'check_in_date',
        'check_out_date', 'created_at'
    ]
    search_fields = [
        'booking_number', 'guest_name', 'guest_email',
        'guest_phone', 'apartment__title', 'user__username'
    ]
    readonly_fields = [
        'booking_number', 'number_of_nights', 'total_price',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Booking Information', {
            'fields': (
                'booking_number', 'apartment', 'user',
                'booking_status', 'payment_status'
            )
        }),
        ('Dates', {
            'fields': (
                'check_in_date', 'check_out_date',
                'number_of_nights', 'number_of_guests'
            )
        }),
        ('Guest Information', {
            'fields': (
                'guest_name', 'guest_email', 'guest_phone',
                'special_requests'
            )
        }),
        ('Pricing', {
            'fields': ('total_price', 'security_deposit_paid')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['confirm_bookings', 'cancel_bookings']
    
    def confirm_bookings(self, request, queryset):
        updated = queryset.update(booking_status='confirmed')
        self.message_user(request, f'{updated} bookings confirmed.')
    confirm_bookings.short_description = 'Confirm selected bookings'
    
    def cancel_bookings(self, request, queryset):
        updated = queryset.update(booking_status='cancelled')
        self.message_user(request, f'{updated} bookings cancelled.')
    cancel_bookings.short_description = 'Cancel selected bookings'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'apartment', 'overall_rating',
        'created_at', 'is_verified'
    ]
    list_filter = [
        'overall_rating', 'is_verified', 'created_at'
    ]
    search_fields = [
        'title', 'comment', 'user__username',
        'apartment__title'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Review Information', {
            'fields': (
                'booking', 'apartment', 'user',
                'is_verified', 'title', 'comment'
            )
        }),
        ('Ratings', {
            'fields': (
                'overall_rating', 'cleanliness_rating',
                'communication_rating', 'location_rating',
                'value_rating'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'booking', 'amount', 'payment_method',
        'is_successful', 'payment_date'
    ]
    list_filter = [
        'is_successful', 'payment_method', 'payment_date'
    ]
    search_fields = [
        'transaction_id', 'booking__booking_number',
        'notes'
    ]
    readonly_fields = ['payment_date']
    
    fieldsets = (
        ('Payment Information', {
            'fields': (
                'booking', 'amount', 'payment_method',
                'transaction_id', 'is_successful'
            )
        }),
        ('Additional Information', {
            'fields': ('notes', 'payment_date')
        })
    )