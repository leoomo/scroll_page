# EyeScroll Tauri 2 + Python Hybrid 重构方案

## Context

当前 EyeScroll 使用 Python + rumps，仅支持 macOS。用户希望发布到 macOS 和 Windows，并获得更好的调试/校准界面。

核心问题：
1. rumps 只能做 macOS 菜单栏 UI
2. PyObjC 滚动控制仅限 macOS
3. 缺少好用的调试/校准界面

## 解决方案

保留 Python 后端（MediaPipe/OpenCV），用 Tauri 2 构建跨平台 UI。

---

## 架构设计

### 项目结构

```
eye_scroll/
├── src/                    # Tauri 前端 (Rust)
│   ├── main.rs             # Tauri 入口
│   ├── commands.rs         # Tauri commands
│   └── web/               # Web UI (HTML/CSS/JS)
│       ├── index.html
│       ├── main.ts
│       ├── style.css
│       └── components/
├── python/                 # Python 后端
│   ├── main.py            # HTTP server + 启动入口
│   ├── core/              # 核心模块
│   │   ├── camera.py
│   │   ├── eye_tracker.py
│   │   ├── gaze_state.py
│   │   └── scroll_controller.py
│   ├── adapters/          # 平台适配
│   │   ├── mac_scroll.py
│   │   └── win_scroll.py
│   ├── config.py
│   └── api.py             # HTTP API 端点
├── src-tauri/             # Tauri 配置
│   ├── Cargo.toml
│   └── tauri.conf.json
└── SPEC.md
```

### 通信协议

**Python 后端暴露 HTTP API：**

| 端点 | 方法 | 说明 |
|------|------|------|
| `GET /api/gaze` | 获取当前 gaze 位置和原始值 |
| `GET /api/state` | 获取状态机当前状态 |
| `POST /api/calibrate/top` | 校准顶部（看摄像头） |
| `POST /api/calibrate/bottom` | 校准底部（看屏幕底部） |
| `GET /api/config` | 获取所有配置 |
| `PUT /api/config` | 更新配置 |
| `WS /ws/events` | WebSocket 实时事件流 |

**事件格式（WebSocket）：**
```json
{
  "type": "gaze_update",
  "data": {
    "raw_x": 0.61,
    "raw_y": 0.74,
    "screen_y": 0.65,
    "zone": "reading"
  }
}
```

---

## 功能模块

### 1. Python 后端

**保留功能：**
- MediaPipe Face Mesh 眼球追踪
- OpenCV 摄像头捕获
- 状态机逻辑（IDLE/DWELLING/SCROLLING）
- 配置持久化

**新增/修改：**
- HTTP Server（FastAPI 或内置 http.server）
- WebSocket 实时推送
- 跨平台滚动适配器

### 2. Tauri 前端

**功能：**
- 菜单栏图标（系统托盘）
- 实时 gaze 可视化（圆形指示器在屏幕示意图上移动）
- 校准向导（引导用户看向顶部/底部）
- 参数调节面板（滑动条）
- 调试日志面板（状态转换事件）
- 启用/暂停切换

**UI 布局：**
```
┌────────────────────────────────────────┐
│  👁 EyeScroll           [─] [□] [×]   │
├────────────────────────────────────────┤
│                                        │
│   ┌─────────────────────────────┐     │
│   │     屏幕区域示意图             │     │
│   │        ● ← gaze 指示器        │     │
│   │    [上方区] [阅读] [下方区]    │     │
│   └─────────────────────────────┘     │
│                                        │
│   Raw: (0.61, 0.74) → Screen: 0.65   │
│   Zone: 阅读区 | State: IDLE          │
│                                        │
├────────────────────────────────────────┤
│  向下滚动                              │
│  [✓] 启用    停留: [====○===] 500ms   │
│  区域: [====○====] 20%               │
│  距离: [===○======] 30px              │
│                                        │
│  向上滚动                              │
│  [✓] 启用    停留: [=====○==] 800ms  │
│  区域: [=○=======] 10%                │
│  距离: [===○======] 30px              │
│                                        │
├────────────────────────────────────────┤
│  校准向导                              │
│  [1. 看屏幕顶部，按 T] [2. 看屏幕底部]   │
│                                        │
│  [启用] [暂停]                         │
└────────────────────────────────────────┘
```

### 3. 跨平台滚动

