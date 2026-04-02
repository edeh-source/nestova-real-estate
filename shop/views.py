from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Avg, Count
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from decimal import Decimal
from .models import (
    Product, Category, Cart, CartItem, Order, OrderItem,
    Review, Wishlist, CustomerProfile, Newsletter
)
import json
import requests
import logging

logger = logging.getLogger(__name__)


# ===========================
# Helper Functions
# ===========================

def calculate_shipping(state):
    """Calculate shipping cost based on state (Option 1: State-based pricing)"""
    # Convert to lowercase for case-insensitive comparison
    state_lower = state.lower().strip()
    
    # Major cities - lower shipping cost
    if state_lower in ['lagos', 'abuja', 'fct']:
        return Decimal('2000.00')
    
    # South-South and South-East states
    elif state_lower in ['rivers', 'delta', 'akwa ibom', 'cross river', 'bayelsa', 'edo',
                          'anambra', 'enugu', 'imo', 'abia', 'ebonyi']:
        return Decimal('3000.00')
    
    # South-West states (excluding Lagos)
    elif state_lower in ['ogun', 'oyo', 'osun', 'ondo', 'ekiti']:
        return Decimal('2500.00')
    
    # North-Central states
    elif state_lower in ['kwara', 'kogi', 'nasarawa', 'plateau', 'benue', 'niger']:
        return Decimal('3500.00')
    
    # North-West and North-East states (farther regions)
    elif state_lower in ['kano', 'kaduna', 'katsina', 'sokoto', 'kebbi', 'zamfara', 'jigawa',
                          'borno', 'yobe', 'adamawa', 'bauchi', 'gombe', 'taraba']:
        return Decimal('5000.00')
    
    # Default shipping for any other location
    else:
        return Decimal('5000.00')


def send_order_confirmation_email(order):
    """Send order confirmation email to customer"""
    try:
        subject = f'Order Confirmation - {order.order_number}'
        
        # Render HTML email
        html_message = render_to_string('shop/email/order_confirmation.html', {
            'order': order,
            'user': order.user,
        })
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Error sending order confirmation email for order {order.order_number}: {e}", exc_info=True)
        return False


def send_payment_success_email(order):
    """Send payment success email to customer"""
    try:
        subject = f'Payment Confirmed - {order.order_number}'

        # Build absolute URL without needing request object
        order_path = reverse('shop:order_detail', args=[order.id])
        order_url = f"{settings.SITE_URL.rstrip('/')}{order_path}"

        # Render HTML email
        html_message = render_to_string('shop/email/payment_success.html', {
            'order': order,
            'user': order.user,
            'order_url': order_url,
        })
        plain_message = strip_tags(html_message)

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Error sending payment success email for order {order.order_number}: {e}", exc_info=True)
        return False

# ===========================
# Product Views
# ===========================

def product_list(request):
    """Display all products with filtering and sorting"""
    products = Product.objects.filter(is_available=True).select_related('category')
    
    # Search functionality
    query = request.GET.get('q', '')
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(brand__icontains=query)
        )
    
    # Filter by category
    category_slug = request.GET.get('category')
    if category_slug:
        products = products.filter(category__slug=category_slug)
    
    # Filter by product type
    product_type = request.GET.get('type')
    if product_type:
        products = products.filter(product_type=product_type)
    
    # Filter by price range
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)
    
    # Filter by brand
    brand = request.GET.get('brand')
    if brand:
        products = products.filter(brand=brand)
    
    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    valid_sorts = ['price', '-price', 'name', '-name', '-created_at', 'views_count']
    if sort_by in valid_sorts:
        products = products.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(products, 12)  # 12 products per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get categories and brands for filters
    categories = Category.objects.filter(is_active=True)
    brands = Product.objects.values_list('brand', flat=True).distinct()
    
    context = {
        'products': page_obj,
        'categories': categories,
        'brands': brands,
        'query': query,
        'current_category': category_slug,
        'current_sort': sort_by,
    }
    return render(request, 'shop/product_list.html', context)


