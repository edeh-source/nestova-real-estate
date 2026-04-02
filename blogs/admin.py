from django.contrib import admin
from .models import Category, Post, Author, Comment

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    list_filter = ['name', 'slug']
    prepopulated_fields = {'slug': ['name', ]}
    
    
    
@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_filter = ['user', 'active']
    list_display = ['user']
    
    
@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'publish', 'author', 'created', 'updated']
    list_filter = ['name', 'slug', 'publish', 'author']
    prepopulated_fields = {'slug': ['name', ]}   
    
    
    
@admin.register(Comment)     
class CommentAdmin(admin.ModelAdmin):
    list_display = ['post', 'user']   
    list_filter = ['post'] 