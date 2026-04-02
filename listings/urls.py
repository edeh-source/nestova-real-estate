from django.urls import path
from . import views

app_name = 'listings'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('post/', views.post_property, name='post_property'),
    path('edit/<slug:slug>/', views.edit_property, name='edit_property'),
    path('pricing/', views.pricing_plans, name='pricing'),
    path('subscribe/<int:package_id>/', views.subscribe, name='subscribe'),
    path("verify/listing/package/", views.verify_payment, name="verify_payment")
]
