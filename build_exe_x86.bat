@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo   Video to audio Build — x86 (PyQt5)
echo   For old 32-bit Windows
echo ========================================
echo.

set "PYTHON="
if exist "C:\Python310-32\python.exe" set "PYTHON=C:\Python310-32\python.exe"
if exist "C:\Python39-32\python.exe" set "PYTHON=C:\Python39-32\python.exe"
if "%PYTHON%"=="" set "PYTHON=python"

"%PYTHON%" --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 32-bit Python not found.
    echo Install Python 3.8-3.10 Windows x86, then:
    echo   set PYTHON=C:\Path\to\python.exe
    echo   build_exe_x86.bat
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
    echo Place 32-bit ffmpeg here, or run sync_ffmpeg_x86.bat
    pause
    exit /b 1
)
if not exist "resources\ffmpeg_x86\ffprobe.exe" (
    echo [ERROR] Missing resources\ffmpeg_x86\ffprobe.exe
    pause
    exit /b 1
)

echo Using: %PYTHON%
"%PYTHON%" -m pip install -q -r requirements-x86.txt

"%PYTHON%" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    "%PYTHON%" -m pip install "pyinstaller>=5.13,<7"
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
