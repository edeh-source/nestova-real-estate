import os
import random
import urllib.request
import tempfile
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.core.files import File
from django.utils import timezone
from blogs.models import Post, Category, Author

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate the blogs app with 20 sample posts and images'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting blog population...')

        # Ensure User exists
        user = User.objects.first()
        if not user:
            self.stdout.write('No user found. Creating a superuser...')
            try:
                user = User.objects.create_superuser('admin', 'admin@example.com', 'admin')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to create user: {e}"))
                return

        # Ensure Author exists
        # Check if user.posts exists (related_name="posts")
        try:
            author = user.posts
            self.stdout.write(f'Found existing Author profile for {user.username}')
        except AttributeError:
             # Or it might be that related_name is not set or access fails if not exists
             # OneToOneField reverse access raises generic exception if not found?
             pass
        except Exception:
             pass
        
        # Better use get_or_create on Author model directly
        author, created = Author.objects.get_or_create(user=user)
        if created:
            self.stdout.write(f'Created Author profile for {user.username}')
            # author.bio could be set
            author.bio = "<p>I am a sample author.</p>"
            author.save()

        # Create Categories
        categories_names = ['Technology', 'Lifestyle', 'Travel', 'Food', 'Coding', 'Real Estate', 'Design', 'Business']
        category_objs = []
        for cat_name in categories_names:
            cat, created = Category.objects.get_or_create(
                name=cat_name, 
                defaults={'slug': slugify(cat_name)}
            )
            category_objs.append(cat)
            if created:
                self.stdout.write(f'Created category: {cat_name}')

        # Image URLs (Lorem Picsum)
        # Using specific IDs to ensure valid images, or random query
        image_url_base = 'https://picsum.photos/800/600?random='

        # Create Posts
        created_count = 0
        for i in range(1, 21):
            title = f"Amazing Blog Post {i} - {random.randint(1000, 9999)}"
            # Ensure title is not too long or duplicated (random int helps)
            
            slug = slugify(title)
            
            # Check if slug exists
            if Post.objects.filter(slug=slug).exists():
                continue

            category = random.choice(category_objs)
            
            self.stdout.write(f"Creating post {i}: {title}")
            
            # Download image
            img_temp = tempfile.NamedTemporaryFile(delete=True)
            try:
                # Add a unique random param to get different images
                current_img_url = f"{image_url_base}{i}"
                urllib.request.urlretrieve(current_img_url, img_temp.name)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Failed to download image for post {i}: {e}. Skipping image."))
                # Continue without image or with empty image? 
                # Model says blank=True, null=True, so it's fine.
                img_temp = None

            post = Post(
                category=category,
                name=title,
                slug=slug,
                author=author,
                status=Post.Status.PUBLISHED, # "Published"
                text=f"""
                <p>Welcome to <strong>{title}</strong>.</p>
                <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.</p>
                <p>Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.</p>
                <p>Category: {category.name}</p>
                """,
                publish=timezone.now()
            )
            
            if img_temp:
                # Save with a filename
                post.image.save(f"blog_post_{i}.jpg", File(img_temp), save=True)
                img_temp.close()
            else:
                post.save()
            
            created_count += 1
            self.stdout.write(self.style.SUCCESS(f"Saved post: {title}"))

        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} blog posts!'))
