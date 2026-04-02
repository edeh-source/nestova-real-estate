"""
Django management command to clean up and apply slug migration
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nestova.settings')
django.setup()

from django.db import connection

def cleanup_and_migrate():
    """Clean up failed migration artifacts and apply fresh migration"""
    
    # Use autocommit to ensure changes are committed immediately
    connection.set_autocommit(True)
    
    with connection.cursor() as cursor:
        print("Cleaning up failed migration artifacts...")
        
        # Drop all possible index variations
        index_names = [
            'agents_agent_slug_0135d8cf_like',
            'agents_agent_slug_0135d8cf',
            'agents_agent_slug_key',
        ]
        
        for index_name in index_names:
            try:
                cursor.execute(f"DROP INDEX IF EXISTS {index_name} CASCADE;")
                print(f"✓ Dropped index {index_name}")
            except Exception as e:
                print(f"  Note: {index_name} - {e}")
        
        # Drop the slug column if it exists
        try:
            cursor.execute("ALTER TABLE agents_agent DROP COLUMN IF EXISTS slug CASCADE;")
            print("✓ Dropped column slug from agents_agent")
        except Exception as e:
            print(f"  Note: {e}")
        
        # Mark migration 0007 as not applied
        try:
            cursor.execute("DELETE FROM django_migrations WHERE app='agents' AND name='0007_agent_slug';")
            print("✓ Removed migration record for 0007_agent_slug")
        except Exception as e:
            print(f"  Note: {e}")
            
        # Mark migration 0008 as not applied (if it exists)
        try:
            cursor.execute("DELETE FROM django_migrations WHERE app='agents' AND name='0008_alter_agent_slug';")
            print("✓ Removed migration record for 0008_alter_agent_slug")
        except Exception as e:
            print(f"  Note: {e}")
    
    # Reset to default transaction mode
    connection.set_autocommit(False)
    
    print("\n✅ Cleanup complete!")
    print("\nNow run: py manage.py migrate agents")

if __name__ == '__main__':
    cleanup_and_migrate()
