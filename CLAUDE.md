# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

EyeScroll 是一个 macOS 菜单栏应用，通过 MacBook 内置摄像头追踪用户眼球运动，实现"向下看即滚动"的免手阅读体验。

### 核心功能
- 实时眼球追踪（MediaPipe Face Mesh / Iris）
- 视线移向屏幕下方区域并停留 0.5s 后自动触发向下滚动
- 适用于所有 macOS 应用

## 技术栈

- **语言**: Python 3.11+
- **眼球追踪**: MediaPipe Face Mesh / Iris
- **摄像头捕获**: OpenCV
- **系统滚动控制**: PyObjC (macOS Accessibility API)
- **菜单栏 UI**: rumps

## 架构

```
eye_scroll/
├── main.py                 # 应用入口
├── config.py               # 配置管理
├── requirements.txt        # 依赖清单
├── core/
│   ├── camera.py           # 摄像头模块（OpenCV 封装）
│   ├── eye_tracker.py      # MediaPipe 眼球追踪
│   ├── gaze_state.py       # 状态机（IDLE/DWELLING/SCROLLING）
│   └── scroll_controller.py # macOS 滚动控制（PyObjC）
├── ui/
│   ├── menu_bar.py         # 菜单栏图标和菜单（rumps）
│   └── settings_window.py  # 设置窗口
└── utils/
    ├── permissions.py       # 权限检查工具
    └── calibration.py       # 校准工具
```

## 状态机

应用有三种状态：
- **IDLE**: 正常阅读，视线在屏幕中央阅读区
- **DWELLING**: 视线停留在下方滚动区，开始计时
- **SCROLLING**: 持续滚动中

## 核心参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `SCROLL_ZONE_RATIO` | 0.25 | 屏幕下方区域占比 |
| `DWELL_TIME_MS` | 500 | 停留触发时间（毫秒）|
| `SCROLL_DISTANCE` | 80 | 每次滚动像素数 |
| `SCROLL_INTERVAL_MS` | 100 | 滚动事件间隔 |

## 依赖安装

```bash
pip install -r requirements.txt
```

## 权限要求

应用需要以下 macOS 权限：
1. **摄像头权限** - 用于眼球追踪
2. **辅助功能权限** - 用于发送滚动事件

## 开发说明

- 使用 `uv` 管理 Python 项目
- 不要使用模拟数据或虚假数据
