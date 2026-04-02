from django.contrib import admin
from .models import Bank, Agent, PropertySale, Commission, Company, VerificationLog



@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active']
    search_fields = ['name', 'code']
    list_filter = ['is_active']


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ['user', 'referral_code', 'commission_rate', 'upline', 'is_active', 'created']
    search_fields = ['user__username', 'user__email', 'referral_code']
    list_filter = ['is_active', 'created']
    readonly_fields = ['referral_code', 'created', 'updated']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'referral_code', 'is_active')
        }),
        ('Verification Status', {
            'fields': ('verification_status', 'can_post_properties', 'rejection_reason')
        }),
        ('Identity Details', {
            'fields': ('id_type', 'id_number', 'id_verified', 'id_verification_date')
        }),
        ('Identity Documents', {
            'fields': ('id_card_front', 'id_card_back', 'selfie_photo')
        }),
        ('Referral Structure', {
            'fields': ('upline', 'commission_rate')
        }),
        ('Bank Details', {
            'fields': ('bank', 'account_name', 'account_number', 'bank_verified')
        }),
        ('Social Media', {
            'fields': ('facebook_page', 'linkedin_page', 'instagram_page', 'x_page'),
            'classes': ('collapse',)
        }),
        ('Staff Review', {
            'fields': ('verified_by', 'verified_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )

    actions = ['approve_agents', 'reject_agents']

    def approve_agents(self, request, queryset):
        from django.utils import timezone
        queryset.update(
            verification_status='verified',
            can_post_properties=True,
            verified_by=request.user,
            verified_at=timezone.now()
        )
        self.message_user(request, f"{queryset.count()} agents approved.")
    approve_agents.short_description = "Approve selected agents"

    def reject_agents(self, request, queryset):
        queryset.update(verification_status='rejected', can_post_properties=False)
        self.message_user(request, f"{queryset.count()} agents rejected.")
    reject_agents.short_description = "Reject selected agents"


@admin.register(PropertySale)
class PropertySaleAdmin(admin.ModelAdmin):
    list_display = ['property', 'buyer', 'referring_agent', 'sale_price', 'status', 'sale_date']
    list_filter = ['status', 'sale_date']
    search_fields = ['property__title', 'buyer__username', 'buyer__email']
    readonly_fields = ['sale_date', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Sale Information', {
            'fields': ('property', 'buyer', 'referring_agent', 'sale_price', 'status')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'transaction_reference')
        }),
        ('Notes', {
            'fields': ('notes', 'admin_notes')
        }),
        ('Timestamps', {
            'fields': ('sale_date', 'completed_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_cancelled']
    
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        for sale in queryset:
            sale.status = 'completed'
            sale.completed_at = timezone.now()
            sale.save()
            # This will trigger commission creation
            sale.create_commission()
        self.message_user(request, f"{queryset.count()} sales marked as completed and commissions created.")
    mark_as_completed.short_description = "Mark selected sales as completed"
    
    def mark_as_cancelled(self, request, queryset):
        queryset.update(status='cancelled')
        self.message_user(request, f"{queryset.count()} sales marked as cancelled.")
    mark_as_cancelled.short_description = "Mark selected sales as cancelled"

    def save_model(self, request, obj, form, change):
        # Auto-populate referring agent from buyer's profile if not set
        if not obj.referring_agent and obj.buyer:
            try:
                from shop.models import CustomerProfile
                profile = CustomerProfile.objects.get(user=obj.buyer)
                if profile.referred_by:
                    obj.referring_agent = profile.referred_by
            except CustomerProfile.DoesNotExist:
                pass
        super().save_model(request, obj, form, change)


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ['agent', 'sale', 'commission_amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['agent__user__username', 'sale__property__title']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Commission Details', {
            'fields': ('agent', 'sale', 'commission_amount', 'commission_rate', 'status')
        }),
        ('Approval', {
            'fields': ('approved_by', 'approved_at')
        }),
        ('Payment', {
            'fields': ('paid_at', 'payment_reference', 'payment_method')
        }),
        ('Notes', {
            'fields': ('admin_notes', 'rejection_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_commissions', 'mark_as_paid', 'reject_commissions']
    
    def approve_commissions(self, request, queryset):
        for commission in queryset.filter(status='pending'):
            commission.approve(request.user)
        self.message_user(request, f"{queryset.count()} commissions approved.")
    approve_commissions.short_description = "Approve selected commissions"
    
    def mark_as_paid(self, request, queryset):
        for commission in queryset.filter(status='approved'):
            commission.mark_as_paid()
        self.message_user(request, f"{queryset.count()} commissions marked as paid.")
    mark_as_paid.short_description = "Mark selected commissions as paid"
    
    def reject_commissions(self, request, queryset):
        for commission in queryset.filter(status='pending'):
            commission.reject("Rejected by admin")
        self.message_user(request, f"{queryset.count()} commissions rejected.")
    reject_commissions.short_description = "Reject selected commissions"


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'user', 'city', 'state', 'is_verified', 'is_active', 'created_at']
    list_filter = ['is_verified', 'is_active', 'state', 'created_at']
    search_fields = ['company_name', 'user__username', 'user__email', 'registration_number']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'company_name', 'registration_number')
        }),
        ('Verification Status', {
            'fields': ('verification_status', 'can_post_properties', 'rejection_reason')
        }),
        ('CAC Verification', {
            'fields': ('rc_number', 'cac_verified', 'cac_verification_date')
        }),
        ('Verification Documents', {
            'fields': ('cac_certificate', 'utility_bill', 'business_address_proof')
        }),
        ('Contact Information', {
            'fields': ('company_email', 'company_phone', 'address', 'city', 'state', 'country')
        }),
        ('Company Details', {
            'fields': ('description', 'website')
        }),
        ('Social Media', {
            'fields': ('facebook_page', 'linkedin_page', 'instagram_page', 'x_page'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_verified')
        }),
        ('Staff Review', {
            'fields': ('verified_by', 'verified_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['approve_companies', 'reject_companies']

    def approve_companies(self, request, queryset):
        from django.utils import timezone
        queryset.update(
            verification_status='verified',
            can_post_properties=True,
            verified_by=request.user,
            verified_at=timezone.now(),
            is_verified=True
        )
        self.message_user(request, f"{queryset.count()} companies approved.")
    approve_companies.short_description = "Approve selected companies"

    def reject_companies(self, request, queryset):
        queryset.update(verification_status='rejected', can_post_properties=False)
        self.message_user(request, f"{queryset.count()} companies rejected.")
    reject_companies.short_description = "Reject selected companies"


@admin.register(VerificationLog)
class VerificationLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'verification_type', 'status', 'api_provider', 'is_match', 'created_at']
    list_filter = ['verification_type', 'status', 'api_provider', 'is_match', 'created_at']
    search_fields = ['user__username', 'user__email', 'error_message']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Verification Details', {
            'fields': ('user', 'verification_type', 'status', 'api_provider')
        }),
        ('Results', {
            'fields': ('is_match', 'confidence_score', 'error_message')
        }),
        ('Metadata', {
            'fields': ('notes', 'created_at')
        }),
    )
