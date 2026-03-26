---
name: EyeScroll 向上滚动（回翻）功能
description: 眼球看向摄像头时向上滚动的功能设计规范
type: spec
created: 2026-03-26
---

# EyeScroll 向上滚动（回翻）功能设计规范

## 1. 概述

### 1.1 功能目标
允许用户通过眼球看向屏幕上方（摄像头位置）来回翻之前看过的内容。

### 1.2 设计原则
- **误操作防护**：向上滚动触发条件比向下滚动更严格（更长停留时间）
- **默认关闭**：向上滚动功能默认禁用，用户需手动启用
- **独立控制**：与向下滚动功能独立，可单独开启/关闭

---

## 2. 屏幕区域划分

```
┌─────────────────────────────┐
│  ▲ 向上滚动区 ▲              │  ← 上方区域 (0-10%)
│   （停留 800ms 触发向上滚动）  │
├─────────────────────────────┤
│                             │
│        阅读区域              │  ← 中央区域 (10-80%)
│                             │
├─────────────────────────────┤
│     ▼ 向下滚动区 ▼           │  ← 下方区域 (80-100%)
│   （停留 500ms 触发向下滚动）  │
└─────────────────────────────┘
```

---

## 3. 参数配置

### 3.1 新增配置参数

| 参数 | 默认值 | 范围 | 说明 |
|------|--------|------|------|
| `up_scroll_enabled` | `false` | bool | 向上滚动功能总开关 |
| `up_scroll_ratio` | `0.10` | 0.05-0.20 | 上方区域占屏幕比例 |
| `up_dwell_time_ms` | `800` | 500-1500 | 向上滚动触发停留时间（毫秒）|
| `up_scroll_distance` | `30` | 20-100 | 每次向上滚动像素数 |
| `up_scroll_interval_ms` | `200` | 100-500 | 向上滚动事件间隔 |

### 3.2 现有参数（保持不变）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `scroll_zone_ratio` | `0.20` | 下方区域比例 |
| `dwell_time_ms` | `500` | 向下滚动触发停留时间 |

---

## 4. 状态机设计

### 4.1 状态列表

| 状态 | 说明 |
|------|------|
| `IDLE` | 视线在阅读区域，不触发滚动 |
| `DWELLING_DOWN` | 视线停留在下方区域，开始计时 |
| `SCROLLING_DOWN` | 持续向下滚动 |
| `DWELLING_UP` | 视线停留在上方区域，开始计时 |
| `SCROLLING_UP` | 持续向上滚动 |

### 4.2 状态转换图

```
                         视线进入上方区域
                        ┌────────────────┐
                        │                ▼
┌─────────┐   停留 > 800ms   ┌──────────────┐   视线离开上方区域   ┌─────────┐
│  IDLE   │──────────────▶│ DWELLING_UP  │─────────────────▶│  IDLE   │
└─────────┘                └──────────────┘                   └─────────┘
     ▲                         │
     │                         │ 停留 > 800ms
     │                         ▼
     │                ┌──────────────┐
     │                │ SCROLLING_UP │
     │                └──────────────┘
     │                         │
     │                         │ 视线离开上方区域
     │                         ▼
     │   视线进入下方区域        ┌──────────────┐   视线离开下方区域
     │  ┌───────────────────────│ DWELLING_DOWN│───────────────────┘
     │  │                       └──────────────┘
     │  │                              │
     │  │                              │ 停留 > 500ms
     │  │                              ▼
     │  │                     ┌──────────────┐
     │  │                     │SCROLLING_DOWN│
     │  │                     └──────────────┘
     │  │                              │
     │  │                              │ 视线离开下方区域
     └──┘──────────────────────────────┘
```

---

## 5. 配置持久化

### 5.1 config.py 更新

新增配置项：
```python
DEFAULT_CONFIG = {
    # 现有配置
    "scroll_zone_ratio": 0.20,
    "dwell_time_ms": 500,
    "scroll_distance": 30,
    "scroll_interval_ms": 200,
    "detection_confidence": 0.5,
    # 新增配置
    "up_scroll_enabled": False,
    "up_scroll_ratio": 0.10,
    "up_dwell_time_ms": 800,
    "up_scroll_distance": 30,
    "up_scroll_interval_ms": 200,
}
```

