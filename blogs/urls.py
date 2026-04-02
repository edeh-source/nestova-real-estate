from django.urls import path
from . import views

urlpatterns = [
    path('', views.post_lists, name='post_list'),
    path('details/<slug:slug>/<int:year>/<int:month>/<int:day>/', views.post_details, name="blog_details")
]
