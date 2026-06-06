from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages

from .models import ValpaintProduct, ProductCategory, Finish
from .forms  import ValpaintEnquiryForm



def valpaint_home(request):
    """Main Valpaint × Nestova partnership landing page."""
    categories    = ProductCategory.objects.prefetch_related('products').order_by('sort_order')
    featured      = ValpaintProduct.objects.filter(
                        is_featured=True, is_active=True
                    ).select_related('category').prefetch_related('finishes')[:6]
    all_finishes  = Finish.objects.all()
    enquiry_form  = ValpaintEnquiryForm()

    context = {
        'categories':   categories,
        'featured':     featured,
        'all_finishes': all_finishes,
        'enquiry_form': enquiry_form,
        'page_title':   'Valpaint — Premium Italian Decorative Paints',
        'active_nav':   'valpaint',
    }
    return render(request, 'valpaint/home.html', context)


# ── Product catalogue ─────────────────────────────────────────────────────────

def product_list(request):
    """Filterable product catalogue."""
    qs = ValpaintProduct.objects.filter(is_active=True).select_related(
            'category').prefetch_related('finishes')

    # Filters from GET params
    category_slug = request.GET.get('category', '')
    finish_slug   = request.GET.get('finish', '')
    use_type      = request.GET.get('use', '')       # interior / exterior / both
    q             = request.GET.get('q', '').strip()

    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    if finish_slug:
        qs = qs.filter(finishes__slug=finish_slug)
    if use_type:
        if use_type in ('interior', 'exterior'):
            qs = qs.filter(category__use_type__in=[use_type, 'both'])
        else:
            qs = qs.filter(category__use_type=use_type)
    if q:
        qs = qs.filter(name__icontains=q)

    qs = qs.distinct()

    context = {
        'products':     qs,
        'categories':   ProductCategory.objects.all(),
        'all_finishes': Finish.objects.all(),
        'active_cat':   category_slug,
        'active_fin':   finish_slug,
        'active_use':   use_type,
        'search_query': q,
        'page_title':   'All Valpaint Products',
        'active_nav':   'valpaint',
    }
    return render(request, 'valpaint/product_list.html', context)


def category_view(request, slug):
    """Products within a single category."""
    category = get_object_or_404(ProductCategory, slug=slug)
    products = ValpaintProduct.objects.filter(
        category=category, is_active=True
    ).prefetch_related('finishes')

    context = {
        'category':   category,
        'products':   products,
        'page_title': f'Valpaint — {category.name}',
        'active_nav': 'valpaint',
    }
    return render(request, 'valpaint/category.html', context)


def product_detail(request, slug):
    """Single product page with enquiry form."""
    product      = get_object_or_404(ValpaintProduct, slug=slug, is_active=True)
    related      = ValpaintProduct.objects.filter(
                       category=product.category, is_active=True
                   ).exclude(pk=product.pk)[:4]
    enquiry_form = ValpaintEnquiryForm(initial={'product': product})

    context = {
        'product':      product,
        'related':      related,
        'enquiry_form': enquiry_form,
        'page_title':   f'{product.name} — Valpaint at Nestova',
        'active_nav':   'valpaint',
    }
    return render(request, 'valpaint/product_detail.html', context)


# ── Enquiry submission ────────────────────────────────────────────────────────

@require_POST
def submit_enquiry(request):
    """Handles the enquiry / quote-request form (AJAX or standard POST)."""
    product_slug = request.POST.get('product_slug', '')
    product      = None
    if product_slug:
        product = ValpaintProduct.objects.filter(slug=product_slug).first()

    form = ValpaintEnquiryForm(request.POST)

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if form.is_valid():
        enquiry          = form.save(commit=False)
        enquiry.product  = product
        enquiry.save()

        if is_ajax:
            return JsonResponse({'status': 'ok',
                                 'message': 'Thank you! We\'ll be in touch shortly.'})

        messages.success(request,
                         'Thank you for your enquiry. Our team will contact you shortly.')
        redirect_url = product.get_absolute_url() if product else 'valpaint:home'
        return redirect(redirect_url)

    # Invalid
    if is_ajax:
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)

    # Re-render the page with errors
    if product:
        return product_detail(request._wrapped if hasattr(request, '_wrapped') else request,
                              slug=product_slug)
    return redirect('valpaint:home')