```python
# scroll_controller.py
class ScrollController:
    def __init__(self):
        if sys.platform == "darwin":
            from .adapters.mac_scroll import MacScrollController
            self._impl = MacScrollController()
        elif sys.platform == "win32":
            from .adapters.win_scroll import WinScrollController
            self._impl = WinScrollController()
        else:
            raise NotImplementedError("Unsupported platform")

# adapters/mac_scroll.py - 现有 PyObjC 实现
# adapters/win_scroll.py - 新增 Windows 实现
```

---

## 关键文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `python/main.py` | 修改 | 启动 HTTP server |
| `python/api.py` | 新增 | HTTP API + WebSocket |
| `python/core/scroll_controller.py` | 重构 | 抽象为适配器模式 |
| `python/adapters/mac_scroll.py` | 新增 | 迁移现有 PyObjC 逻辑 |
| `python/adapters/win_scroll.py` | 新增 | Windows 滚动实现 |
| `src/main.rs` | 新增 | Tauri 入口 |
| `src/commands.rs` | 新增 | Tauri commands |
| `src/web/index.html` | 新增 | Web UI |
| `src-tauri/Cargo.toml` | 新增 | Rust 依赖 |
| `src-tauri/tauri.conf.json` | 新增 | Tauri 配置 |

---

## 验收条件

### 功能验收

| ID | 条件 | 验证方式 |
|----|------|----------|
| V1 | macOS 应用启动后显示 Tauri 窗口 | 运行 `cargo tauri dev`，窗口正常显示 |
| V2 | 窗口显示实时 gaze 位置和区域 | 看向摄像头，观察数字变化 |
| V3 | 点击"校准顶部"按钮后 gaze screen_y 正确映射到 0.0 附近 | 按 T 后看向摄像头，screen_y < 0.1 |
| V4 | 点击"校准底部"后 gaze screen_y 正确映射到 1.0 附近 | 按 B 后看向屏幕底部，screen_y > 0.9 |
| V5 | gaze 进入下方区域（screen_y > 0.8）后触发向下滚动 | 看向屏幕下方，等待 500ms，观察滚动 |
| V6 | gaze 进入上方区域（screen_y < 0.1）后触发向上滚动 | 看向摄像头，等待 800ms，观察回翻 |
| V7 | 配置修改后实时生效 | 拖动滑动条修改停留时间，立即反映行为 |
| V8 | Windows 版本能启动并显示 UI（需 Windows机器测试） | 交叉编译后拷贝到 Windows 运行 |

### 技术验收

| ID | 条件 | 验证方式 |
|----|------|----------|
| T1 | Python HTTP API 响应正常 | `curl http://localhost:8765/api/gaze` 返回 JSON |
| T2 | WebSocket 事件实时推送 | 连接 `ws://localhost:8765/ws/events`，观察事件流 |
| T3 | 现有 pytest 测试全部通过 | `pytest tests/` 无失败 |
| T4 | Tauri 构建成功生成 macOS app | `cargo tauri build` 生成 `.app` 文件 |
| T5 | Windows 交叉编译成功 | `cargo tauri build --target x86_64-pc-windows-msvc` |

### 用户体验验收

| ID | 条件 | 验证方式 |
|----|------|----------|
| U1 | 菜单栏显示 EyeScroll 图标 | macOS 菜单栏出现 👁 图标 |
| U2 | 暂停/启用切换正常 | 点击暂停，图标变为 👁⊘，滚动停止 |
| U3 | 校准向导清晰易懂 | UI 显示当前步骤，引导用户操作 |
| U4 | 参数调节无需重启 | 所有滑动条改动即时生效 |

---

## 实施顺序

### Phase 1: Python 后端改造
1. 提取 PyObjC 滚动逻辑到 `adapters/mac_scroll.py`
2. 实现 `adapters/win_scroll.py`（占位或简单实现）
3. 添加 HTTP server + WebSocket
4. 添加 HTTP API 端点
5. 运行现有测试确保无回归

### Phase 2: Tauri 前端
1. 创建 Tauri 项目
2. 实现系统托盘/菜单栏
3. 实现 gaze 可视化组件
4. 实现校准向导 UI
5. 实现参数调节面板
6. 连接 Python 后端 WebSocket

### Phase 3: 跨平台构建
1. 配置 Tauri 跨平台构建
2. Windows 测试（如有条件）

---

## 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| 后端语言 | Python | 3.11+ |
| Web 服务 | FastAPI / uvicorn | latest |
| WebSocket | fastapi.websockets | latest |
| 眼球追踪 | MediaPipe | latest |
| Tauri | tauri | 2.x |
| 前端 | HTML/CSS/TS | - |
| macOS 滚动 | PyObjC | latest |
| Windows 滚动 | pywin32/ctypes | latest |
