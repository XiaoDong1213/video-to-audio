@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Sync ffmpeg.exe / ffprobe.exe into resources\ffmpeg\
echo.

set "DEST=%~dp0resources\ffmpeg"
if not exist "%DEST%" mkdir "%DEST%"

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo [ERROR] ffmpeg not found on PATH. Install first:
    echo   winget install Gyan.FFmpeg
    pause
    exit /b 1
)

for /f "delims=" %%I in ('where ffmpeg') do (
    copy /Y "%%I" "%DEST%\ffmpeg.exe" >nul
    echo Copied ffmpeg: %%I
    goto :probe
)

:probe
where ffprobe >nul 2>nul
if errorlevel 1 (
    echo [WARN] ffprobe not on PATH — stream listing may be limited.
) else (
    for /f "delims=" %%I in ('where ffprobe') do (
        copy /Y "%%I" "%DEST%\ffprobe.exe" >nul
        echo Copied ffprobe: %%I
        goto :done
    )
)

:done
echo.
echo Done. Files in:
echo %DEST%
dir "%DEST%"
echo.
pause
endlocal
