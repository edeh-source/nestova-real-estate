@echo off
echo ========================================
echo Railway Migration Fix - Fake Method
echo ========================================
echo.

echo Step 1: Faking the migration...
railway run python manage.py migrate agents 0007 --fake
echo.

echo Step 2: Cleaning up database...
railway run python fix_production_migration.py
echo.

echo Step 3: Rolling back to previous migration...
railway run python manage.py migrate agents 0006
echo.

echo Step 4: Applying migration properly...
railway run python manage.py migrate agents 0007
echo.

echo ========================================
echo Fix Complete!
echo ========================================
echo.
echo Check Railway logs to verify migration succeeded.
echo.
pause
