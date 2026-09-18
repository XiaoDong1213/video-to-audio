# FFmpeg（内置）

把 `ffmpeg.exe` 与 `ffprobe.exe` 放在本目录，程序会优先使用它们；
打包时会一并打进安装包，目标机无需再装 FFmpeg。

```bat
..\sync_ffmpeg.bat
```

或手动从系统 PATH 复制进来。推荐体积较小的 **essentials** 构建（full 构建单文件可超过 200MB）。
