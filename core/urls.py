from django.urls import path
from . import views


urlpatterns = [
    path("about/", views.about_page, name="about"),
    path("contact/", views.contact, name="contact"),
    path("agents/", views.agents, name="agents"),
    path("agent-details/", views.agents_details, name="agent_details"),
    path("properties-details/", views.properties_details, name="properties_details"),
    path("service/", views.service, name="service"),
    path("service-details/", views.service_detail_page, name="service_details"),
    path("dashboard/", views.dashboard_user, name="dashboard"),
    path("privacy-policy/", views.privacy_policy, name="privacy_policy"),
    
    
]
