@echo off
echo ========================================
echo Fixing Agent Slug Migration
echo ========================================
echo.

echo Deleting migration 0008...
if exist agents\migrations\0008_alter_agent_slug.py (
    del agents\migrations\0008_alter_agent_slug.py
    echo ✓ Deleted 0008_alter_agent_slug.py
) else (
    echo ✓ File already deleted
)

echo.
echo Now run these commands:
echo.
echo   py manage.py migrate agents
echo.
echo This will apply the fixed migration that:
echo   1. Adds slug field (nullable)
echo   2. Populates slugs for all agents
echo   3. Adds unique constraint
echo.
pause
