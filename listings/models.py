from django.db import models
from django.conf import settings
from django.utils import timezone
from property.models import Property
import uuid

class ListingPackage(models.Model):
    """
    Defines slot packages available for permanent purchase.
    e.g. Basic (5 slots for ₦15,000), Pro (10 slots for ₦30,000).
    """
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    slots_count = models.PositiveIntegerField(help_text="Number of property posting slots in this package")
    description = models.TextField(blank=True)
    features = models.JSONField(default=list, blank=True, help_text="List of features for display")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Keep for backward compatibility, but optional
    listing_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Deprecated: Use slots_count")
    duration_days = models.PositiveIntegerField(null=True, blank=True, help_text="Deprecated: Slots are permanent")
    is_default = models.BooleanField(default=False, help_text="Deprecated")

    def __str__(self):
        return f"{self.name} - {self.slots_count} Slots"
    
    @property
    def price_per_slot(self):
        """Calculate price per slot for display"""
        if self.slots_count > 0:
            return self.price / self.slots_count
        return 0

    class Meta:
        ordering = ['price']


class UserSubscription(models.Model):
    """
    Tracks user's permanent slot ownership and usage.
    Users purchase slots that never expire.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription')
    
    # New slot-based fields
    total_slots = models.PositiveIntegerField(default=1, help_text="Total property posting slots owned (permanent)")
    used_slots = models.PositiveIntegerField(default=0, help_text="Number of slots currently in use")
    initial_free_slots = models.PositiveIntegerField(default=1, help_text="Free slots given initially (admin configurable)")
    
    # Keep for reference/history but make optional
    package = models.ForeignKey(ListingPackage, on_delete=models.SET_NULL, null=True, blank=True, help_text="Last purchased package (for reference)")
    
    # Deprecated fields (keep for backward compatibility)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.remaining_slots}/{self.total_slots} slots"

    def save(self, *args, **kwargs):
        # Set initial free slots if this is a new subscription
        if not self.pk and self.total_slots == 1:
            self.total_slots = self.initial_free_slots
        super().save(*args, **kwargs)
    
    @property
    def remaining_slots(self):
        """Calculate remaining available slots"""
        return max(0, self.total_slots - self.used_slots)
    
    @property
    def slots_usage_percentage(self):
        """Calculate percentage of slots used"""
        if self.total_slots == 0:
            return 100
        return int((self.used_slots / self.total_slots) * 100)

    def has_remaining_slots(self):
        """Check if user has available slots to post"""
        return self.remaining_slots > 0
    
    def add_slots(self, count):
        """Add purchased slots to total"""
        self.total_slots += count
        self.save()
    
    def use_slot(self):
        """Increment used slots when posting property"""
        if self.has_remaining_slots():
            self.used_slots += 1
            self.save()
            return True
        return False
    
    def release_slot(self):
        """Decrement used slots when property is deleted"""
        if self.used_slots > 0:
            self.used_slots -= 1
            self.save()
    
    def recalculate_used_slots(self):
        """Recalculate used_slots from actual property count"""
        from property.models import Property
        self.used_slots = Property.objects.filter(listed_by=self.user).count()
        self.save()
    
    # Deprecated methods (keep for backward compatibility)
    @property
    def is_valid(self):
        """Deprecated: Slots are permanent now"""
        return self.is_active
    
    @property
    def remaining_days(self):
        """Deprecated: Slots don't expire"""
        return 999
    
    def get_used_slots(self):
        """Deprecated: Use used_slots field instead"""
        return self.used_slots


class SavedProperty(models.Model):
    """
    User's saved/wishlisted properties.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_properties')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='saved_by')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'property']
        ordering = ['-saved_at']

    def __str__(self):
        return f"{self.user} saved {self.property.title}"

class Notification(models.Model):
    """
    Simple notification system
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Notification for {self.user}: {self.title}"
