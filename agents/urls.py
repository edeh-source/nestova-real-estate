from django.urls import path
from . import views

app_name = 'agents'

urlpatterns = [
    path('dashboard/', views.agent_dashboard, name='agent_dashboard'),
    path("agents/signup/", views.agents_signup, name="agents_signup"),
    
    # Verification URLs
    path('verification/', views.verification_dashboard, name='verification_dashboard'),
    path('verification/submit/agent/', views.submit_agent_verification, name='submit_agent_verification'),
    path('verification/submit/company/', views.submit_company_verification, name='submit_company_verification'),
    
    # Agent Search
    path('search/', views.agent_search, name='agent_search'),
    path('search/autocomplete/', views.agent_search_autocomplete, name='agent_search_autocomplete'),

    # Agent Profile & Properties (slug-based URLs)
    path('<slug:slug>/', views.agent_profile, name='agent_profile'),
    path('<slug:slug>/properties/', views.agent_properties, name='agent_properties'),
]