---

## 6. UI 更新

### 6.1 菜单栏设置

```
┌─────────────────────────┐
│ 👁 EyeScroll      [●]   │
├─────────────────────────┤
│ ✓ 已启用                 │
│                         │
│ ─── 向下滚动 ───         │
│  停留时间: ▬▬▬○ 500ms   │
│  滚动距离: ▬▬○▬ 30px    │
│                         │
│ ─── 向上滚动 ───         │
│ [ ] 启用向上回翻          │
│  停留时间: ▬▬▬○ 800ms   │
│  滚动距离: ▬▬○▬ 30px    │
│                         │
│ [校准]  [关于]  [退出]   │
└─────────────────────────┘
```

### 6.2 状态指示

| 状态 | 图标 | 说明 |
|------|------|------|
| IDLE | 👁 | 阅读中 |
| DWELLING_DOWN | 👁⏳ | 准备向下滚动 |
| SCROLLING_DOWN | 👁⬇ | 向下滚动中 |
| DWELLING_UP | 👁🔼 | 准备向上回翻 |
| SCROLLING_UP | 👁⬆ | 向上回翻中 |
| DISABLED | 👁⊘ | 已暂停 |

---

## 7. 实现要点

### 7.1 状态机修改

扩展 `GazeStateMachine` 类：
- 新增 `DWELLING_UP` 和 `SCROLLING_UP` 状态
- 新增 `_up_scroll_threshold_y` 计算
- 修改 `_transition_to()` 支持新状态
- 修改 `update_gaze()` 处理上方区域逻辑

### 7.2 滚动控制器

修改 `ScrollController` 类：
- 新增 `_up_scroll_distance` 和 `_up_scroll_interval_ms` 参数
- 新增 `scroll_up()` 方法发送向上滚动事件
- 新增 `stop_up()` 方法停止向上滚动

### 7.3 条件判断

```python
def update_gaze(self, gaze_point):
    gaze_x, gaze_y = gaze_point

    if self._state == STATE_SCROLLING_DOWN:
        if gaze_y < self._down_threshold:
            self._transition_to(STATE_IDLE)
    elif self._state == STATE_SCROLLING_UP:
        if gaze_y > self._up_threshold:
            self._transition_to(STATE_IDLE)
    elif self._state == STATE_DWELLING_DOWN:
        if gaze_y < self._down_threshold:
            self._transition_to(STATE_IDLE)
        elif self._check_dwell_timeout(self._down_dwell_time):
            self._transition_to(STATE_SCROLLING_DOWN)
    elif self._state == STATE_DWELLING_UP:
        if gaze_y > self._up_threshold:
            self._transition_to(STATE_IDLE)
        elif self._check_dwell_timeout(self._up_dwell_time):
            self._transition_to(STATE_SCROLLING_UP)
    else:  # IDLE
        if gaze_y > self._down_threshold:
            self._start_dwell(self._down_dwell_time, STATE_DWELLING_DOWN)
        elif gaze_y < self._up_threshold and self._up_scroll_enabled:
            self._start_dwell(self._up_dwell_time, STATE_DWELLING_UP)
```

---

## 8. 测试用例

### 8.1 功能测试

| 用例 | 步骤 | 预期结果 |
|------|------|----------|
| 向上滚动触发 | 视线进入上方区域并停留 800ms | 进入 UP_DWELLING 状态，800ms 后进入 SCROLLING_UP |
| 向上滚动停止 | 视线离开上方区域 | 停止向上滚动 |
| 向下滚动触发 | 视线进入下方区域并停留 500ms | 进入 DWELLING_DOWN 状态，500ms 后进入 SCROLLING_DOWN |
| 默认关闭 | 启动应用 | up_scroll_enabled=False，不响应上方区域 |

### 8.2 误操作测试

| 用例 | 步骤 | 预期结果 |
|------|------|----------|
| 短暂经过上方 | 视线快速经过上方区域（< 800ms） | 不触发滚动 |
| 交叉区域 | 视线在上下区域间移动 | 响应时间较长的区域优先 |
