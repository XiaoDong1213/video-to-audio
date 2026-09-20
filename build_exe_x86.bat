@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   Video to audio Build - x86 (PyQt5)
echo   For old 32-bit Windows
echo ========================================
echo.

set "PYTHON=D:\Python38-32\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

"%PYTHON%" --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 32-bit Python not found: D:\Python38-32\python.exe
    pause
    exit /b 1
)

"%PYTHON%" -c "import sys; raise SystemExit(0 if sys.maxsize<=2**32 else 1)"
if errorlevel 1 (
    echo [ERROR] %PYTHON% is 64-bit. Need 32-bit Python for x86 build.
    pause
    exit /b 1
)

if not exist "resources\ffmpeg_x86\ffmpeg.exe" (
    echo [ERROR] Missing resources\ffmpeg_x86\ffmpeg.exe
    echo Download: https://github.com/defisym/FFmpeg-Builds-Win32/releases
    echo Pick a win32-gpl zip, then run sync_ffmpeg_x86.bat
    pause
    exit /b 1
)
if not exist "resources\ffmpeg_x86\ffprobe.exe" (
    echo [ERROR] Missing resources\ffmpeg_x86\ffprobe.exe
    echo Run sync_ffmpeg_x86.bat
    pause
    exit /b 1
)

echo Using: %PYTHON%
echo Installing dependencies...
"%PYTHON%" -m pip install -r requirements-x86.txt
if errorlevel 1 (
    echo [ERROR] pip install failed. Fix requirements-x86.txt encoding / network, then retry.
    pause
    exit /b 1
)

"%PYTHON%" -c "import PyQt5; from PyQt5.QtWidgets import QApplication"
if errorlevel 1 (
    echo [ERROR] PyQt5 is not importable in this 32-bit Python. Cannot build x86 package.
    pause
    exit /b 1
)

"%PYTHON%" -m PyInstaller --version >nul 2>nul
"%PYTHON%" -c "import PyInstaller; raise SystemExit(0 if PyInstaller.__version__=='5.13.2' else 1)"
if errorlevel 1 (
    echo [ERROR] Need PyInstaller 5.13.2 for Windows 7. PyInstaller 6 will not start on Win7.
    pause
    exit /b 1
)

echo [1/3] Cleaning...
if exist build rmdir /s /q build
if exist "dist\Video to audio_x86" rmdir /s /q "dist\Video to audio_x86"
if not exist dist mkdir dist

echo [2/3] Building x86 EXE (PyQt5 + 32-bit FFmpeg)...
"%PYTHON%" -m PyInstaller --noconfirm --clean "Video to audio_x86.spec"
if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo [3/3] Cleanup personal files...
if exist "dist\Video to audio_x86\crash.log" del /f /q "dist\Video to audio_x86\crash.log"
if exist "dist\Video to audio_x86\config.json" del /f /q "dist\Video to audio_x86\config.json"
if exist "dist\Video to audio_x86\video-to-audio-failures.log" del /f /q "dist\Video to audio_x86\video-to-audio-failures.log"

echo.
echo Done: %CD%\dist\Video to audio_x86\
echo Install this folder on 32-bit Windows machines.
echo.
pause
endlocal
