from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
import random
import string
from ckeditor.fields import RichTextField
from embed_video.fields import EmbedVideoField
from agents.models import Agent
User = get_user_model()


# ==================== LOCATION MODELS ====================

class State(models.Model):
    """Nigerian States"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)  # e.g., "AN" for Anambra
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class City(models.Model):
    """Cities in Nigerian States"""
    name = models.CharField(max_length=100)
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='cities')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Cities'
        unique_together = ['name', 'state']  # Same city name can exist in different states
    
    def __str__(self):
        return f"{self.name}, {self.state.name}"


# ==================== PROPERTY MODELS ====================

# models.py
class PropertyType(models.Model):
    """Types of properties - Nigerian context"""
    TYPE_CHOICES = [
        # Residential
        ('detached_house', 'Detached House'),
        ('semi_detached', 'Semi-Detached House'),
        ('terrace', 'Terrace/Townhouse'),
        ('duplex', 'Duplex'),
        ('bungalow', 'Bungalow'),
        ('mansion', 'Mansion'),
        ('villa', 'Villa'),
        ('cottage', 'Cottage'),
        
        # Apartments
        ('studio', 'Studio Apartment'),
        ('1_bed_flat', '1-Bedroom Flat'),
        ('2_bed_flat', '2-Bedroom Flat'),
        ('3_bed_flat', '3-Bedroom Flat'),
        ('4_bed_flat', '4+ Bedroom Flat'),
        ('penthouse', 'Penthouse'),
        ('maisonette', 'Maisonette'),
        ('serviced_apt', 'Serviced Apartment'),
        
        # Nigerian Specific
        ('self_contain', 'Self-Contain'),
        ('room_parlour', 'Room and Parlour'),
        ('mini_flat', 'Mini Flat'),
        ('boys_quarters', 'Boys Quarters (BQ)'),
        
        # Commercial
        ('office', 'Office Space'),
        ('shop', 'Shop/Store'),
        ('mall', 'Shopping Mall'),
        ('showroom', 'Showroom'),
        ('warehouse', 'Warehouse'),
        ('factory', 'Factory'),
        ('hotel', 'Hotel'),
        ('event_center', 'Event Center'),
        ('filling_station', 'Filling Station'),
        
        # Land
        ('residential_land', 'Residential Land'),
        ('commercial_land', 'Commercial Land'),
        ('agricultural_land', 'Agricultural Land'),
        ('industrial_land', 'Industrial Land'),
        ('mixed_use_land', 'Mixed-Use Land'),
        
        # Special
        ('compound', 'Compound'),
        ('estate_house', 'Estate House'),
        ('farm_house', 'Farm House'),
        ('student_accommodation', 'Student Accommodation'),
    ]
    
    name = models.CharField(max_length=50, choices=TYPE_CHOICES, unique=True)
    category = models.CharField(max_length=20, choices=[
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('land', 'Land'),
        ('special', 'Special'),
    ], default='residential')
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='bi bi-house-door')
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['category', 'display_order', 'name']
    
    def __str__(self):
        return self.get_name_display()


class PropertyStatus(models.Model):
    """Property listing status"""
    STATUS_CHOICES = [
        ('for_sale', 'For Sale'),
        ('for_rent', 'For Rent'),
        ('sold', 'Sold'),
        ('rented', 'Rented'),
        ('pending', 'Pending'),
    ]
    
    name = models.CharField(max_length=20, choices=STATUS_CHOICES, unique=True)
    
    class Meta:
        verbose_name_plural = 'Property Statuses'
    
    def __str__(self):
        return self.get_name_display()


class Property(models.Model):
    """Main Property Model"""
    
    # Basic Information
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=250, unique=True, blank=True)
    description = RichTextField(blank=True)
    
    # Location
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='properties')
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='properties')
    address = models.CharField(max_length=500)
    zip_code = models.CharField(max_length=10, blank=True)
    
    # Property Details
    property_type = models.ForeignKey(PropertyType, on_delete=models.CASCADE, related_name='properties')
    status = models.ForeignKey(PropertyStatus, on_delete=models.CASCADE, related_name='properties')
    
    # Specifications
    bedrooms = models.PositiveIntegerField(default=0)
    bathrooms = models.PositiveIntegerField(default=0)
    square_feet = models.PositiveIntegerField(help_text="Property size in square feet")
    lot_size = models.PositiveIntegerField(blank=True, null=True, help_text="Lot size in square feet")
    year_built = models.PositiveIntegerField(blank=True, null=True)
    parking_spaces = models.PositiveIntegerField(default=0)
    
    # Pricing
    price = models.DecimalField(max_digits=15, decimal_places=2)
    price_per_sqft = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # Features & Amenities
    has_garage = models.BooleanField(default=False)
    has_pool = models.BooleanField(default=False)
    has_garden = models.BooleanField(default=False)
    has_security = models.BooleanField(default=False)
    has_gym = models.BooleanField(default=False)
    has_balcony = models.BooleanField(default=False)
    is_furnished = models.BooleanField(default=False)
    has_ac = models.BooleanField(default=False)
    has_heating = models.BooleanField(default=False)
    pet_friendly = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    # Additional Features (JSON field for flexibility)
    additional_features = models.JSONField(blank=True, null=True, help_text="Store additional features as JSON")
    
    # Media
    featured_image = models.ImageField(upload_to='properties/featured/', blank=True, null=True)
    video_url = EmbedVideoField(blank=True, help_text="YouTube or Vimeo URL")
    virtual_tour_url = models.URLField(blank=True, help_text="360° virtual tour URL")
    
    # Badges & Tags
    is_featured = models.BooleanField(default=False)
    is_premium = models.BooleanField(default=False)
    is_hot = models.BooleanField(default=False)
    is_new = models.BooleanField(default=False)
    is_exclusive = models.BooleanField(default=False)
    
    
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='properties')
    
    # Owner (Admin who listed)
    listed_by = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, related_name='listed_properties')
    
    # Referral tracking - which agent referred the buyer
    referring_agent = models.ForeignKey('agents.Agent', on_delete=models.SET_NULL, null=True, blank=True, related_name='referred_properties', help_text="Agent who referred the buyer")
    
    # Views & Interactions
    views_count = models.PositiveIntegerField(default=0)
    saved_count = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    listed_date = models.DateField(auto_now_add=True)
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(max_length=500, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Properties'
        indexes = [
            models.Index(fields=['state', 'city']),
            models.Index(fields=['property_type']),
            models.Index(fields=['price']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Auto-generate slug
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Property.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Calculate price per square foot
        if self.square_feet and self.square_feet > 0:
            self.price_per_sqft = self.price / self.square_feet
        
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('property_detail', kwargs={'slug': self.slug})
    
    def increment_views(self):
        """Increment view count"""
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    def get_badge_display(self):
        """Return appropriate badge for display"""
        if self.is_featured:
            return {'text': 'Featured', 'class': 'featured'}
        elif self.is_premium:
            return {'text': 'Premium', 'class': 'premium'}
        elif self.is_hot:
            return {'text': 'Hot', 'class': 'hot'}
        elif self.is_new:
            return {'text': 'New', 'class': 'new'}
        elif self.is_exclusive:
            return {'text': 'Exclusive', 'class': 'exclusive'}
        return None
    
    def get_days_listed(self):
        """Get number of days since listing"""
        from django.utils import timezone
        delta = timezone.now().date() - self.listed_date
        return delta.days
    
    @property
    def formatted_price(self):
        """Format price with currency symbol"""
        return f"₦{self.price:,.2f}"


class PropertyImage(models.Model):
    """Multiple images for a property"""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='properties/gallery/')
    caption = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', '-uploaded_at']
    
    def __str__(self):
        return f"Image for {self.property.title}"
    
    def save(self, *args, **kwargs):
        # If this is set as primary, unset other primary images
        if self.is_primary:
            PropertyImage.objects.filter(property=self.property, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)


class PropertyAmenity(models.Model):
    """Individual amenities/features"""
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, default='bi bi-check-circle')
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = 'Property Amenities'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class PropertyAmenityLink(models.Model):
    """Link properties to amenities (Many-to-Many with extra fields)"""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='property_amenities')
    amenity = models.ForeignKey(PropertyAmenity, on_delete=models.CASCADE)
    is_available = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['property', 'amenity']
    
    def __str__(self):
        return f"{self.property.title} - {self.amenity.name}"


# ==================== PROPERTY APPLICATION MODEL ====================

class PropertyApplication(models.Model):
    """
    Application form for a property unit — mirrors the Ibby's Mall
    Form & FAQ document from Finebricks Properties.
    Linked to a specific Property; submitted from the property detail page.
    """

    # ── Link to property ────────────────────────────────────────────────────
    # NOTE: named 'listing' (not 'property') to avoid shadowing Python's
    # built-in @property decorator, which would cause a TypeError.
    listing = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    applicant = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='property_applications'
    )

    # ── Application status (admin-managed) ──────────────────────────────────
    APPLICATION_STATUS = [
        ('pending',   'Pending Review'),
        ('reviewing', 'Under Review'),
        ('approved',  'Approved'),
        ('rejected',  'Rejected'),
    ]
    status      = models.CharField(max_length=20, choices=APPLICATION_STATUS, default='pending')
    admin_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    # ── SECTION 1: Personal Details ──────────────────────────────────────────
    TITLE_CHOICES = [
        ('mr',     'Mr'),
        ('mrs',    'Mrs'),
        ('miss',   'Miss'),
        ('ms',     'Ms'),
        ('dr',     'Dr'),
        ('prof',   'Prof'),
        ('engr',   'Engr'),
        ('chief',  'Chief'),
        ('alhaji', 'Alhaji'),
        ('alhaja', 'Alhaja'),
        ('barr',   'Barr'),
        ('other',  'Other'),
    ]
    title       = models.CharField(max_length=10, choices=TITLE_CHOICES)
    surname     = models.CharField(max_length=100)
    firstname   = models.CharField(max_length=100)
    other_names = models.CharField(max_length=100, blank=True)

    residential_address = models.TextField()
    phone_number        = models.CharField(max_length=20)
    email               = models.EmailField()
    date_of_birth       = models.DateField()

    nationality    = models.CharField(max_length=100, default='Nigerian')
    marital_status = models.CharField(
        max_length=20,
        choices=[
            ('single',   'Single'),
            ('married',  'Married'),
            ('divorced', 'Divorced'),
            ('widowed',  'Widowed'),
        ]
    )
    occupation    = models.CharField(max_length=150)
    place_of_work = models.CharField(max_length=200, blank=True)
    work_address  = models.TextField(blank=True)

    passport_photo = models.ImageField(
        upload_to='applications/passports/',
        blank=True, null=True
    )

    # ── Means of Identification ──────────────────────────────────────────────
    ID_TYPE_CHOICES = [
        ('national_id',     'National Identity Card'),
        ('drivers_licence', "Driver's Licence / Permit"),
        ('intl_passport',   'International Passport'),
        ('voters_card',     "Voter's Card"),
    ]
    id_type    = models.CharField(max_length=20, choices=ID_TYPE_CHOICES)
    id_number  = models.CharField(max_length=100)
    id_document = models.FileField(
        upload_to='applications/ids/',
        blank=True, null=True,
        help_text="Scanned copy / photo of the ID document"
    )

    # ── Politically Exposed Person ───────────────────────────────────────────
    is_pep      = models.BooleanField(
        default=False,
        verbose_name="Are you (or related to) a Politically Exposed Person (PEP)?"
    )
    pep_details = models.CharField(
        max_length=300, blank=True,
        help_text="Name and position held (required if PEP is Yes)"
    )

    # ── SECTION 2: Next of Kin ───────────────────────────────────────────────
    NOK_RELATIONSHIP = [
        ('spouse',  'Spouse'),
        ('parent',  'Parent'),
        ('sibling', 'Sibling'),
        ('child',   'Child'),
        ('friend',  'Friend'),
        ('other',   'Other'),
    ]
    nok_name         = models.CharField(max_length=200, verbose_name="Name of Next of Kin")
    nok_relationship = models.CharField(max_length=20, choices=NOK_RELATIONSHIP, verbose_name="Relationship")
    nok_phone        = models.CharField(max_length=20, verbose_name="Next of Kin Phone Number")
    nok_email        = models.EmailField(blank=True, verbose_name="Next of Kin Email")
    nok_address      = models.TextField(verbose_name="Next of Kin Address")

    # ── SECTION 3: Purchase Details (FAQ Q2 & Q3) ───────────────────────────
    FLOOR_CHOICES = [
        ('ground', 'Ground Floor'),
        ('first',  'First Floor'),
        ('second', 'Second Floor'),
    ]
    PAYMENT_PLAN_CHOICES = [
        ('3_month', '3-Month Plan'),
        ('6_month', '6-Month Plan'),
    ]
    floor_choice    = models.CharField(max_length=10, blank=True, null=True, choices=FLOOR_CHOICES)
    number_of_shops = models.PositiveIntegerField(default=1,blank=True, null=True, verbose_name="Number of Shop Units")
    payment_plan    = models.CharField(max_length=10, blank=True, null=True, choices=PAYMENT_PLAN_CHOICES)
    intended_use    = models.TextField(
        help_text="e.g. retail, office, service centre, etc.",
        verbose_name="Intended Use of the Shopping Unit", blank=True, null=True,
    )

    # ── SECTION 4: AML Declaration (FAQ Q7) ─────────────────────────────────
    aml_accepted         = models.BooleanField(default=False, verbose_name="AML/CFT Declaration Accepted")
    subscriber_signature = models.ImageField(
        upload_to='applications/signatures/',
        blank=True, null=True,
        help_text="Upload a scanned signature image"
    )

    # ── SECTION 5: Realtor Details ───────────────────────────────────────────
    realtor_name  = models.CharField(max_length=200, blank=True)
    realtor_email = models.EmailField(blank=True)
    realtor_phone = models.CharField(max_length=20, blank=True)
    realtor_cid   = models.CharField(max_length=100, blank=True, verbose_name="Realtor CID Number")

    # ────────────────────────────────────────────────────────────────────────
    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Property Application'
        verbose_name_plural = 'Property Applications'

    def __str__(self):
        return f"{self.get_full_name()} → {self.listing.title} ({self.get_status_display()})"

    def get_full_name(self):
        parts = [self.firstname, self.other_names, self.surname]
        return ' '.join(p for p in parts if p).strip()

    # Price lookup table matching FAQ Q3
    UNIT_PRICES = {
        ('ground', '3_month'): 40_000_000,
        ('ground', '6_month'): 40_500_000,
        ('first',  '3_month'): 37_000_000,
        ('first',  '6_month'): 37_500_000,
        ('second', '3_month'): 37_000_000,
        ('second', '6_month'): 37_500_000,
    }

    def get_unit_price(self):
        return self.UNIT_PRICES.get((self.floor_choice, self.payment_plan), 0)

    def get_total_price(self):
        return self.get_unit_price() * self.number_of_shops

    @property
    def formatted_total(self):
        return f"₦{self.get_total_price():,.2f}"