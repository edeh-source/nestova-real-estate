from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
from django.urls import reverse
from django.utils.text import slugify
from ckeditor.fields import RichTextField

User = get_user_model()


class ApartmentChoice(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    
    def __str__(self):
        return self.name

class Apartment(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('maintenance', 'Under Maintenance'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True, null=True, unique=True)
    description = RichTextField()
    property_type = models.ForeignKey(ApartmentChoice, on_delete=models.SET_NULL, null=True, related_name='apartments')
    address = models.CharField(max_length=300)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=10)
    
    # Property Details
    bedrooms = models.PositiveIntegerField(default=1)
    bathrooms = models.PositiveIntegerField(default=1)
    square_feet = models.PositiveIntegerField()
    floor_number = models.PositiveIntegerField(null=True, blank=True)
    
    # Pricing
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    price_per_month = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Amenities
    has_wifi = models.BooleanField(default=False)
    has_parking = models.BooleanField(default=False)
    has_pool = models.BooleanField(default=False)
    has_gym = models.BooleanField(default=False)
    has_ac = models.BooleanField(default=True)
    has_heating = models.BooleanField(default=True)
    is_pet_friendly = models.BooleanField(default=False)
    has_balcony = models.BooleanField(default=False)
    has_elevator = models.BooleanField(default=False)
    
    # Status and Management
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_apartments', blank=True, null=True)
    max_guests = models.PositiveIntegerField(default=2)
    
    # Media
    main_image = models.ImageField(upload_to='apartments/', null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.city}"
    
    
    def get_absolute_url(self):
        return reverse("apartment_details", args=[self.slug])
    
    
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            self.slug = base_slug[:100]  # Reasonable slug length
        super().save(*args, **kwargs)
        
        
    
    
    def get_amenities_list(self):
        """Returns list of available amenities"""
        amenities = []
        if self.has_wifi:
            amenities.append('WiFi')
        if self.has_parking:
            amenities.append('Parking')
        if self.has_pool:
            amenities.append('Pool')
        if self.has_gym:
            amenities.append('Gym')
        if self.has_ac:
            amenities.append('Air Conditioning')
        if self.has_heating:
            amenities.append('Heating')
        if self.is_pet_friendly:
            amenities.append('Pet Friendly')
        if self.has_balcony:
            amenities.append('Balcony')
        if self.has_elevator:
            amenities.append('Elevator')
        return amenities


class ApartmentImage(models.Model):
    """Additional images for apartments"""
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='apartments/gallery/')
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['uploaded_at']
    
    def __str__(self):
        return f"Image for {self.apartment.title}"


class Booking(models.Model):
    """Model for apartment bookings"""
    BOOKING_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('completed', 'Completed'),
        ('refunded', 'Refunded'),
    ]
    
    # Booking Details
    booking_number = models.CharField(max_length=20, unique=True, editable=False)
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name='bookings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    
    # Dates
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    number_of_guests = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    number_of_nights = models.PositiveIntegerField(editable=False)
    
    # Pricing
    total_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    security_deposit_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Guest Information
    guest_name = models.CharField(max_length=200)
    guest_email = models.EmailField()
    guest_phone = models.CharField(max_length=20)
    special_requests = models.TextField(blank=True)
    
    # Status
    booking_status = models.CharField(max_length=20, choices=BOOKING_STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Booking {self.booking_number} - {self.apartment.title}"
    
    def save(self, *args, **kwargs):
        # Generate booking number
        if not self.booking_number:
            import random
            import string
            self.booking_number = 'BK' + ''.join(random.choices(string.digits, k=8))
        
        # Calculate number of nights
        if self.check_in_date and self.check_out_date:
            delta = self.check_out_date - self.check_in_date
            self.number_of_nights = delta.days
            
            # Calculate total price
            self.total_price = self.apartment.price_per_night * self.number_of_nights
        
        super().save(*args, **kwargs)
    
    def is_active(self):
        """Check if booking is currently active"""
        today = timezone.now().date()
        return (self.check_in_date <= today <= self.check_out_date and 
                self.booking_status in ['confirmed', 'checked_in'])
    
    def can_cancel(self):
        """Check if booking can be cancelled"""
        today = timezone.now().date()
        return (self.check_in_date > today and 
                self.booking_status not in ['cancelled', 'checked_out'])


class Review(models.Model):
    """Model for apartment reviews"""
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='review')
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    
    # Ratings (1-5)
    overall_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    cleanliness_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    communication_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    location_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    value_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    
    # Review Content
    title = models.CharField(max_length=200)
    comment = models.TextField()
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_verified = models.BooleanField(default=True)  # Verified if tied to a real booking
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['booking', 'user']
    
    def __str__(self):
        return f"Review by {self.user.username} for {self.apartment.title}"


class Payment(models.Model):
    """Model for tracking payments"""
    PAYMENT_METHOD_CHOICES = [
        ('card', 'Credit/Debit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('paypal', 'PayPal'),
        ('cash', 'Cash'),
    ]
    
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    transaction_id = models.CharField(max_length=100, unique=True)
    
    is_successful = models.BooleanField(default=False)
    payment_date = models.DateTimeField(auto_now_add=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Payment for {self.booking.booking_number} - ${self.amount}"