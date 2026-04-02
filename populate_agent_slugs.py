"""
Script to populate slug field for existing Agent records
Run this before applying the migration
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nestova.settings')
django.setup()

from django.utils.text import slugify
from agents.models import Agent

def populate_agent_slugs():
    """Populate slug field for all agents without a slug"""
    agents_without_slug = Agent.objects.filter(slug__isnull=True) | Agent.objects.filter(slug='')
    
    print(f"Found {agents_without_slug.count()} agents without slugs")
    
    for agent in agents_without_slug:
        # Generate slug from username
        base_slug = slugify(agent.user.username)
        slug = base_slug
        counter = 1
        
        # Ensure uniqueness
        while Agent.objects.filter(slug=slug).exclude(id=agent.id).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        agent.slug = slug
        agent.save(update_fields=['slug'])
        print(f"✓ Updated agent {agent.user.username} with slug: {slug}")
    
    print(f"\n✅ Successfully populated slugs for {agents_without_slug.count()} agents")

if __name__ == '__main__':
    populate_agent_slugs()