def product_detail(request, slug):
    """Display single product details"""
    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related(
            'images', 'specifications', 
        ),
        slug=slug
    )
    
    # Increment view count
    product.views_count += 1
    product.save(update_fields=['views_count'])
    
    # Get related products
    related_products = Product.objects.filter(
        category=product.category,
        is_available=True
    ).exclude(id=product.id)[:4]
    
    # Get approved reviews
    reviews = product.product_reviews.filter(is_approved=True).select_related('user')
    
    # Check if user has this in wishlist
    in_wishlist = False
    if request.user.is_authenticated:
        in_wishlist = Wishlist.objects.filter(user=request.user, product=product).exists()
    
    context = {
        'product': product,
        'related_products': related_products,
        'reviews': reviews,
        'in_wishlist': in_wishlist,
        'average_rating': product.get_average_rating(),
        'reviews_count': reviews.count(),
    }
    return render(request, 'shop/product_detail.html', context)


def category_products(request, slug):
    """Display products in a specific category"""
    category = get_object_or_404(Category, slug=slug, is_active=True)
    products = Product.objects.filter(
        category=category,
        is_available=True
    ).select_related('category')
    
    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'category': category,
        'products': page_obj,
    }
    return render(request, 'shop/category_products.html', context)


def featured_products(request):
    """Display featured products"""
    products = Product.objects.filter(
        is_featured=True,
        is_available=True
    ).select_related('category')[:8]
    
    context = {
        'products': products,
        'title': 'Featured Products'
    }
    return render(request, 'shop/featured_products.html', context)


def bestsellers(request):
    """Display bestselling products"""
    products = Product.objects.filter(
        is_bestseller=True,
        is_available=True
    ).select_related('category')[:8]
    
    context = {
        'products': products,
        'title': 'Best Sellers'
    }
    return render(request, 'shop/bestsellers.html', context)


# ===========================
# Cart Views
# ===========================

def get_or_create_cart(request):
    """Helper function to get or create cart for user or session"""
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key)
    return cart


def cart_view(request):
    """Display shopping cart"""
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related('product').all()
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'cart_total': cart.get_total_price(),
        'cart_count': cart.get_total_items(),
    }
    return render(request, 'shop/cart.html', context)


def cart_count(request):
    """API endpoint to get cart count"""
    cart = get_or_create_cart(request)
    return JsonResponse({'count': cart.get_total_items()})


@require_POST
def add_to_cart(request, product_id):
    """Add product to cart"""
    product = get_object_or_404(Product, id=product_id, is_available=True)
    
    if not product.is_in_stock():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Product is out of stock'})
        messages.error(request, 'Product is out of stock.')
        return redirect('shop:product_detail', slug=product.slug)
    
    cart = get_or_create_cart(request)
    quantity = int(request.POST.get('quantity', 1))
    
    # Check stock availability
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    
    if created:
        cart_item.quantity = quantity
    else:
        cart_item.quantity += quantity
    
    # Ensure we don't exceed stock
    if cart_item.quantity > product.stock_quantity:
        cart_item.quantity = product.stock_quantity
        message = f'Only {product.stock_quantity} items available'
    else:
        message = f'{product.name} added to cart'
    
    cart_item.save()
    
    # AJAX response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': message,
            'cart_count': cart.get_total_items(),
            'cart_total': float(cart.get_total_price())
        })
    
    messages.success(request, message)
    return redirect('shop:cart')


@require_POST
def update_cart(request, item_id):
    """Update cart item quantity"""
    cart = get_or_create_cart(request)
    cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
    
    quantity = int(request.POST.get('quantity', 1))
    
    if quantity <= 0:
        cart_item.delete()
        message = 'Item removed from cart'
    else:
        # Check stock
        if quantity > cart_item.product.stock_quantity:
            quantity = cart_item.product.stock_quantity
            message = f'Only {quantity} items available'
        else:
            message = 'Cart updated'
        
        cart_item.quantity = quantity
        cart_item.save()
    
    # AJAX response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': message,
            'cart_count': cart.get_total_items(),
            'cart_total': float(cart.get_total_price()),
            'item_total': float(cart_item.get_total_price()) if quantity > 0 else 0
        })
    
    messages.success(request, message)
    return redirect('shop:cart')


