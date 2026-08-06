@echo off
setlocal
set "ARTICLE_DIR=%~1"
if "%ARTICLE_DIR%"=="" set "ARTICLE_DIR=%CD%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0公众号排版.ps1" -ArticleDir "%ARTICLE_DIR%" -OpenPreview
endlocal
