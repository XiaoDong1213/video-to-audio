# FFmpeg 32 位（x86）

将 **32 位** `ffmpeg.exe` / `ffprobe.exe` 放在本目录，供 `build_exe_x86.bat` 打包。

不要把 64 位 Gyan full 构建拷到这里。可从第三方 32 位 FFmpeg 构建获取，或自行交叉编译。

```bat
..\sync_ffmpeg_x86.bat
```

（脚本会提示你手动指定源目录，因系统 PATH 上的多为 64 位。）
