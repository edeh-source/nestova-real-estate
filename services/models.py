from django.db import models
from django.contrib.auth import get_user_model
from phonenumber_field.modelfields import PhoneNumberField

User = get_user_model()


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
