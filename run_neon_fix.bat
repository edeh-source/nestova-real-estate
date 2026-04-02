@echo off
echo ========================================
echo Neon PostgreSQL Migration Fix
echo ========================================
echo.
echo Running fix script on Railway (connected to Neon)...
echo.

railway run python fix_production_migration.py

echo.
echo ========================================
echo.
echo If the fix was successful, now redeploy:
echo   Option 1: Push to git (triggers auto-deploy)
echo   Option 2: Redeploy in Railway dashboard
echo.
echo ========================================
pause
