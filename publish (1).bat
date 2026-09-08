@echo off
REM ============================================================
REM Publish this folder as a new public repo on github.com/Milad-Shabani
REM Requires: git, and GitHub CLI (gh) installed + logged in (gh auth login)
REM ============================================================

set REPO_NAME=resource-planning-capacity-forecasting
set REPO_DESC=Resource Planning ^& DC Capacity Forecasting engine: turns a sales forecast into a day-by-day, DC-by-DC staffing and delivery plan.

cd /d "C:\Users\MILAD\Desktop\dc-capacity-forecasting"

REM --- set your git identity (safe to run every time)
git config --global user.name "Milad Shabani"
git config --global user.email "MILAD.SHABANI6515@GMAIL.COM"

REM --- init only if not already a repo
if not exist ".git" (
    git init
)

REM --- remove any leftover remote from a previous attempt
git remote remove origin 2>nul

git add .
git commit -m "Initial commit: Resource Planning - DC Capacity Forecasting project"
git branch -M main

gh repo create %REPO_NAME% --public --source=. --remote=origin --push --description "%REPO_DESC%"

gh repo edit Milad-Shabani/%REPO_NAME% --add-topic resource-planning --add-topic capacity-forecasting --add-topic supply-chain --add-topic operations-planning --add-topic python

echo.
echo Done. Repo should now be live at:
echo https://github.com/Milad-Shabani/%REPO_NAME%
pause
