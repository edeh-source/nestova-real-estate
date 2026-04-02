from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from ckeditor.fields import RichTextField
from django.urls import reverse


User = get_user_model()

class Category(models.Model):
    name = models.CharField(max_length=256, db_index=True, unique=True)
    slug = models.SlugField(max_length=256, db_index=True, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'category'
        verbose_name_plural = 'categories'
    
    
    
class Author(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="author_profile")
    bio = RichTextField(blank=True)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    
    def __str__(self):
        return str(self.user.username)
    
    
    
    
class Post(models.Model):
    class Status(models.TextChoices):
        PUBLISHED = "published", "Published"
        DRAFT = "draft", "Draft"
    
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="posts")
    name = models.CharField(max_length=256, db_index=True, unique=True)
    slug = models.SlugField(max_length=256, db_index=True, unique_for_date='publish')
    publish = models.DateTimeField(default=timezone.now)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='posts')
    image = models.ImageField(upload_to="users_image", blank=True, null=True)
    status = models.CharField(max_length=100, choices=Status.choices, default=Status.DRAFT)
    text = RichTextField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    
    def get_absolute_url(self):
        return reverse("blog_details", args=[self.slug, self.publish.year, self.publish.month, self.publish.day])
    
    
    
    
class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments")
    text = models.TextField()    
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    
    def __str__(self):
        return f"{self.user}'s comment {self.text} on {self.post.name}"
    