from django.db import models
from django.contrib.auth import get_user_model
from phonenumber_field.modelfields import PhoneNumberField

User = get_user_model()


# ==============================================================
#  EXISTING MODEL — Interior Design Request
# ==============================================================

class InteriorDesignRequest(models.Model):
    """
    Model for clients requesting interior design services
    """
    SERVICE_TYPE_CHOICES = [
        ('residential', 'Residential Design'),
        ('commercial', 'Commercial Design'),
        ('renovation', 'Renovation & Remodeling'),
        ('consultation', 'Design Consultation'),
    ]

    BUDGET_RANGE_CHOICES = [
        ('0-500000', 'Under ₦500,000'),
        ('500000-1000000', '₦500,000 - ₦1,000,000'),
        ('1000000-3000000', '₦1,000,000 - ₦3,000,000'),
        ('3000000-5000000', '₦3,000,000 - ₦5,000,000'),
        ('5000000+', 'Above ₦5,000,000'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('contacted', 'Client Contacted'),
        ('in_progress', 'Project In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    # Client Information
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interior_design_requests', null=True, blank=True)
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = PhoneNumberField()

    # Project Details
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES)
    property_address = models.TextField(help_text="Full address of the property to be designed")
    property_size = models.CharField(max_length=100, blank=True, help_text="e.g., 2000 sq ft, 3 bedroom apartment")

    # Design Preferences
    budget_range = models.CharField(max_length=20, choices=BUDGET_RANGE_CHOICES)
    preferred_style = models.CharField(max_length=200, blank=True, help_text="e.g., Modern, Contemporary, Traditional, Minimalist")
    project_description = models.TextField(help_text="Describe your vision and requirements for the project")

    # Timeline
    preferred_start_date = models.DateField(null=True, blank=True)
    project_deadline = models.DateField(null=True, blank=True)

    # Additional Information
    reference_images = models.FileField(upload_to='interior_design/references/', null=True, blank=True, help_text="Upload inspiration images (optional)")
    special_requirements = models.TextField(blank=True, help_text="Any special requirements or considerations")

    # Status Tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True, help_text="Internal notes for admin/designers")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    contacted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Interior Design Request'
        verbose_name_plural = 'Interior Design Requests'

    def __str__(self):
        return f"{self.full_name} - {self.get_service_type_display()} ({self.status})"

    def mark_as_contacted(self):
        """Mark request as contacted"""
        from django.utils import timezone
        self.status = 'contacted'
        self.contacted_at = timezone.now()
        self.save()

    def mark_as_completed(self):
        """Mark project as completed"""
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()


# ==============================================================
#  NESTOVA TOURISM — Inquiry / Trip Planning Model
# ==============================================================

class TourismInquiry(models.Model):
    """
    Model for visitors requesting tourism packages, trip planning, or partnerships.
    Covers the Nestova Tourism ecosystem page.
    """

    INQUIRY_TYPE_CHOICES = [
        ('travel_package', 'Travel Package / Tour'),
        ('group_tour', 'Group Tour'),
        ('cultural_tour', 'Cultural Heritage Tour'),
        ('business_tourism', 'Business Tourism'),
        ('educational_tourism', 'Educational Tourism'),
        ('luxury_experience', 'Luxury / Lifestyle Experience'),
        ('hospitality_partnership', 'Hospitality Partnership'),
        ('investment_opportunity', 'Tourism Investment Opportunity'),
        ('youth_fellowship', 'Youth Tourism Fellowship'),
        ('general', 'General Inquiry'),
    ]

    DESTINATION_CHOICES = [
        ('within_nigeria', 'Within Nigeria'),
        ('west_africa', 'West Africa'),
        ('rest_of_africa', 'Rest of Africa'),
        ('international', 'International'),
        ('not_sure', 'Not Sure Yet'),
    ]

    BUDGET_CHOICES = [
        ('under_100k', 'Under ₦100,000'),
        ('100k_500k', '₦100,000 – ₦500,000'),
        ('500k_1m', '₦500,000 – ₦1,000,000'),
        ('1m_5m', '₦1,000,000 – ₦5,000,000'),
        ('above_5m', 'Above ₦5,000,000'),
        ('open', 'Open / Flexible'),
    ]

    GROUP_SIZE_CHOICES = [
        ('solo', 'Solo (1 Person)'),
        ('couple', 'Couple (2 People)'),
        ('small', 'Small Group (3–10 People)'),
        ('medium', 'Medium Group (11–30 People)'),
        ('large', 'Large Group (30+ People)'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('contacted', 'Client Contacted'),
        ('package_sent', 'Package Sent'),
        ('booked', 'Booked / Confirmed'),
        ('completed', 'Trip Completed'),
        ('cancelled', 'Cancelled'),
    ]

    # Contact Info
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tourism_inquiries')
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = PhoneNumberField()

    # Trip Details
    inquiry_type = models.CharField(max_length=30, choices=INQUIRY_TYPE_CHOICES, default='general')
    destination_preference = models.CharField(max_length=30, choices=DESTINATION_CHOICES, default='within_nigeria')
    group_size = models.CharField(max_length=20, choices=GROUP_SIZE_CHOICES, default='solo')
    budget_range = models.CharField(max_length=20, choices=BUDGET_CHOICES, default='open')

    # Dates
    preferred_travel_date = models.DateField(null=True, blank=True, help_text="Preferred departure date")
    trip_duration = models.CharField(max_length=100, blank=True, help_text="e.g., 3 days, 1 week, 2 weeks")

    # Preferences & Message
    special_interests = models.CharField(max_length=300, blank=True, help_text="e.g., history, food, adventure, beaches, culture")
    message = models.TextField(help_text="Tell us about your dream experience or what you're looking for")

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    contacted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Tourism Inquiry'
        verbose_name_plural = 'Tourism Inquiries'

    def __str__(self):
        return f"{self.full_name} — {self.get_inquiry_type_display()} [{self.status}]"

    def mark_as_contacted(self):
        from django.utils import timezone
        self.status = 'contacted'
        self.contacted_at = timezone.now()
        self.save()


# ==============================================================
#  NESTOVA ACADEMY — Enrollment / Registration Model
# ==============================================================

class AcademyEnrollment(models.Model):
    """
    Model for individuals enrolling in Nestova Academy programs.
    Covers training, mentorship, and youth development registrations.
    """

    PROGRAM_CHOICES = [
        ('real_estate_training', 'Real Estate Training'),
        ('entrepreneurship', 'Entrepreneurship Development'),
        ('business_mentorship', 'Business Mentorship Program'),
        ('industry_networking', 'Industry Networking'),
        ('career_empowerment', 'Career Empowerment'),
        ('youth_development', 'Youth Development Initiative'),
        ('investment_masterclass', 'Investment Masterclass'),
        ('hospitality_training', 'Hospitality & Tourism Training'),
    ]

    EXPERIENCE_LEVEL_CHOICES = [
        ('beginner', 'Beginner — No Prior Experience'),
        ('intermediate', 'Intermediate — Some Experience'),
        ('advanced', 'Advanced — Experienced Professional'),
        ('entrepreneur', 'Business Owner / Entrepreneur'),
    ]

    FORMAT_CHOICES = [
        ('online', 'Online / Virtual'),
        ('in_person', 'In-Person (Lagos)'),
        ('hybrid', 'Hybrid'),
        ('self_paced', 'Self-Paced / Recorded'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Application Pending'),
        ('reviewed', 'Application Reviewed'),
        ('accepted', 'Accepted'),
        ('enrolled', 'Enrolled / Active'),
        ('completed', 'Program Completed'),
        ('deferred', 'Deferred'),
        ('rejected', 'Rejected'),
    ]

    # Personal Info
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='academy_enrollments')
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = PhoneNumberField()
    age = models.PositiveIntegerField(null=True, blank=True)
    occupation = models.CharField(max_length=200, blank=True, help_text="Current occupation or field of work")
    location = models.CharField(max_length=200, blank=True, help_text="City / State of residence")

    # Program Details
    program = models.CharField(max_length=40, choices=PROGRAM_CHOICES)
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_LEVEL_CHOICES, default='beginner')
    preferred_format = models.CharField(max_length=20, choices=FORMAT_CHOICES, default='online')

    # Goals & Motivation
    goals = models.TextField(help_text="What do you hope to achieve from this program?")
    how_heard = models.CharField(max_length=200, blank=True, help_text="How did you hear about Nestova Academy?")
    referral_name = models.CharField(max_length=200, blank=True, help_text="Name of person who referred you (if any)")

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Academy Enrollment'
        verbose_name_plural = 'Academy Enrollments'

    def __str__(self):
        return f"{self.full_name} — {self.get_program_display()} [{self.status}]"

    def accept(self):
        from django.utils import timezone
        self.status = 'accepted'
        self.accepted_at = timezone.now()
        self.save()


# ==============================================================
#  NESTOVA BROKERAGE — General Service Inquiry Model
# ==============================================================

class BrokerageInquiry(models.Model):
    """
    Model for general brokerage service inquiries —
    property sales, shortlets, cleaning, SmartShield installations, realtor hub.
    """

    SERVICE_CHOICES = [
        ('buy_property', 'Buy a Property'),
        ('sell_property', 'Sell My Property'),
        ('shortlet_booking', 'Book a Shortlet Apartment'),
        ('shortlet_listing', 'List My Shortlet'),
        ('interior_design', 'Interior Design'),
        ('smart_security', 'SmartShield Security Installation'),
        ('industrial_cleaning', 'Industrial Cleaning Service'),
        ('realtor_hub', 'Realtor / Developer Hub — List Property'),
        ('property_inspection', 'Book a Property Inspection'),
        ('investment_consulting', 'Investment Consulting'),
        ('property_management', 'Property Management'),
        ('documentation', 'Property Documentation Support'),
    ]

    LOCATION_CHOICES = [
        ('lagos', 'Lagos'),
        ('abuja', 'Abuja'),
        ('port_harcourt', 'Port Harcourt'),
        ('enugu', 'Enugu'),
        ('owerri', 'Owerri'),
        ('other', 'Other Location'),
    ]

    TIMELINE_CHOICES = [
        ('urgent', 'Urgent — As Soon As Possible'),
        ('within_month', 'Within 1 Month'),
        ('1_3_months', '1–3 Months'),
        ('3_6_months', '3–6 Months'),
        ('flexible', 'Flexible / Just Exploring'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('contacted', 'Client Contacted'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    # Contact Info
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='brokerage_inquiries')
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = PhoneNumberField()

    # Service Details
    service_requested = models.CharField(max_length=30, choices=SERVICE_CHOICES)
    location = models.CharField(max_length=20, choices=LOCATION_CHOICES, blank=True)
    timeline = models.CharField(max_length=20, choices=TIMELINE_CHOICES, default='flexible')
    budget = models.CharField(max_length=200, blank=True, help_text="Your budget range for this service")
    message = models.TextField(help_text="Provide details about what you need")

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    contacted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Brokerage Inquiry'
        verbose_name_plural = 'Brokerage Inquiries'

    def __str__(self):
        return f"{self.full_name} — {self.get_service_requested_display()} [{self.status}]"

    def mark_as_contacted(self):
        from django.utils import timezone
        self.status = 'contacted'
        self.contacted_at = timezone.now()
        self.save()


# ==============================================================
#  NESTOVA BUSINESSES — Partnership / Collaboration Inquiry
# ==============================================================

class BusinessPartnershipInquiry(models.Model):
    """
    Model for businesses and individuals wishing to partner with
    Nestova Businesses (Valpaint, SmartShield, Communications, Essentials, Tourism).
    """

    PARTNERSHIP_TYPE_CHOICES = [
        ('valpaint_distributor', 'Valpaint Distribution Partnership'),
        ('smartshield_installer', 'SmartShield Installer / Technician'),
        ('smartshield_investor', 'SmartShield Manufacturing Investor'),
        ('communications_supplier', 'Tech Gadget Supplier / Sourcing'),
        ('essentials_supplier', 'Home & Lifestyle Product Supplier'),
        ('tourism_hospitality', 'Tourism Hospitality Partner (Hotel/Resort/Airline)'),
        ('tourism_agency', 'Travel / Tourism Agency Partnership'),
        ('media_influencer', 'Media / Influencer Collaboration'),
        ('real_estate_developer', 'Real Estate Developer Partnership'),
        ('general', 'General Business Inquiry'),
    ]

    BUSINESS_SIZE_CHOICES = [
        ('individual', 'Individual / Freelancer'),
        ('startup', 'Startup (1–10 Employees)'),
        ('sme', 'SME (11–100 Employees)'),
        ('large', 'Large Business (100+ Employees)'),
        ('corporation', 'Corporation / Conglomerate'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('contacted', 'Team Contacted'),
        ('negotiation', 'In Negotiation'),
        ('active_partner', 'Active Partner'),
        ('declined', 'Declined'),
    ]

    # Contact Info
    full_name = models.CharField(max_length=200)
    business_name = models.CharField(max_length=300, blank=True)
    email = models.EmailField()
    phone = PhoneNumberField()
    location = models.CharField(max_length=200, blank=True, help_text="City / Country of operation")
    website = models.URLField(blank=True)

    # Partnership Details
    partnership_type = models.CharField(max_length=30, choices=PARTNERSHIP_TYPE_CHOICES)
    business_size = models.CharField(max_length=20, choices=BUSINESS_SIZE_CHOICES, default='individual')
    message = models.TextField(help_text="Describe what you're proposing and how you'd like to partner with Nestova")

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    contacted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Business Partnership Inquiry'
        verbose_name_plural = 'Business Partnership Inquiries'

    def __str__(self):
        name = self.business_name or self.full_name
        return f"{name} — {self.get_partnership_type_display()} [{self.status}]"
