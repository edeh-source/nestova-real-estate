from django.urls import path
from . import views


app_name = 'users'

urlpatterns = [
    path("register/", views.register_page, name="register"),
    path("login/", views.login__page, name="login"),
    path("<str:username>/dashboard/", views.users__dashboard, name="dashboard"),
    path("logout/", views.users_logout, name="logout"),
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset-confirm/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('verify-identity/', views.submit_user_verification, name='submit_user_verification'),
]
