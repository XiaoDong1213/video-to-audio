# FFmpeg（64 位，内置）

仓库**不包含** `ffmpeg.exe` / `ffprobe.exe`（体积大）。开发或打包前放到本目录。

## 下载（GitHub）

发布页：https://github.com/BtbN/FFmpeg-Builds/releases

推荐下载其一：

- `ffmpeg-master-latest-win64-gpl-shared.zip`（较小）
- `ffmpeg-master-latest-win64-gpl.zip`（静态，无 DLL）

解压后找到含 `ffmpeg.exe`、`ffprobe.exe` 的目录（多为 `bin`）。

## 同步到本目录

在项目根目录运行：

```bat
..\sync_ffmpeg.bat
```

- 若该目录已在 PATH，脚本会自动拷贝。
- 否则按提示粘贴解压后的文件夹路径。

完成后本目录应有 `ffmpeg.exe` 与 `ffprobe.exe`。打包时会打进安装包，目标机无需再装 FFmpeg。
