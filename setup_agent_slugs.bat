@echo off
echo ========================================
echo Django Agent Slug Migration Setup
echo ========================================
echo.

echo Step 1: Activating virtual environment...
call venv\Scripts\activate.bat

echo Step 2: Creating migration for slug field...
python manage.py makemigrations agents

echo Step 3: Applying migration to add slug column...
python manage.py migrate agents

echo Step 4: Populating slugs for existing agents...
python populate_agent_slugs.py

echo.
echo ========================================
echo Migration Complete!
echo ========================================
echo.
echo Your agent URLs will now use slugs like:
echo   /agents/john-doe/ instead of /agents/1/
echo.
pause
