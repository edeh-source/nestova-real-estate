from django.db import models
from django.utils.text import slugify
from django.urls import reverse


# ── Lookup tables ────────────────────────────────────────────────────────────

class Finish(models.Model):
    """e.g. Metallic, Satin, Cement, Glitter…"""
    name       = models.CharField(max_length=100, unique=True)
    slug       = models.SlugField(max_length=120, unique=True, blank=True)
    icon       = models.CharField(max_length=60, blank=True,
                                  help_text="Bootstrap-icon class e.g. bi-stars")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ProductCategory(models.Model):
    USE_INTERIOR = 'interior'
    USE_EXTERIOR = 'exterior'
    USE_BOTH     = 'both'
    USE_CHOICES  = [
        (USE_INTERIOR, 'Interior'),
        (USE_EXTERIOR, 'Exterior'),
        (USE_BOTH,     'Interior & Exterior'),
    ]

    name        = models.CharField(max_length=120, unique=True)
    slug        = models.SlugField(max_length=140, unique=True, blank=True)
    use_type    = models.CharField(max_length=10, choices=USE_CHOICES, default=USE_INTERIOR)
    description = models.TextField(blank=True)
    icon        = models.CharField(max_length=60, blank=True,
                                   help_text="Bootstrap-icon class e.g. bi-paint-bucket")
    sort_order  = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name_plural = 'product categories'
        ordering            = ['sort_order', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('category', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ── Core product ─────────────────────────────────────────────────────────────

class ValpaintProduct(models.Model):
    # identifiers
    name         = models.CharField(max_length=200)
    slug         = models.SlugField(max_length=220, unique=True, blank=True)
    sku          = models.CharField(max_length=60, blank=True)

    # taxonomy
    category     = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='products')
    finishes     = models.ManyToManyField(Finish, blank=True, related_name='products')

    # descriptive content
    short_desc   = models.CharField(max_length=320, blank=True,
                                    verbose_name='Short description')
    description  = models.TextField(blank=True)
    applications = models.TextField(blank=True,
                                    help_text="Where / how to apply (one item per line)")
    # media
    image        = models.ImageField(upload_to='valpaint/products/', blank=True, null=True)
    image_alt    = models.CharField(max_length=200, blank=True)

    # pricing (optional — contact for quote is also fine)
    price_ngn    = models.DecimalField(max_digits=12, decimal_places=2,
                                       null=True, blank=True,
                                       verbose_name='Price (₦)')
    price_label  = models.CharField(max_length=60, blank=True,
                                    help_text="e.g. 'per 5 L tin' or 'Contact for quote'")

    # flags
    is_featured  = models.BooleanField(default=False)
    is_active    = models.BooleanField(default=True)
    in_stock     = models.BooleanField(default=True)

    # meta
    meta_title       = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=320, blank=True)

    # Valpaint source link (for reference / "learn more" linking to official docs)
    valpaint_url = models.URLField(blank=True,
                                   verbose_name='Valpaint official product URL')

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_featured', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('product_detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def application_list(self):
        """Return applications as a Python list."""
        return [a.strip() for a in self.applications.splitlines() if a.strip()]


# ── Enquiry / quote request ───────────────────────────────────────────────────

class ValpaintEnquiry(models.Model):
    STATUS_NEW       = 'new'
    STATUS_CONTACTED = 'contacted'
    STATUS_CLOSED    = 'closed'
    STATUS_CHOICES   = [
        (STATUS_NEW,       'New'),
        (STATUS_CONTACTED, 'Contacted'),
        (STATUS_CLOSED,    'Closed'),
    ]

    product      = models.ForeignKey(ValpaintProduct, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='enquiries')
    full_name    = models.CharField(max_length=140)
    email        = models.EmailField()
    phone        = models.CharField(max_length=30, blank=True)
    location     = models.CharField(max_length=200, blank=True,
                                    help_text="City / area in Nigeria")
    message      = models.TextField()
    quantity     = models.CharField(max_length=80, blank=True,
                                    help_text="e.g. '10 tins', 'whole apartment'")
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                    default=STATUS_NEW)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering           = ['-created_at']
        verbose_name       = 'Valpaint Enquiry'
        verbose_name_plural = 'Valpaint Enquiries'

    def __str__(self):
        product_name = self.product.name if self.product else 'General'
        return f"Enquiry from {self.full_name} — {product_name}"