@echo off
REM Push local changes to the existing Resource-planning-capacity-forecasting
REM repo (Windows). The repo and its "origin" remote already exist -- this
REM just commits and pushes, then enables GitHub Pages if it isn't already.
REM Requires: git, GitHub CLI (gh) authenticated (gh auth login).

setlocal
set REPO_NAME=Resource-planning-capacity-forecasting
set COMMIT_MSG=Add resource-planning dashboard, advanced analyses, and forecasting updates

echo ==^> Staging and committing
git add -A
git commit -q -m "%COMMIT_MSG%"

echo ==^> Pushing to origin/main
git push origin main

echo ==^> Enabling GitHub Pages (workflow build), if not already on
for /f "delims=" %%i in ('gh api user --jq .login') do set OWNER=%%i
gh api "repos/%OWNER%/%REPO_NAME%/pages" -f build_type=workflow >nul 2>&1
if errorlevel 1 (
    echo Pages site already exists, updating build type instead
    gh api -X PUT "repos/%OWNER%/%REPO_NAME%/pages" -f build_type=workflow
)

echo.
echo Done. Repo: https://github.com/%OWNER%/%REPO_NAME%
echo Dashboard (after Pages workflow runs): https://%OWNER%.github.io/%REPO_NAME%/
endlocal
