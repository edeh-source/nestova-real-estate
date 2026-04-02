from django.urls import path
from . import views




app_name = 'shop'

urlpatterns = [
    # ===========================
    # Product URLs
    # ===========================
    path('', views.product_list, name='product_list'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('category/<slug:slug>/', views.category_products, name='category_products'),
    path('featured/', views.featured_products, name='featured_products'),
    path('bestsellers/', views.bestsellers, name='bestsellers'),
    path('search/', views.search, name='search'),
    path('cart_count/', views.cart_count, name='cart_count'),
    
    # ===========================
    # Cart URLs
    # ===========================
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<uuid:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_id>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    
    # ===========================
    # Checkout & Order URLs
    # ===========================
    path('checkout/', views.checkout, name='checkout'),
    path('payment/initialize/<uuid:order_id>/', views.initialize_payment, name='initialize_payment'),
    path('payment/verify/', views.verify_payment, name='verify_payment'),
    path('order/confirmation/<uuid:order_id>/', views.order_confirmation, name='order_confirmation'),
    path('orders/', views.order_list, name='order_list'),
    path('order/<uuid:order_id>/', views.order_detail, name='order_detail'),
    
    # ===========================
    # Review URLs
    # ===========================
    path('review/submit/<uuid:product_id>/', views.submit_review, name='submit_review'),
    
    # ===========================
    # Wishlist URLs
    # ===========================
    path('wishlist/', views.wishlist, name='wishlist'),
    path('wishlist/add/<uuid:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<uuid:product_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    
    # ===========================
    # Profile URLs
    # ===========================
    path('profile/', views.profile, name='profile'),
    
    # ===========================
    # Newsletter URLs
    # ===========================
    path('newsletter/subscribe/', views.subscribe_newsletter, name='subscribe_newsletter'),
]