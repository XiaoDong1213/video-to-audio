@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo  Sync 32-bit FFmpeg into resources\ffmpeg_x86
echo ========================================
echo.
echo PATH 上的 ffmpeg 通常是 64 位，请手动指定 32 位构建目录。
echo 目录内需包含 ffmpeg.exe 与 ffprobe.exe
echo.

set "DEST=%~dp0resources\ffmpeg_x86"
if not exist "%DEST%" mkdir "%DEST%"

set /p "SRC=32-bit FFmpeg folder: "
if "%SRC%"=="" (
    echo Cancelled.
    pause
    exit /b 1
)
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
echo Copied to %DEST%
dir "%DEST%"
echo.
pause
endlocal
