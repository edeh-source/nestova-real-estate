from django.contrib import admin
from .models import CommunityEvent


@admin.register(CommunityEvent)
class CommunityEventAdmin(admin.ModelAdmin):
    list_display  = ('name', 'event_date', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    ordering      = ('order', '-event_date')