from django.db import models
from django.utils import timezone
from django.core.validators import EmailValidator


class ContactMessage(models.Model):
    """Model for storing contact form submissions"""
    
    STATUS_CHOICES = [
        ('new', 'New'),
        ('read', 'Read'),
        ('replied', 'Replied'),
        ('archived', 'Archived'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Full Name")
    email = models.EmailField(
        max_length=254,
        validators=[EmailValidator()],
        verbose_name="Email Address"
    )
    subject = models.CharField(max_length=300, verbose_name="Subject")
    message = models.TextField(verbose_name="Message")
    
    # Metadata
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new',
        verbose_name="Status"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Submitted At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Last Updated")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP Address")
    user_agent = models.TextField(blank=True, null=True, verbose_name="User Agent")
    
    # Admin notes
    admin_notes = models.TextField(blank=True, null=True, verbose_name="Admin Notes")
    replied_at = models.DateTimeField(null=True, blank=True, verbose_name="Replied At")
    
    class Meta:
        verbose_name = "Contact Message"
        verbose_name_plural = "Contact Messages"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.subject} ({self.created_at.strftime('%Y-%m-%d')})"
    
    def mark_as_read(self):
        """Mark message as read"""
        if self.status == 'new':
            self.status = 'read'
            self.save(update_fields=['status', 'updated_at'])
    
    def mark_as_replied(self):
        """Mark message as replied"""
        self.status = 'replied'
        self.replied_at = timezone.now()
        self.save(update_fields=['status', 'replied_at', 'updated_at'])


class Newsletter(models.Model):
    """Model for newsletter subscriptions"""
    
    email = models.EmailField(
        unique=True,
        validators=[EmailValidator()],
        verbose_name="Email Address"
    )
    subscribed_at = models.DateTimeField(auto_now_add=True, verbose_name="Subscribed At")
    is_active = models.BooleanField(default=True, verbose_name="Active Subscription")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP Address")
    unsubscribed_at = models.DateTimeField(null=True, blank=True, verbose_name="Unsubscribed At")
    
    class Meta:
        verbose_name = "Newsletter Subscription"
        verbose_name_plural = "Newsletter Subscriptions"
        ordering = ['-subscribed_at']
        indexes = [
            models.Index(fields=['-subscribed_at']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        status = "Active" if self.is_active else "Unsubscribed"
        return f"{self.email} ({status})"
    
    def unsubscribe(self):
        """Unsubscribe from newsletter"""
        self.is_active = False
        self.unsubscribed_at = timezone.now()
        self.save(update_fields=['is_active', 'unsubscribed_at'])


class ContactInfo(models.Model):
    """Model for storing contact information displayed on the site"""
    
    # Company Information
    company_name = models.CharField(max_length=200, default="Nestova")
    tagline = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    
    # Address
    address_line1 = models.CharField(max_length=300, verbose_name="Address Line 1")
    address_line2 = models.CharField(max_length=300, blank=True, verbose_name="Address Line 2")
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="United States")
    
    # Contact Details
    phone = models.CharField(max_length=50, verbose_name="Phone Number")
    email = models.EmailField(verbose_name="Email Address")
    support_email = models.EmailField(blank=True, verbose_name="Support Email")
    
    # Business Hours
    weekday_hours = models.CharField(max_length=100, default="9 AM - 6 PM")
    weekend_hours = models.CharField(max_length=100, default="9 AM - 4 PM")
    
    # Map
    google_maps_embed_url = models.URLField(max_length=1000, blank=True, verbose_name="Google Maps Embed URL")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Social Media
    facebook_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Contact Information"
        verbose_name_plural = "Contact Information"
    
    def __str__(self):
        return f"{self.company_name} Contact Info"
    
    def get_full_address(self):
        """Return formatted full address"""
        parts = [
            self.address_line1,
            self.address_line2,
            f"{self.city}, {self.state} {self.postal_code}",
            self.country
        ]
        return ", ".join(filter(None, parts))
    
    @classmethod
    def get_active(cls):
        """Get the active contact info (singleton pattern)"""
        return cls.objects.filter(is_active=True).first()