@require_POST
def remove_from_cart(request, item_id):
    """Remove item from cart"""
    cart = get_or_create_cart(request)
    cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
    product_name = cart_item.product.name
    cart_item.delete()
    
    # AJAX response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f'{product_name} removed from cart',
            'cart_count': cart.get_total_items(),
            'cart_total': float(cart.get_total_price())
        })
    
    messages.success(request, f'{product_name} removed from cart')
    return redirect('cart')


def clear_cart(request):
    """Clear all items from cart"""
    cart = get_or_create_cart(request)
    cart.items.all().delete()
    
    messages.success(request, 'Cart cleared')
    return redirect('shop:cart')


# ===========================
# Checkout & Order Views
# ===========================

@login_required
def checkout(request):
    """Checkout page"""
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related('product').all()
    
    if not cart_items:
        messages.warning(request, 'Your cart is empty')
        return redirect('shop:cart')
    
    # Get or create customer profile
    profile, created = CustomerProfile.objects.get_or_create(user=request.user)
    
    # Calculate subtotal
    subtotal = cart.get_total_price()
    
    # Default values for initial page load
    shipping_cost = Decimal('0.00')
    tax = subtotal * Decimal('0.075')  # 7.5% tax
    total = subtotal + tax
    
    if request.method == 'POST':
        # Get shipping state and calculate shipping
        state = request.POST.get('state', '')
        shipping_cost = calculate_shipping(state)
        tax = subtotal * Decimal('0.075')  # 7.5% tax
        total = subtotal + shipping_cost + tax
        
        # Get full name safely
        full_name = f"{request.user.first_name} {request.user.last_name}".strip()
        if not full_name:
            full_name = request.user.username
            
        # Process order
        order = Order.objects.create(
            user=request.user,
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            tax=tax,
            total_amount=total,
            shipping_name=request.POST.get('first_name', full_name) + ' ' + request.POST.get('last_name', ''),
            shipping_phone=request.POST.get('phone_number', ''),
            shipping_address_line1=request.POST.get('address', ''),
            shipping_address_line2='',
            shipping_city=request.POST.get('city', ''),
            shipping_state=state,
            shipping_postal_code='',
            shipping_country='Nigeria',
            payment_method=request.POST.get('payment_method', 'paystack'),
            customer_notes=request.POST.get('notes', '')
        )
        
        # Create order items
        for cart_item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                product_name=cart_item.product.name,
                product_sku=cart_item.product.sku,
                quantity=cart_item.quantity,
                unit_price=cart_item.product.get_price(),
                total_price=cart_item.get_total_price()
            )
            
            # Reduce stock
            product = cart_item.product
            product.stock_quantity -= cart_item.quantity
            product.save()
        
        # Clear cart
        cart.items.all().delete()
        
        # Send order confirmation email
        send_order_confirmation_email(order)
        
        # Check payment method
        payment_method = request.POST.get('payment_method', 'paystack')
        
        if payment_method == 'paystack':
            # Redirect to payment initialization
            return redirect('shop:initialize_payment', order_id=order.id)
        else:
            # Cash on delivery - go directly to confirmation
            messages.success(request, f'Order {order.order_number} placed successfully!')
            return redirect('shop:order_confirmation', order_id=order.id)
    
    context = {
        'cart_items': cart_items,
        'profile': profile,
        'subtotal': subtotal,
        'shipping_cost': shipping_cost,
        'tax': tax,
        'total': total,
    }
    return render(request, 'shop/checkout.html', context)


def order_confirmation(request, order_id):
    """Order confirmation page - Accessible without login for payment callbacks"""
    # Try to get order, don't filter by user to allow callback access
    order = get_object_or_404(Order, id=order_id)
    
    # If user is authenticated, verify they own the order (security check)
    if request.user.is_authenticated and order.user != request.user:
        messages.error(request, 'You do not have permission to view this order.')
        return redirect('shop:order_list')
    
    context = {
        'order': order,
    }
    return render(request, 'shop/order_confirmation.html', context)



