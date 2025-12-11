@echo off
REM Git Cache Cleanup Script for Windows
REM This script removes cached files from Git tracking based on the updated .gitignore

setlocal enabledelayedexpansion

echo ==========================================
echo Git Cache Cleanup Script
echo ==========================================
echo.

REM Check if we're in a git repository
git rev-parse --git-dir >nul 2>&1
if errorlevel 1 (
    echo Error: Not a git repository
    exit /b 1
)

echo Step 1: Checking current status...
git status --short
echo.

echo Step 2: Removing all cached files from Git index...
echo This will NOT delete files from your disk, only from Git tracking.
set /p CONTINUE="Continue? (y/n): "
if /i not "%CONTINUE%"=="y" (
    echo Aborted.
    exit /b 0
)

REM Remove all files from Git index
git rm -r --cached . 2>nul
if errorlevel 1 (
    echo Some files were already untracked
)

echo.
echo Step 3: Re-adding files based on new .gitignore...
git add .

echo.
echo Step 4: Checking what will be committed...
echo.
echo Files to be deleted (removed from tracking):
git status --short | findstr /B "D" | more
echo.
echo Modified files:
git status --short | findstr /B "M" | more
echo.

echo Summary:
git status --short | find /c /v ""
echo.

echo Step 5: Ready to commit
echo Suggested commit message:
echo   chore: update .gitignore and remove cached files from tracking
echo.
set /p COMMIT="Commit these changes? (y/n): "

if /i "%COMMIT%"=="y" (
    git commit -m "chore: update .gitignore and remove cached files from tracking"
    echo.
    echo Changes committed successfully!
    echo.
    
    set /p PUSH="Push to origin? (y/n): "
    if /i "!PUSH!"=="y" (
        for /f "tokens=*" %%i in ('git rev-parse --abbrev-ref HEAD') do set BRANCH=%%i
        echo Pushing to origin/!BRANCH!...
        git push origin !BRANCH!
        echo.
        echo Changes pushed successfully!
    ) else (
        for /f "tokens=*" %%i in ('git rev-parse --abbrev-ref HEAD') do set BRANCH=%%i
        echo Skipped push. You can push later with: git push origin !BRANCH!
    )
) else (
    echo Commit skipped. Changes are staged. You can commit later with:
    echo   git commit -m "chore: update .gitignore and remove cached files"
)

echo.
echo ==========================================
echo Cleanup Complete!
echo ==========================================
echo.
echo Verification commands:
echo   git check-ignore Frontend/node_modules
echo   git check-ignore Backend/__pycache__
echo   git ls-files ^| findstr node_modules
echo.

endlocal
