@echo off
echo ========================================
echo Railway Production Migration Fix
echo ========================================
echo.

echo Step 1: Logging into Railway...
railway login
echo.

echo Step 2: Linking to your project...
railway link
echo.

echo Step 3: Running the fix script...
railway run python fix_production_migration.py
echo.

echo Step 4: Applying the migration...
railway run python manage.py migrate agents
echo.

echo Step 5: Verifying migrations...
railway run python manage.py showmigrations agents
echo.

echo ========================================
echo Fix Complete!
echo ========================================
pause