def order_list(request):
    """List user's orders"""
    if not request.user.is_authenticated:
        return redirect('login')
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'orders': page_obj,
    }
    return render(request, 'shop/order_list.html', context)


@login_required
def order_detail(request, order_id):
    """Order detail page"""
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'),
        id=order_id,
        user=request.user
    )
    
    context = {
        'order': order,
    }
    return render(request, 'shop/order_detail.html', context)


# ===========================
# Review Views
# ===========================

@login_required
@require_POST
def submit_review(request, product_id):
    """Submit product review"""
    product = get_object_or_404(Product, id=product_id)
    
    # Check if user has already reviewed
    if Review.objects.filter(user=request.user, product=product).exists():
        messages.warning(request, 'You have already reviewed this product')
        return redirect('shop:product_detail', slug=product.slug)
    
    # Check if user has purchased this product
    has_purchased = OrderItem.objects.filter(
        order__user=request.user,
        product=product,
        order__status='delivered'
    ).exists()
    
    rating = int(request.POST.get('rating', 5))
    title = request.POST.get('title', '')
    comment = request.POST.get('comment', '')
    
    Review.objects.create(
        user=request.user,
        product=product,
        rating=rating,
        title=title,
        comment=comment,
        is_verified_purchase=has_purchased
    )
    
    messages.success(request, 'Thank you for your review! It will be published after moderation.')
    return redirect('shop:product_detail', slug=product.slug)


# ===========================
# Wishlist Views
# ===========================

@login_required
def wishlist(request):
    """Display user's wishlist"""
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    
    context = {
        'wishlist_items': wishlist_items,
    }
    return render(request, 'shop/wishlist.html', context)


@login_required
@require_POST
def add_to_wishlist(request, product_id):
    """Add product to wishlist"""
    product = get_object_or_404(Product, id=product_id)
    
    wishlist_item, created = Wishlist.objects.get_or_create(
        user=request.user,
        product=product
    )
    
    if created:
        message = f'{product.name} added to wishlist'
    else:
        message = f'{product.name} is already in your wishlist'
    
    # AJAX response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': message,
            'created': created
        })
    
    messages.success(request, message)
    return redirect('product_detail', slug=product.slug)


@login_required
@require_POST
def remove_from_wishlist(request, product_id):
    """Remove product from wishlist"""
    product = get_object_or_404(Product, id=product_id)
    
    wishlist_item = Wishlist.objects.filter(user=request.user, product=product)
    if wishlist_item.exists():
        wishlist_item.delete()
        message = f'{product.name} removed from wishlist'
    else:
        message = 'Product not in wishlist'
    
    # AJAX response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': message
        })
    
    messages.success(request, message)
    return redirect('wishlist')


# ===========================
# Profile Views
# ===========================

