# CLAUDE.md

## 项目概述

EyeScroll — macOS 免手滚动应用。通过 MacBook 内置摄像头追踪头部姿态（非眼球），实现低头向下滚动、抬头向上滚动。

## 双模式架构

本项目有**两套运行模式**，共享 `python/core/` 和 `python/config.py`：

| | simple_main.py (本地模式) | main.py + Tauri (GUI 模式) |
|---|---|---|
| 入口 | `python/simple_main.py` | `python/main.py` + `src-tauri/` |
| UI | rumps 菜单栏 | Tauri WebView 窗口 |
| 通信 | 无（单进程） | HTTP API :8765 + WebSocket |
| 校准 | PySide6 弹窗 (multiprocessing 隔离) | HTTP API 触发，Tauri UI 展示 |
| 启动 | `uv run python/simple_main.py` | 先启动 Python 后端，再启动 Tauri |
| 适用场景 | 日常使用，最低延迟 | 调试、可视化、参数调整 |

### 通信协议 (GUI 模式)

Python 后端提供 HTTP API，Tauri (Rust) 作为代理转发给前端 JS：

```
Frontend (JS) → Tauri (Rust invoke) → HTTP :8765 → Python asyncio
```

- `GET  /api/state` — 追踪状态 (state, head_offset, face_detected, calibrated, enabled)
- `POST /api/calibrate/neutral` → `POST /api/calibrate/neutral/stop` — 校准流程
- `GET/PUT /api/config` — 配置读写
- `POST /api/enable` / `POST /api/disable` — 开关追踪
- `WebSocket /ws` — 30fps 实时状态推送

## 目录结构

```
python/
├── simple_main.py          # 本地模式入口（rumps 菜单栏）
├── main.py                 # GUI 模式入口（asyncio HTTP + WS 服务器）
├── config.py               # 配置管理（DEFAULT_CONFIG + 持久化到 ~/.eye_scroll/）
├── core/
│   ├── camera.py           # OpenCV 摄像头封装
│   ├── head_tracker.py     # MediaPipe Face Mesh 头部姿态追踪
│   ├── head_state.py       # 5 状态状态机
│   └── scroll_controller.py # 抽象滚动控制器 + 平台适配器
├── adapters/
│   ├── mac_scroll.py       # macOS 滚动 (PyObjC Accessibility API)
│   ├── mac_flash.py        # macOS 方向箭头通知
│   ├── calibration_pyside6.py  # 校准弹窗 (当前使用)
│   ├── calibration_window.py   # 校准弹窗 (AppKit 备选)
│   └── win_scroll.py       # Windows 滚动 (占位)
├── tests/                  # pytest 测试
src-tauri/                  # Rust/Tauri 桌面应用
src/web/                    # 前端 HTML/JS/CSS (Vite 构建)
```

## 状态机 (5 状态)

```
IDLE → DWELLING_DOWN → CONTINUOUS_DOWN
IDLE → DWELLING_UP   → CONTINUOUS_UP
任何状态 → (无面部) → IDLE
```

| 状态 | 触发条件 | 行为 |
|------|----------|------|
| IDLE | offset 在 deadzone 内 | 无动作 |
| DWELLING_DOWN | offset_y ≤ down_threshold | 停留超 dwell_time 后触发 scroll_down |
| DWELLING_UP | offset_y ≥ up_threshold | 停留超 dwell_time 后触发 scroll_up |
| CONTINUOUS_DOWN | 持续低头超 continuous_threshold_ms | 按 scroll_interval_ms 持续滚动 |
| CONTINUOUS_UP | 持续抬头超 continuous_threshold_ms | 按 scroll_interval_ms 持续滚动 |

**关键**: `offset_y` 是头部偏移量，负值 = 低头（向下看），正值 = 抬头。因此 `down_threshold` 为负值，`up_threshold` 为正值。比较方向：低头检测用 `<=`，抬头检测用 `>=`。

## 核心参数

在 `config.py` 的 `DEFAULT_CONFIG` 中定义，单一数据源。所有 `config.get()` 调用不应提供 fallback 值——让 DEFAULT_CONFIG 作为唯一默认值来源。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| head_down_threshold | -0.015 | 低头触发阈值（负值） |
| head_up_threshold | 0.015 | 抬头触发阈值（正值） |
| head_deadzone | 0.008 | 死区范围 |
| head_ema_alpha | 0.30 | EMA 平滑系数 |
| head_dwell_time_ms | 150 | 停留触发时间 |
| scroll_distance | 30 | 每次滚动像素数 |
| scroll_interval_ms | 200 | 滚动事件间隔 |

## 开发规范

- 使用 `uv` 管理 Python 项目（不用 pip）
- **禁止**使用模拟数据或虚假数据——校准和追踪必须使用真实传感器数据
- `config.get("key")` 不要提供第二参数——DEFAULT_CONFIG 已包含所有默认值
- 追踪循环 (tracking_loop) 是 200Hz 热路径——不能在其中做阻塞 I/O、subprocess、或 import
- cleanup() 必须用 try/except 保护每个资源释放，避免部分初始化时资源泄漏

## 常用命令

```bash
# 本地模式启动
uv run python simple_main.py

# 测试
uv run pytest python/tests/

# Tauri 开发 (需要先启动 Python 后端)
uv run python main.py &
cd src/web && npm run build
cd ../.. && npx tauri dev
```

## 权限要求

macOS 需要：
1. **摄像头权限** — 用于 MediaPipe 头部追踪
2. **辅助功能权限** — 用于 PyObjC 发送滚动事件

## 已知问题

- `simple_main.py` 和 `main.py` 存在大量重复代码（AppState、tracking_loop、save/load_calibration）——未来应提取为共享模块
- `calibration_pyside6.py` 的 Worker 使用硬编码假数据——需要接入真实 head_tracker 数据
- 三个校准适配器 (pyside6/window/osascript) 只使用 pyside6，其余为历史代码
