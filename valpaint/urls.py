from django.urls import path
from . import views



urlpatterns = [
    path('', views.valpaint_home, name='valpaint_home'),

    path('products/', views.product_list, name='product_list'),

    path('products/category/<slug:slug>/', views.category_view, name='category'),

    path('products/<slug:slug>/', views.product_detail,   name='product_detail'),

    path('enquire/', views.submit_enquiry,   name='submit_enquiry'),
]