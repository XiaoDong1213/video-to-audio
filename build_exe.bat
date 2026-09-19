@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   Video to audio Build - x64 (PyQt6)
echo ========================================
echo.

set "PYTHON=D:\Python\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

"%PYTHON%" --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)

"%PYTHON%" -c "import sys; raise SystemExit(0 if sys.maxsize>2**32 else 1)"
if errorlevel 1 (
    echo [ERROR] Need 64-bit Python. Use build_exe_x86.bat for 32-bit.
    pause
    exit /b 1
)

if not exist "resources\ffmpeg\ffmpeg.exe" (
    echo [ERROR] Missing resources\ffmpeg\ffmpeg.exe
    echo Download: https://github.com/BtbN/FFmpeg-Builds/releases
    echo Then run sync_ffmpeg.bat
    pause
    exit /b 1
)
if not exist "resources\ffmpeg\ffprobe.exe" (
    echo [ERROR] Missing resources\ffmpeg\ffprobe.exe
    echo Run sync_ffmpeg.bat
    pause
    exit /b 1
)

"%PYTHON%" -m pip install -q -r requirements.txt
"%PYTHON%" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    "%PYTHON%" -m pip install pyinstaller
)

echo [1/3] Cleaning...
if exist build rmdir /s /q build
if exist "dist\Video to audio" rmdir /s /q "dist\Video to audio"
if not exist dist mkdir dist

echo [2/3] Building x64 EXE...
"%PYTHON%" -m PyInstaller --noconfirm --clean "Video to audio.spec"
if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo [3/3] Cleanup logs...
if exist "dist\Video to audio\crash.log" del /f /q "dist\Video to audio\crash.log"
if exist "dist\Video to audio\config.json" del /f /q "dist\Video to audio\config.json"
if exist "dist\Video to audio\video-to-audio-failures.log" del /f /q "dist\Video to audio\video-to-audio-failures.log"

echo.
echo Done: %CD%\dist\Video to audio\
echo.
pause
endlocal
