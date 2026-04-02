@echo off
echo ========================================
echo Simple Solution: Fake the Migration
echo ========================================
echo.

echo This will mark the migration as applied without running it.
echo Then we'll manually add the slug column and populate it.
echo.

echo Step 1: Faking migration 0007...
py manage.py migrate agents 0007 --fake

echo.
echo Step 2: Manually adding slug column to database...
python add_slug_column_manual.py

echo.
echo ========================================
echo Done! Your agent URLs now use slugs.
echo ========================================
pause
