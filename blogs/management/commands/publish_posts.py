# Save this as: yourapp/management/commands/publish_posts.py

from django.core.management.base import BaseCommand
from blogs.models import Post  # Replace 'yourapp' with your actual app name

class Command(BaseCommand):
    help = 'Publish all draft posts'

    def handle(self, *args, **options):
        draft_posts = Post.objects.filter(status='draft')
        count = draft_posts.count()
        
        draft_posts.update(status='published')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully published {count} posts')
        )
        
        published_count = Post.objects.filter(status='published').count()
        self.stdout.write(
            self.style.SUCCESS(f'Total published posts: {published_count}')
        )