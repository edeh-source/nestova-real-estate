@echo off
echo ========================================
echo Cleaning Up Failed Slug Migration
echo ========================================
echo.

echo Running cleanup script...
python cleanup_migration.py

echo.
echo Now applying the migration...
py manage.py migrate agents

echo.
echo ========================================
echo Done!
echo ========================================
pause
