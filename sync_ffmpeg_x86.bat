@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  Sync 32-bit FFmpeg -^> resources\ffmpeg_x86
echo ========================================
echo.
echo Download for Windows 7 (recommended):
echo   https://github.com/sudo-nautilus/FFmpeg-Builds-Win32/releases/download/latest/ffmpeg-n4.4-latest-win32-gpl-4.4.zip
echo Or n5.1:
echo   https://github.com/sudo-nautilus/FFmpeg-Builds-Win32/releases/download/latest/ffmpeg-n5.1-latest-win32-gpl-5.1.zip
echo.
echo Do NOT use defisym "latest / n7 / n8 / n9" builds for Win7.
echo Those link SetThreadDescription and will not start on Windows 7.
echo Unzip, then paste the folder that contains ffmpeg.exe.
echo.
echo Do NOT copy a 64-bit build here.
echo.

set "DEST=%~dp0resources\ffmpeg_x86"
if not exist "%DEST%" mkdir "%DEST%"

set /p "SRC=32-bit FFmpeg folder (with ffmpeg.exe): "
if "%SRC%"=="" (
    echo Cancelled.
    pause
    exit /b 1
)
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