@login_required
def profile(request):
    """User comprehensive dashboard"""
    profile, created = CustomerProfile.objects.get_or_create(user=request.user)
    
    # Handle Profile Update
    if request.method == 'POST':
        # Check if it's a profile update form
        if 'update_profile' in request.POST:
            profile.phone = request.POST.get('phone', '')
            profile.address_line1 = request.POST.get('address_line1', '')
            profile.city = request.POST.get('city', '')
            profile.state = request.POST.get('state', '')
            
            if 'profile_image' in request.FILES:
                profile.profile_image = request.FILES['profile_image']
            
            profile.save()
            
            # Update User model fields too
            user = request.user
            user.first_name = request.POST.get('first_name', user.first_name)
            user.last_name = request.POST.get('last_name', user.last_name)
            # handle email if needed, but usually email change requires verification
            user.save()
            
            messages.success(request, 'Profile updated successfully')
            return redirect('shop:profile')

    # Fetch Data for Dashboard Tabs
    from property.models import Property
    from bookings.models import Booking
    from listings.models import SavedProperty, Notification, UserSubscription
    
    # 1. My Properties (Real Estate Listings)
    my_properties = Property.objects.filter(listed_by=request.user).order_by('-created_at')
    
    # 2. My Bookings (Appointments/Rental Bookings)
    my_bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    
    # 3. Saved Properties (Wishlist)
    saved_properties = SavedProperty.objects.filter(user=request.user).select_related('property')
    
    # 4. Notifications
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:20]
    
    # 5. Orders (Shop)
    recent_orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    # 6. Subscription Status
    subscription = UserSubscription.objects.filter(user=request.user).first()
    
    # Fallback for subscription if not exists
    if not subscription:
        # Create default if possible or just pass None
        pass

    # Get agent profile if exists
    agent_profile = getattr(request.user, 'agent_profile', None)
    
    # Agent-specific data
    agent_data = {}
    if agent_profile:
        from agents.models import Commission, PropertySale
        
        # Get downlines (agents referred by this agent)
        downlines = agent_profile.downlines.filter(is_active=True).select_related('user')
        print("this is the agent downlines", downlines)
        
        # Get commissions
        commissions = agent_profile.commissions.all().select_related('sale__property').order_by('-created_at')
        pending_commissions = commissions.filter(status='pending')
        approved_commissions = commissions.filter(status='approved')
        paid_commissions = commissions.filter(status='paid')
        
        # Get referred sales
        referred_sales = agent_profile.referred_sales.all().select_related('property', 'buyer').order_by('-created_at')
        
        # Calculate totals
        total_commission_earned = agent_profile.get_paid_commission()
        pending_commission_amount = agent_profile.get_pending_commission()
        approved_commission_amount = agent_profile.get_approved_commission()
        
        agent_data = {
            'downlines': downlines,
            'downline_count': downlines.count(),
            'commissions': commissions[:10],  # Recent 10
            'pending_commissions': pending_commissions,
            'approved_commissions': approved_commissions,
            'paid_commissions': paid_commissions,
            'referred_sales': referred_sales[:10],  # Recent 10
            'total_sales': referred_sales.count(),
            'total_commission_earned': total_commission_earned,
            'pending_commission_amount': pending_commission_amount,
            'approved_commission_amount': approved_commission_amount,
            'referral_code': agent_profile.referral_code,
        }

    context = {
        'profile': profile,
        'agent_profile': agent_profile,
        'agent_data': agent_data,
        'my_properties': my_properties,
        'my_bookings': my_bookings,
        'saved_properties': saved_properties,
        'notifications': notifications,
        'recent_orders': recent_orders,
        'subscription': subscription,
    }
    return render(request, 'shop/profile.html', context)


# ===========================
# Newsletter Views
# ===========================

@require_POST
def subscribe_newsletter(request):
    """Subscribe to newsletter"""
    email = request.POST.get('email', '')
    
    if not email:
        return JsonResponse({'success': False, 'message': 'Email is required'})
    
    newsletter, created = Newsletter.objects.get_or_create(email=email)
    
    if created:
        message = 'Successfully subscribed to our newsletter!'
    else:
        if newsletter.is_active:
            message = 'You are already subscribed'
        else:
            newsletter.is_active = True
            newsletter.save()
            message = 'Welcome back! You have been resubscribed'
    
    return JsonResponse({'success': True, 'message': message})


# ===========================
# Search & Filter Views
# ===========================

def search(request):
    """Advanced search"""
    query = request.GET.get('q', '')
    
    if not query:
        return redirect('product_list')
    
    products = Product.objects.filter(
        Q(name__icontains=query) |
        Q(description__icontains=query) |
        Q(brand__icontains=query) |
        Q(category__name__icontains=query),
        is_available=True
    ).select_related('category')
    
    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'products': page_obj,
        'query': query,
        'total_results': products.count(),
    }
    return render(request, 'shop/search_results.html', context)


# ===========================
# Payment Views (Paystack)
# ===========================

