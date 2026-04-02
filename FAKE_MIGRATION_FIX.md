# 🚨 CRITICAL FIX - Fake the Migration First

## The Real Problem

Railway runs migrations **automatically** during deployment, so the error happens BEFORE we can fix it. We need to **fake the migration** first, then fix the database.

---

## ✅ **SOLUTION: Fake Migration Then Fix**

### **Step 1: Fake the Migration on Railway**

This tells Django the migration is already applied (even though it failed):

```bash
railway run python manage.py migrate agents 0007 --fake
```

This will mark the migration as "done" without actually running it.

---

### **Step 2: Now Fix the Database State**

Run the fix script to clean up the partial migration:

```bash
railway run python fix_production_migration.py
```

---

### **Step 3: Manually Apply the Migration Properly**

Now that the database is clean and Django thinks the migration is done, we need to actually apply it:

```bash
# First, fake-reverse the migration
railway run python manage.py migrate agents 0006

# Then apply it for real
railway run python manage.py migrate agents 0007
```

---

## 🎯 **All-in-One Command**

Or run all steps at once:

```bash
railway run python manage.py migrate agents 0007 --fake && railway run python fix_production_migration.py && railway run python manage.py migrate agents 0006 && railway run python manage.py migrate agents 0007
```

---

## ⚠️ **If That Doesn't Work: Nuclear Option**

If the above still fails, we need to use Neon SQL Editor directly:

### Go to Neon Console

1. Open [console.neon.tech](https://console.neon.tech)
2. Select your project
3. Click "SQL Editor"
4. Run this SQL:

```sql
-- Drop everything related to slug
DROP INDEX IF EXISTS agents_agent_slug_0135d8cf_like CASCADE;
DROP INDEX IF EXISTS agents_agent_slug_0135d8cf CASCADE;
DROP INDEX IF EXISTS agents_agent_slug_key CASCADE;
ALTER TABLE agents_agent DROP COLUMN IF EXISTS slug CASCADE;

-- Mark migration as NOT applied
DELETE FROM django_migrations WHERE app='agents' AND name='0007_agent_slug';
```

5. Then run:

```bash
railway run python manage.py migrate agents
```

---

## 📝 **Why This Works**

- **Faking** tells Django to skip running the migration
- **Cleaning** removes the broken database state
- **Re-running** applies the migration properly to a clean state

---

**Try Step 1 first** (fake the migration) and let me know what happens!
