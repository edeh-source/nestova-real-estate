from django.urls import path
from .views import (
    ContactView, 
    NewsletterSubscribeView,
    ContactMessageAjaxView,
    NewsletterAjaxView
)

urlpatterns = [
    # Main contact page
    path('contact/', ContactView.as_view(), name='contact'),
    
    # Newsletter subscription
    path('newsletter/subscribe/', NewsletterSubscribeView.as_view(), name='newsletter_subscribe'),
    
    # AJAX endpoints (optional, for enhanced user experience)
    path('api/contact/submit/', ContactMessageAjaxView.as_view(), name='contact_ajax'),
    path('api/newsletter/subscribe/', NewsletterAjaxView.as_view(), name='newsletter_ajax'),
]