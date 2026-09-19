# Video to audio

Video to audio 是一款基于 **Python + PyQt6 / PyQt5 + FFmpeg** 构建的 Windows 应用。它将视频预览、入出点裁剪、音轨提取、MP3 质量预设与多段音频合并整合在一个工作流中。

软件采用 **左侧预览裁剪 + 右侧输出设置** 的模式：导入视频后即可预览并设置裁剪区间，确认格式后一键转换；也可切换到音频合并模式按列表顺序拼接。

---

## 软件功能

### 视频转音频

- 支持常见视频容器（mp4 / mkv / avi / mov / mpg 等）。
- 输出格式：mp3、wav、aac、m4a、flac。
- MP3 三档质量（对齐常见提取工具）：
  - **低**：32k · 22050 Hz
  - **中**：128k · 44100 Hz
  - **高**：编码器默认（不强制码率 / 采样率）
- 可选采样率、声道、直接拷贝音轨、覆盖输出。

### 预览与裁剪

- 导入后左侧队列、右侧预览并排显示。
- 播放 / 暂停、±1 秒、进度拖动。
- 设入点 / 出点，或直接输入时间；出点留空表示到结尾。
- 转换时按区间提取音频。

### 音频合并

- 按列表顺序合并多段音频。
- 支持上移 / 下移调整顺序。

### 其它

- 记住上次视频 / 音频 / 输出目录、格式、质量与窗口位置。
- 内置 FFmpeg（x64 / x86 两套）。
- 转换进度按文件与 FFmpeg 进度文件实时更新。

未处理异常会写入 `crash.log`。

---

## 技术架构

| 技术 | 用途 |
| --- | --- |
| Python | 应用主要开发语言 |
| PyQt6 | 64 位 GUI / 预览 |
| PyQt5 | 32 位 GUI（老系统） |
| FFmpeg | 转码、合并、探测时长 |
| QSS | 界面样式 |
| PyInstaller | Windows EXE 打包 |

模块划分：`app` 负责启动与 CLI，`core` 负责转换与配置，`ui` 负责界面，`resources` 存放样式、图标与内置 FFmpeg。

---

## 项目结构

```text
video-to-audio/
├── main.py
├── app/                         # 启动、CLI、应用标识、中文翻译
│   ├── main.py
│   ├── cli.py
│   ├── identity.py
│   └── i18n.py
├── core/                        # 转换、格式、配置、路径
│   ├── converter.py
│   ├── formats.py
│   ├── config.py
│   ├── paths.py
│   ├── trim_time.py
│   └── utils.py
├── ui/                          # 主窗口、裁剪预览、Qt 兼容层
│   ├── main_window.py
│   ├── trim_panel.py
│   ├── combo.py
│   └── qtcompat.py
├── tests/
├── resources/
│   ├── icon.ico                 # 窗口 / 任务栏图标
│   ├── styles/app.qss
│   ├── icons/                   # 界面 SVG
│   ├── ffmpeg/                  # 64 位 FFmpeg（gitignore）
│   └── ffmpeg_x86/              # 32 位 FFmpeg（gitignore）
├── build_exe.bat
├── build_exe_x86.bat
├── sync_ffmpeg.bat
├── sync_ffmpeg_x86.bat
├── Video to audio.spec
├── Video to audio_x86.spec
├── file_version_info.txt
├── requirements.txt
├── requirements-x86.txt
├── LICENSE
└── README.md
```

---

## 准备 FFmpeg（仓库不含 exe）

体积大，exe **不进 Git**。开发 / 打包前自己下载一次，拷进 `resources\`。

### 64 位（日常开发 + `build_exe.bat`）

1. 打开发布页：[BtbN/FFmpeg-Builds Releases](https://github.com/BtbN/FFmpeg-Builds/releases)
2. 下载其一：
   - `ffmpeg-master-latest-win64-gpl-shared.zip`（较小，推荐）
   - `ffmpeg-master-latest-win64-gpl.zip`（静态）
3. 解压，找到含 `ffmpeg.exe` / `ffprobe.exe` 的目录（多为 `bin`）
4. 在项目根目录运行：

```bat
sync_ffmpeg.bat
```

脚本若在 PATH 里找到 ffmpeg 会自动拷贝；否则按提示粘贴上面的目录。完成后应有 `resources\ffmpeg\ffmpeg.exe` 与 `ffprobe.exe`。

### 32 位（仅打老系统包时需要）

1. 打开发布页：[defisym/FFmpeg-Builds-Win32 Releases](https://github.com/defisym/FFmpeg-Builds-Win32/releases)
2. 下载文件名含 **`win32-gpl`** 的 zip（不要选 win64）
3. 解压后运行：

```bat
sync_ffmpeg_x86.bat
```

按提示粘贴含两个 exe 的目录。完成后应有 `resources\ffmpeg_x86\ffmpeg.exe` 与 `ffprobe.exe`。

---

## 从源码运行

### 环境

- Windows
- Python 3.10+（64 位开发推荐）
- PyQt6
- 已按上文准备好 64 位 FFmpeg

```bash
pip install -r requirements.txt
.\sync_ffmpeg.bat
python main.py
```

开发时配置写在项目根目录 `config.json`；安装版配置在 `%APPDATA%\video_to_audio\`。

---

## Windows EXE 打包

发布包会把 `resources\ffmpeg*` 里的 exe **打进安装目录**，目标机不用再装 FFmpeg。

### x64（Win10 / 11）

```bat
sync_ffmpeg.bat
build_exe.bat
```

输出：`dist\Video to audio\`

### x86（老款 32 位 Windows）

需要 32 位 Python 3.8–3.10，以及已同步的 `resources\ffmpeg_x86\`：

```bat
sync_ffmpeg_x86.bat
set PYTHON=C:\Python310-32\python.exe
build_exe_x86.bat
```

输出：`dist\Video to audio_x86\`

> PyQt6 不支持 Win32，故 32 位包使用 PyQt5；业务代码共用，`ui/qtcompat.py` 自动选择。

打包脚本会尽量删除 `dist` 中的个人配置与日志，避免把开发机设置带入发布目录。

---

## 使用流程

1. 启动 Video to audio。
2. 顶部添加视频文件（或文件夹）。
3. 在预览区播放并设置入点 / 出点（可选）。
4. 右侧选择输出格式与 MP3 质量。
5. 点击「开始转换」。
6. 需要拼接多段音频时，切换到「音频合并」模式。

---

## 版权与许可

Video to audio 项目代码采用 **MIT License**。

### 项目贡献者

- **XiaoDong**
- **JiangRTTTR**

### 项目版权

```text
Copyright © 2026 XiaoDong and JiangRTTTR
```

详细许可条款请参阅项目根目录下的 `LICENSE` 文件。

> 本项目中内置的 FFmpeg，以及字体、图标等第三方资源，其版权归相应权利人所有。第三方资源不属于本项目代码许可证的授权范围，具体使用权限请以其各自的许可证或版权声明为准。
