"""
Script to fix the slug migration issue on Railway production
This script safely handles the case where the migration partially ran
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nestova.settings')
django.setup()

from django.db import connection

def fix_production_migration():
    """Fix the partially applied migration on production"""
    
    with connection.cursor() as cursor:
        print("🔍 Checking database state...")
        
        # Check if slug column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='agents_agent' AND column_name='slug';
        """)
        slug_exists = cursor.fetchone() is not None
        print(f"  Slug column exists: {slug_exists}")
        
        # Check if the LIKE index exists
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename='agents_agent' AND indexname='agents_agent_slug_0135d8cf_like';
        """)
        like_index_exists = cursor.fetchone() is not None
        print(f"  LIKE index exists: {like_index_exists}")
        
        # Check if the unique index exists
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename='agents_agent' AND indexname='agents_agent_slug_0135d8cf';
        """)
        unique_index_exists = cursor.fetchone() is not None
        print(f"  Unique index exists: {unique_index_exists}")
        
        # Check migration record
        cursor.execute("""
            SELECT id FROM django_migrations 
            WHERE app='agents' AND name='0007_agent_slug';
        """)
        migration_recorded = cursor.fetchone() is not None
        print(f"  Migration recorded: {migration_recorded}")
        
        print("\n🔧 Applying fixes...")
        
        # Drop all indexes related to slug (if they exist)
        index_names = [
            'agents_agent_slug_0135d8cf_like',
            'agents_agent_slug_0135d8cf',
            'agents_agent_slug_key',
        ]
        
        for index_name in index_names:
            try:
                cursor.execute(f"DROP INDEX IF EXISTS {index_name} CASCADE;")
                print(f"  ✓ Dropped index: {index_name}")
            except Exception as e:
                print(f"  ⚠ Could not drop {index_name}: {e}")
        
        # Drop the slug column if it exists
        if slug_exists:
            try:
                cursor.execute("ALTER TABLE agents_agent DROP COLUMN slug CASCADE;")
                print("  ✓ Dropped slug column")
            except Exception as e:
                print(f"  ⚠ Could not drop slug column: {e}")
        
        # Remove migration record
        if migration_recorded:
            try:
                cursor.execute("DELETE FROM django_migrations WHERE app='agents' AND name='0007_agent_slug';")
                print("  ✓ Removed migration record")
            except Exception as e:
                print(f"  ⚠ Could not remove migration record: {e}")
        
        # Commit changes
        connection.commit()
        
        print("\n✅ Database cleanup complete!")
        print("\n📝 Next steps:")
        print("1. Run: python manage.py migrate agents")
        print("2. This will apply the 0007_agent_slug migration cleanly")

if __name__ == '__main__':
    try:
        fix_production_migration()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
