# FFmpeg（32 位 / x86）

仅打 **32 位安装包**（`build_exe_x86.bat`）时需要。仓库**不包含** exe。

**不要**把 64 位包拷到这里。

## 下载（GitHub）

发布页：https://github.com/defisym/FFmpeg-Builds-Win32/releases

选文件名含 **`win32-gpl`** 的 zip（不要选 `win64`）。例如：

- `…-win32-gpl-shared-….zip`（较小）
- `…-win32-gpl-….zip`（静态）

解压后找到含 `ffmpeg.exe`、`ffprobe.exe` 的目录。

## 同步到本目录

在项目根目录运行：

```bat
..\sync_ffmpeg_x86.bat
```

按提示粘贴解压后的文件夹路径。完成后本目录应有两个 exe，再运行 `build_exe_x86.bat`。
