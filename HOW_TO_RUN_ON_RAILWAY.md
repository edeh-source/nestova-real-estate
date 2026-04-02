# How to Run the Fix on Railway

You have **3 options** to run the fix script on Railway. Choose the one that works best for you:

---

## Option 1: Railway CLI (Recommended - Most Control)

### Step 1: Install Railway CLI (if not already installed)

```bash
# Install via npm
npm i -g @railway/cli

# Or via PowerShell (Windows)
iwr https://railway.app/install.ps1 | iex
```

### Step 2: Login to Railway

```bash
railway login
```

This will open your browser to authenticate.

### Step 3: Link to Your Project

```bash
cd c:\Users\htdocs\nestova
railway link
```

Select your project from the list.

### Step 4: Run the Fix Script

```bash
railway run python fix_production_migration.py
```

### Step 5: Apply the Migration

```bash
railway run python manage.py migrate agents
```

### Step 6: Verify

```bash
railway run python manage.py showmigrations agents
```

---

## Option 2: Deploy and Let Railway Run It Automatically

### Step 1: Add the fix to your deployment

The file `fix_production_migration.py` is already in your project. Just commit and push:

```bash
git add fix_production_migration.py
git commit -m "Add production migration fix script"
git push
```

### Step 2: SSH into Railway

Once deployed, go to Railway Dashboard:

1. Open your project on [railway.app](https://railway.app)
2. Click on your **Django service**
3. Click on the **"..."** menu (three dots)
4. Select **"Shell"** or **"Terminal"**

### Step 3: Run the commands in Railway's terminal

```bash
python fix_production_migration.py
python manage.py migrate agents
```

---

## Option 3: Use Railway's PostgreSQL Query Console (Direct SQL)

If you prefer to fix it directly in the database:

### Step 1: Access PostgreSQL

1. Go to [railway.app](https://railway.app)
2. Open your project
3. Click on your **PostgreSQL database**
4. Click on **"Query"** tab

### Step 2: Run this SQL

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

### Step 3: Redeploy

After running the SQL, trigger a redeploy:

1. Go to your Django service
2. Click **"Deployments"**
3. Click **"Redeploy"** on the latest deployment

OR just push a small change to trigger redeploy:

```bash
git commit --allow-empty -m "Trigger redeploy after DB fix"
git push
```

---

## Which Option Should You Choose?

- **Option 1 (Railway CLI)**: Best if you want full control and can install the CLI
- **Option 2 (Railway Shell)**: Best if you don't want to install anything locally
- **Option 3 (SQL Console)**: Fastest, but requires understanding SQL

---

## After Running the Fix

Verify everything is working:

1. Check your Railway deployment logs
2. Visit your site and test agent profiles
3. Check if slugs are populated:

```bash
railway run python manage.py shell -c "from agents.models import Agent; print(f'Total agents: {Agent.objects.count()}'); print(f'Agents with slugs: {Agent.objects.exclude(slug__isnull=True).count()}')"
```

---

## Troubleshooting

### "railway: command not found"

Install the Railway CLI first (see Option 1, Step 1).

### "Project not linked"

Run `railway link` in your project directory.

### "Permission denied"

Make sure you're logged in: `railway login`

### Still getting migration errors?

Try the SQL approach (Option 3) - it's the most direct way to fix the database state.
