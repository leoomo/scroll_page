# HeadScroll

**macOS 免手滚动应用 — 通过头部姿态控制页面滚动**

[中文说明](#中文说明) | [English](#english)

---

## English

### Overview

HeadScroll is a macOS menu bar application that enables hands-free scrolling by tracking your head pose using the webcam. Simply look down to scroll down, look up to scroll up.

### Features

- **Head Pose Tracking** — Uses MediaPipe Face Mesh to detect head orientation in real-time
- **Dual Scroll Modes**
  - **Dwell Scroll** — Look down/up for a moment to trigger scrolling
  - **Continuous Scroll** — Maintain head position for continuous scrolling
- **macOS Native** — Runs as a menu bar app with minimal resource usage
- **Privacy First** — All processing happens locally, no data sent to any server
- **Configurable Sensitivity** — Adjust thresholds and deadzones to match your preference

### Requirements

- macOS 10.15 (Catalina) or later
- Webcam (built-in or external)
- **Camera Permission** — Required for head tracking
- **Accessibility Permission** — Required for sending scroll events (System Settings → Privacy & Security → Accessibility)

### Installation

1. Download the latest `HeadScroll.app` from [Releases](https://github.com/leoomo/scroll_page/releases)
2. Move `HeadScroll.app` to your Applications folder
3. Launch HeadScroll from Applications
4. Grant camera and accessibility permissions when prompted

### Usage

Once running, HeadScroll appears as an icon (👤) in your menu bar.

| Menu Item | Description |
|-----------|-------------|
| 启用 | Toggle tracking on/off |
| 校准 (3秒) | Calibrate neutral head position |
| 重置校准 | Clear calibration data |
| 退出 | Exit the application |

**Scroll Behavior:**
- Look **down** → Scroll **up**
- Look **up** → Scroll **down**
- Return to **neutral** → Stop scrolling

### Configuration

Configuration file: `~/.eye_scroll/config.json`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `head_down_threshold` | 0.008 | Head down trigger (negative value) |
| `head_up_threshold` | -0.035 | Head up trigger (negative value) |
| `head_deadzone` | 0.045 | Neutral zone where no scrolling occurs |
| `head_dwell_time_ms` | 150 | Time in deadzone before triggering |
| `head_continuous_threshold_ms` | 2000 | Time to hold for continuous scroll |
| `scroll_distance` | 30 | Pixels per scroll event |
| `scroll_interval_ms` | 200 | Interval between scroll events |

### Development Setup

```bash
# Clone the repository
git clone https://github.com/leoomo/scroll_page.git
cd scroll_page

# Install dependencies
uv sync

# Run in development mode
uv run python python/simple_main.py
```

### Building from Source

```bash
# Install PyInstaller
uv pip install pyinstaller

# Build macOS app bundle
uv run pyinstaller HeadScroll.spec

# Output: dist/HeadScroll.app
```

### Architecture

```
python/
├── simple_main.py          # Menu bar app entry point (rumps)
├── main.py                 # GUI mode entry (Tauri + HTTP server)
├── config.py               # Configuration management
├── core/
│   ├── camera.py           # OpenCV camera wrapper
│   ├── head_tracker.py     # MediaPipe Face Mesh integration
│   ├── head_state.py       # 5-state scroll state machine
│   └── scroll_controller.py # Platform scroll event dispatcher
├── adapters/
│   ├── mac_scroll.py       # macOS scroll (PyObjC Accessibility API)
│   ├── mac_flash.py        # Menu bar notification arrows
│   └── calibration_pyside6.py # Calibration dialog (Qt multiprocess)
└── tests/                  # pytest tests
```

**State Machine:**
```
IDLE → DWELLING_DOWN → CONTINUOUS_DOWN
IDLE → DWELLING_UP   → CONTINUOUS_UP
Any state → (no face) → IDLE
```

### Permissions Explained

| Permission | Why It's Needed |
|------------|-----------------|
| Camera | HeadScroll uses your webcam to detect head position via MediaPipe Face Mesh |
| Accessibility | Required to programmatically send scroll events to other applications |

### License

MIT License

---

## 中文说明

### 概述

HeadScroll 是一款 macOS 菜单栏应用，通过摄像头追踪头部姿态实现免手滚动。低头向下滚动，抬头向上滚动。

### 主要功能

- **头部姿态追踪** — 使用 MediaPipe Face Mesh 实时检测头部方向
- **双滚动模式**
  - **停留滚动** — 低头/抬头一小段时间触发滚动
  - **持续滚动** — 保持头部位置持续滚动
- **原生 macOS** — 菜单栏应用，资源占用低
- **隐私优先** — 所有处理在本地完成，不上传任何数据
- **灵敏度可调** — 可配置阈值和死区，适应不同使用习惯

### 系统要求

- macOS 10.15 (Catalina) 或更高版本
- 摄像头（内置或外接）
- **摄像头权限** — 用于头部追踪
- **辅助功能权限** — 用于发送滚动事件（系统设置 → 隐私与安全性 → 辅助功能）

### 安装

1. 从 [Releases](https://github.com/leoomo/scroll_page/releases) 下载最新版的 `HeadScroll.app`
2. 将 `HeadScroll.app` 移动到应用程序文件夹
3. 从应用程序文件夹启动 HeadScroll
4. 按提示授予摄像头和辅助功能权限

### 使用方法

运行后，HeadScroll 会显示在菜单栏，图标为 👤。

| 菜单项 | 说明 |
|--------|------|
| 启用 | 开启/关闭追踪 |
| 校准 (3秒) | 校准头部中立位置 |
| 重置校准 | 清除校准数据 |
| 退出 | 退出应用 |

**滚动逻辑：**
- 低头 → 向上滚动
- 抬头 → 向下滚动
- 回到中间 → 停止滚动

### 配置说明

配置文件位置：`~/.eye_scroll/config.json`

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `head_down_threshold` | 0.008 | 低头触发阈值（负值） |
| `head_up_threshold` | -0.035 | 抬头触发阈值（负值） |
| `head_deadzone` | 0.045 | 死区范围，不触发滚动 |
| `head_dwell_time_ms` | 150 | 死区内停留触发时间 |
| `head_continuous_threshold_ms` | 2000 | 持续滚动触发时间 |
| `scroll_distance` | 30 | 每次滚动像素数 |
| `scroll_interval_ms` | 200 | 滚动事件间隔 |

### 开发环境搭建

```bash
# 克隆仓库
git clone https://github.com/leoomo/scroll_page.git
cd scroll_page

# 安装依赖
uv sync

# 开发模式运行
uv run python python/simple_main.py
```

### 从源码构建

```bash
# 安装 PyInstaller
uv pip install pyinstaller

# 构建 macOS 应用包
uv run pyinstaller HeadScroll.spec

# 输出位置：dist/HeadScroll.app
```

### 项目结构

```
python/
├── simple_main.py          # 菜单栏应用入口 (rumps)
├── main.py                 # GUI 模式入口 (Tauri + HTTP 服务器)
├── config.py               # 配置管理
├── core/
│   ├── camera.py           # OpenCV 摄像头封装
│   ├── head_tracker.py     # MediaPipe Face Mesh 头部追踪
│   ├── head_state.py       # 5 状态滚动状态机
│   └── scroll_controller.py # 平台滚动事件分发
├── adapters/
│   ├── mac_scroll.py       # macOS 滚动 (PyObjC Accessibility API)
│   ├── mac_flash.py        # 菜单栏方向箭头通知
│   └── calibration_pyside6.py # 校准弹窗 (Qt 多进程)
└── tests/                  # pytest 测试
```

### 权限说明

| 权限 | 用途 |
|------|------|
| 摄像头 | HeadScroll 使用摄像头通过 MediaPipe Face Mesh 检测头部位置 |
| 辅助功能 | 必须获取此权限才能向其他应用发送滚动事件 |

### 开源协议

MIT License
