"""
Manually add slug column and populate it
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nestova.settings')
django.setup()

from django.db import connection
from django.utils.text import slugify
from agents.models import Agent

def add_slug_column():
    """Manually add slug column and populate it"""
    
    connection.set_autocommit(True)
    
    with connection.cursor() as cursor:
        print("Step 1: Adding slug column to agents_agent table...")
        
        try:
            # Add slug column (nullable, no unique constraint yet)
            cursor.execute("""
                ALTER TABLE agents_agent 
                ADD COLUMN IF NOT EXISTS slug VARCHAR(100) NULL;
            """)
            print("✓ Added slug column")
        except Exception as e:
            print(f"  Note: {e}")
        
        print("\nStep 2: Populating slugs for all agents...")
        
        # Now use Django ORM to populate slugs
        agents_updated = 0
        for agent in Agent.objects.all():
            if not agent.slug:
                base_slug = slugify(agent.user.username)
                slug = base_slug
                counter = 1
                
                # Ensure uniqueness
                while Agent.objects.filter(slug=slug).exclude(id=agent.id).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                
                agent.slug = slug
                agent.save(update_fields=['slug'])
                agents_updated += 1
                print(f"  ✓ {agent.user.username} → {slug}")
        
        print(f"\n✓ Updated {agents_updated} agents")
        
        print("\nStep 3: Adding unique constraint to slug column...")
        
        try:
            # Now add unique constraint
            cursor.execute("""
                ALTER TABLE agents_agent 
                ADD CONSTRAINT agents_agent_slug_key UNIQUE (slug);
            """)
            print("✓ Added unique constraint")
        except Exception as e:
            print(f"  Note: {e}")
        
        try:
            # Add index for LIKE queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS agents_agent_slug_like 
                ON agents_agent (slug varchar_pattern_ops);
            """)
            print("✓ Added LIKE index")
        except Exception as e:
            print(f"  Note: {e}")
    
    connection.set_autocommit(False)
    
    print("\n✅ All done! Agent URLs now use slugs like /agents/john-doe/")

if __name__ == '__main__':
    add_slug_column()
