# admin.py
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.utils.html import format_html
from django.contrib.auth import get_user_model
from agents.models import Agent
from .models import (
    State, City, PropertyType, PropertyStatus, Property,
    PropertyImage, PropertyAmenity, PropertyAmenityLink,
    Developer,
)

User = get_user_model()


class AssignAgentListedByForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    agent = forms.ModelChoiceField(
        queryset=Agent.objects.none(),
        required=False,
        label="Select Agent",
        help_text="Select agent to assign to selected properties."
    )
    listed_by = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Select Listed By (User)",
        help_text="Select user who listed these properties. If left blank and an Agent is selected, it automatically defaults to the Agent's user account."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['agent'].queryset = Agent.objects.select_related('user').order_by('user__username')
        self.fields['listed_by'].queryset = User.objects.order_by('username')


# ── Developer ────────────────────────────────────────────────────────────

class DeveloperPropertyInline(admin.TabularInline):
    model = Property
    fk_name = 'developer'
    extra = 0
    fields = ['title', 'status', 'price', 'is_active']
    readonly_fields = ['title', 'status', 'price']
    show_change_link = True
    verbose_name = "Linked Property"
    verbose_name_plural = "Linked Properties"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Developer)
class DeveloperAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'headquarters', 'founded_year', 'property_count_display',
        'is_featured', 'is_active', 'created_at'
    ]
    list_filter = ['is_featured', 'is_active', 'created_at']
    search_fields = ['name', 'tagline', 'headquarters', 'email']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at', 'logo_preview', 'banner_preview', 'founder_preview']

    fieldsets = (
        ('Identity', {
            'fields': ('name', 'slug', 'tagline', 'description')
        }),
        ('Media', {
            'fields': ('logo', 'logo_preview', 'banner_image', 'banner_preview', 'founder_image', 'founder_preview')
        }),
        ('Contact & Location', {
            'fields': ('headquarters', 'email', 'phone', 'website')
        }),
        ('Social Media', {
            'fields': ('facebook_page', 'instagram_page', 'linkedin_page', 'x_page'),
            'classes': ('collapse',)
        }),
        ('Stats', {
            'fields': ('founded_year', 'total_units_delivered')
        }),
        ('Visibility', {
            'fields': ('is_featured', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [DeveloperPropertyInline]

    def property_count_display(self, obj):
        count = obj.property_count
        return format_html(
            '<span style="font-weight:bold;color:#2e7d32">{}</span>', count
        )
    property_count_display.short_description = 'Active Properties'

    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" style="max-height:80px;border-radius:6px;" />', obj.logo.url
            )
        return "No logo uploaded"
    logo_preview.short_description = 'Logo Preview'

    def banner_preview(self, obj):
        if obj.banner_image:
            return format_html(
                '<img src="{}" style="max-height:120px;border-radius:6px;" />', obj.banner_image.url
            )
        return "No banner uploaded"
    banner_preview.short_description = 'Banner Preview'

    def founder_preview(self, obj):
        if obj.founder_image:
            return format_html(
                '<img src="{}" style="max-height:100px;border-radius:50%;border:2px solid #C9A84C;" />', obj.founder_image.url
            )
        return "No image uploaded"
    founder_preview.short_description = 'Founder Preview'


# ─────────────────────────────────────────────────────────────────────────────

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'city_count']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    
    def city_count(self, obj):
        return obj.cities.count()
    city_count.short_description = 'Cities'


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name', 'state', 'is_active', 'property_count']
    list_filter = ['state', 'is_active']
    search_fields = ['name', 'state__name']
    
    def property_count(self, obj):
        return obj.properties.count()
    property_count.short_description = 'Properties'


@admin.register(PropertyType)
class PropertyTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']


@admin.register(PropertyStatus)
class PropertyStatusAdmin(admin.ModelAdmin):
    list_display = ['name']


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ['image', 'caption', 'is_primary', 'order']


class PropertyAmenityLinkInline(admin.TabularInline):
    model = PropertyAmenityLink
    extra = 1


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'agent', 'listed_by', 'developer', 'state', 'city', 'property_type', 'status',
        'price', 'bedrooms', 'bathrooms', 'is_featured',
        'views_count', 'created_at'
    ]
    list_filter = [
        'agent', 'listed_by', 'developer', 'property_type', 'status', 'state', 'is_featured',
        'is_premium', 'is_hot', 'created_at'
    ]
    search_fields = ['title', 'description', 'address', 'city__name', 'state__name', 'agent__user__username', 'listed_by__username']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['views_count', 'created_at', 'updated_at', 'price_per_sqft']
    actions = ['assign_agent_and_listed_by']

    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'description', 'listed_by', 'agent', 'developer')
        }),
        ('Location', {
            'fields': ('state', 'city', 'address', 'zip_code')
        }),
        ('Property Details', {
            'fields': (
                'property_type', 'status', 'bedrooms', 'bathrooms', 
                'square_feet', 'lot_size', 'year_built', 'parking_spaces'
            )
        }),
        ('Pricing', {
            'fields': ('price', 'price_per_sqft')
        }),
        ('Features', {
            'fields': (
                'has_garage', 'has_pool', 'has_garden', 'has_security',
                'has_gym', 'has_balcony', 'is_furnished', 'has_ac',
                'has_heating', 'pet_friendly'
            )
        }),
        ('Media', {
            'fields': ('featured_image', 'video_url', 'virtual_tour_url')
        }),
        ('Badges & Visibility', {
            'fields': (
                'is_featured', 'is_premium', 'is_hot', 'is_new', 'is_exclusive'
            )
        }),
        ('Statistics', {
            'fields': ('views_count', 'saved_count', 'created_at', 'updated_at')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [PropertyImageInline, PropertyAmenityLinkInline]
    
    def save_model(self, request, obj, form, change):
        if not obj.listed_by:
            if obj.agent and hasattr(obj.agent, 'user'):
                obj.listed_by = obj.agent.user
            else:
                obj.listed_by = request.user
        if not obj.agent and hasattr(request.user, 'agent_profile'):
            obj.agent = request.user.agent_profile
        super().save_model(request, obj, form, change)

    @admin.action(description="Assign Agent and Listed By to selected properties")
    def assign_agent_and_listed_by(self, request, queryset):
        if 'apply' in request.POST:
            form = AssignAgentListedByForm(request.POST)
            if form.is_valid():
                agent = form.cleaned_data.get('agent')
                listed_by = form.cleaned_data.get('listed_by')

                if not listed_by and agent and hasattr(agent, 'user'):
                    listed_by = agent.user

                update_data = {}
                if agent:
                    update_data['agent'] = agent
                if listed_by:
                    update_data['listed_by'] = listed_by

                if update_data:
                    count = queryset.update(**update_data)
                    msg_parts = []
                    if agent:
                        msg_parts.append(f"Agent: {agent}")
                    if listed_by:
                        msg_parts.append(f"Listed By: {listed_by}")
                    
                    self.message_user(
                        request,
                        f"Successfully updated {count} property/properties with {', '.join(msg_parts)}.",
                        messages.SUCCESS
                    )
                else:
                    self.message_user(
                        request,
                        "No changes made because neither Agent nor Listed By was selected.",
                        messages.WARNING
                    )
                return HttpResponseRedirect(request.get_full_path())
        else:
            selected_ids = request.POST.getlist(ACTION_CHECKBOX_NAME)
            form = AssignAgentListedByForm(initial={
                '_selected_action': selected_ids
            })

        return render(
            request,
            'admin/assign_agent_listed_by.html',
            {
                'items': queryset,
                'form': form,
                'title': 'Assign Agent and Listed By',
                'action_checkbox_name': ACTION_CHECKBOX_NAME,
            }
        )



@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ['property', 'caption', 'is_primary', 'order', 'uploaded_at']
    list_filter = ['is_primary', 'uploaded_at']
    search_fields = ['property__title', 'caption']


@admin.register(PropertyAmenity)
class PropertyAmenityAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'description']
    search_fields = ['name']




