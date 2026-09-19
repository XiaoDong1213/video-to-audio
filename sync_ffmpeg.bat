@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  Sync 64-bit FFmpeg -^> resources\ffmpeg
echo ========================================
echo.
echo Download (GitHub):
echo   https://github.com/BtbN/FFmpeg-Builds/releases
echo Pick: ffmpeg-master-latest-win64-gpl-shared.zip
echo   or: ffmpeg-master-latest-win64-gpl.zip
echo Unzip, then either:
echo   1) Add the bin folder to PATH and re-run this script, or
echo   2) Paste the folder that contains ffmpeg.exe when prompted.
echo.

set "DEST=%~dp0resources\ffmpeg"
if not exist "%DEST%" mkdir "%DEST%"

set "SRC="
where ffmpeg >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%I in ('where ffmpeg') do (
        set "SRC=%%~dpI"
        goto :have_src
    )
)

:have_src
if not "%SRC%"=="" goto :copy

set /p "SRC=64-bit FFmpeg folder (with ffmpeg.exe): "
if "%SRC%"=="" (
    echo Cancelled.
    pause
    exit /b 1
)

:copy
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
if not exist "%SRC%\ffmpeg.exe" (
    echo [ERROR] %SRC%\ffmpeg.exe not found
    pause
    exit /b 1
)
if not exist "%SRC%\ffprobe.exe" (
    echo [ERROR] %SRC%\ffprobe.exe not found
    pause
    exit /b 1
)

copy /Y "%SRC%\ffmpeg.exe" "%DEST%\ffmpeg.exe" >nul
copy /Y "%SRC%\ffprobe.exe" "%DEST%\ffprobe.exe" >nul
echo Copied from: %SRC%
echo Into:        %DEST%
dir "%DEST%\ffmpeg.exe" "%DEST%\ffprobe.exe"
echo.
pause
endlocal
