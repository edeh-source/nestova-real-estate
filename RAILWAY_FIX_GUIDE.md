# Railway Production Migration Fix Guide

## Problem
The migration `0007_agent_slug` partially ran on Railway production, creating the index `agents_agent_slug_0135d8cf_like` but failing to complete. Now Django can't re-run the migration because the index already exists.

## Solution Steps

### Option 1: Using Railway CLI (Recommended)

1. **Connect to Railway shell:**
   ```bash
   railway run python fix_production_migration.py
   ```

2. **Apply the migration:**
   ```bash
   railway run python manage.py migrate agents
   ```

3. **Verify the fix:**
   ```bash
   railway run python manage.py showmigrations agents
   ```

### Option 2: Using Railway Dashboard SQL Console

If you have access to Railway's PostgreSQL console:

1. **Open Railway Dashboard** → Your Project → PostgreSQL → Query

2. **Run this SQL to clean up:**
   ```sql
   -- Drop indexes
   DROP INDEX IF EXISTS agents_agent_slug_0135d8cf_like CASCADE;
   DROP INDEX IF EXISTS agents_agent_slug_0135d8cf CASCADE;
   DROP INDEX IF EXISTS agents_agent_slug_key CASCADE;
   
   -- Drop column
   ALTER TABLE agents_agent DROP COLUMN IF EXISTS slug CASCADE;
   
   -- Remove migration record
   DELETE FROM django_migrations WHERE app='agents' AND name='0007_agent_slug';
   ```

3. **Then redeploy your app** - Railway will run migrations automatically

### Option 3: Using Django Shell on Railway

1. **Open Railway shell:**
   ```bash
   railway run python manage.py shell
   ```

2. **Run this Python code:**
   ```python
   from django.db import connection
   
   with connection.cursor() as cursor:
       # Drop indexes
       cursor.execute("DROP INDEX IF EXISTS agents_agent_slug_0135d8cf_like CASCADE;")
       cursor.execute("DROP INDEX IF EXISTS agents_agent_slug_0135d8cf CASCADE;")
       cursor.execute("DROP INDEX IF EXISTS agents_agent_slug_key CASCADE;")
       
       # Drop column
       cursor.execute("ALTER TABLE agents_agent DROP COLUMN IF EXISTS slug CASCADE;")
       
       # Remove migration record
       cursor.execute("DELETE FROM django_migrations WHERE app='agents' AND name='0007_agent_slug';")
       
       connection.commit()
   
   print("✅ Cleanup complete!")
   exit()
   ```

3. **Redeploy or run migrations:**
   ```bash
   railway run python manage.py migrate agents
   ```

## Verification

After applying the fix, verify everything is working:

```bash
# Check migrations
railway run python manage.py showmigrations agents

# Check if slug field exists
railway run python manage.py shell -c "from agents.models import Agent; print(Agent._meta.get_field('slug'))"

# Check if slugs are populated
railway run python manage.py shell -c "from agents.models import Agent; print(f'Agents with slugs: {Agent.objects.exclude(slug__isnull=True).count()}')"
```

## Prevention

To prevent this in the future:
1. Always test migrations locally first
2. Use `--fake-initial` flag if needed: `python manage.py migrate --fake-initial`
3. Create database backups before running migrations on production

## Troubleshooting

**If you still get errors:**

1. Check Railway logs for the exact error
2. Verify database connection is working
3. Make sure you have the latest code deployed
4. Try running with `--fake` flag: `railway run python manage.py migrate agents 0007 --fake`

**If slugs aren't populated after migration:**

Run the population script:
```bash
railway run python populate_agent_slugs.py
```