@login_required
def initialize_payment(request, order_id):
    """Initialize Paystack payment for an order"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Check if user has email
    if not order.user.email:
        messages.error(request, 'Please add an email address to your profile before making payment.')
        return redirect('shop:order_confirmation', order_id=order.id)
    
    # Prepare Paystack payment data
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    # Convert amount to kobo (Paystack uses kobo, not naira)
    amount_in_kobo = int(order.total_amount * 100)
    
    # Construct dynamic callback URL
    callback_url = request.build_absolute_uri(reverse('shop:verify_payment'))
    
    data = {
        "email": order.user.email,
        "amount": amount_in_kobo,
        "currency": "NGN",
        "reference": f"{order.order_number}-{order.id}",
        "callback_url": callback_url,
        "metadata": {
            "order_id": str(order.id),
            "order_number": order.order_number,
            "customer_name": order.shipping_name,
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response_data = response.json()
        
        # Debug logging
        print(f"Paystack Response Status Code: {response.status_code}")
        print(f"Paystack Response Data: {response_data}")
        
        if response_data.get('status'):
            # Save Paystack reference and access code
            order.paystack_reference = response_data['data']['reference']
            order.paystack_access_code = response_data['data']['access_code']
            order.save()
            
            # Redirect to Paystack payment page
            authorization_url = response_data['data']['authorization_url']
            print(f"Redirecting to: {authorization_url}")
            return redirect(authorization_url)
        else:
            error_message = response_data.get('message', 'Unknown error')
            print(f"Paystack Error: {error_message}")
            messages.error(request, f'Payment initialization failed: {error_message}')
            return redirect('shop:order_confirmation', order_id=order.id)
            
    except requests.exceptions.RequestException as e:
        print(f"Network Error: {str(e)}")
        messages.error(request, f'Network error: Unable to connect to payment gateway. Please try again.')
        return redirect('shop:order_confirmation', order_id=order.id)
    except Exception as e:
        print(f"Payment Error: {str(e)}")
        messages.error(request, f'Payment initialization error: {str(e)}')
        return redirect('shop:order_confirmation', order_id=order.id)

#2348039729536

def verify_payment(request):
    """Verify Paystack payment callback - No login required as this is a callback from Paystack"""
    reference = request.GET.get('reference')
    
    if not reference:
        messages.error(request, 'Invalid payment reference')
        return redirect('shop:product_list')
    
    # Verify payment with Paystack
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }
    
    try:
        response = requests.get(url, headers=headers)
        response_data = response.json()
        
        print(f"Payment Verification Response: {response_data}")
        
        if response_data.get('status') and response_data['data']['status'] == 'success':
            # Extract order number from reference (format: ORD-20251230-00002-uuid)
            # Split by '-' and reconstruct order number (first 3 parts)
            parts = reference.split('-')
            if len(parts) >= 3:
                order_number = f"{parts[0]}-{parts[1]}-{parts[2]}"
            else:
                messages.error(request, 'Invalid payment reference format')
                return redirect('shop:product_list')
            
            try:
                # Get order without user filter since callback may not have session
                order = Order.objects.get(order_number=order_number)
                
                # Check if already paid to avoid duplicate processing
                if order.payment_status == 'paid':
                    messages.info(request, f'Payment already confirmed for order {order.order_number}')
                    return redirect('shop:order_confirmation', order_id=order.id)
                
                # Update order payment status
                order.payment_status = 'paid'
                order.status = 'processing'
                order.transaction_id = str(response_data['data']['id'])
                order.paid_at = timezone.now()
                order.save()
                
                # Send payment success email
                send_payment_success_email(order)
                
                messages.success(request, f'Payment successful! Your order {order.order_number} has been confirmed.')
                return redirect('shop:order_confirmation', order_id=order.id)
                
            except Order.DoesNotExist:
                messages.error(request, 'Order not found')
                return redirect('shop:product_list')
        else:
            error_msg = response_data.get('message', 'Payment verification failed')
            print(f"Payment verification failed: {error_msg}")
            messages.error(request, f'Payment verification failed: {error_msg}. Please contact support.')
            return redirect('shop:product_list')
            
    except Exception as e:
        print(f"Payment verification error: {str(e)}")
        messages.error(request, f'Payment verification error: {str(e)}')
        return redirect('shop:product_list')