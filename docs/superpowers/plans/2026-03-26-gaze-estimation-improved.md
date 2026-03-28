# Gaze Estimation 改进实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用虹膜相对位移算法替换原有的 face-normalized iris 坐标，使眼动信号独立于头动。

**Architecture:** 用眼角 landmarks (33, 133, 263, 362) 和眼皮 landmarks (159, 145, 386, 23) 的加权组合做参考点，计算虹膜相对偏移量。对齐 2 点校准接口，添加指数滑动平均滤波。

**Tech Stack:** Python 3, MediaPipe Face Mesh, numpy

---

## 文件改动

- 修改: `python/core/eye_tracker.py`

---

## Task 1: 添加 Landmark 索引常量

**Files:**
- Modify: `python/core/eye_tracker.py:12-14`

- [ ] **Step 1: 在 LEFT_IRIS_INDEX, RIGHT_IRIS_INDEX 下方添加眼 landmark 常量**

在第 14 行后添加：

```python
# 眼角 landmarks
LEFT_EYE_OUTER = 33    # 左眼外角（左侧眼角）
LEFT_EYE_INNER = 133   # 左眼内角（右侧眼角，靠近鼻子）
RIGHT_EYE_INNER = 263  # 右眼内角（左侧眼角，靠近鼻子）
RIGHT_EYE_OUTER = 362  # 右眼外角（右侧眼角）

# 眼皮 landmarks（上/下眼皮边缘中点）
LEFT_UPPER_LID = 159   # 左眼上眼皮左角
LEFT_LOWER_LID = 145   # 左眼下眼皮左角
RIGHT_UPPER_LID = 386  # 右眼上眼皮右角
RIGHT_LOWER_LID = 23   # 右眼下眼皮右角
```

- [ ] **Step 2: Commit**

```bash
git add python/core/eye_tracker.py
git commit -m "feat(eye_tracker): add eye and lid landmark indices

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: 添加平滑滤波和新的校准存储

**Files:**
- Modify: `python/core/eye_tracker.py:29-37`

- [ ] **Step 1: 在 `__init__` 中添加平滑滤波参数和偏移量存储**

在 `self._calibrated = False` 后添加：

```python
# 新的校准参数（存储 offset_y 而非 raw_y）
self._top_offset_y = None    # 向上看时的 offset_y
self._bottom_offset_y = None  # 向下看时的 offset_y

# 指数滑动平均参数
self._smoothing_alpha = 0.3   # 越小越平滑
self._last_smoothed_offset_y = None  # 上一帧的平滑 offset_y

# 保留旧的校准变量别名以兼容外部调用（main.py 仍用 _top_gaze_y / _bottom_gaze_y）
self._top_gaze_y = None
self._bottom_gaze_y = None
```

- [ ] **Step 2: Commit**

```bash
git add python/core/eye_tracker.py
git commit -m "feat(eye_tracker): add smoothing params and offset storage

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: 改写 `process()` 方法为核心偏移量计算

**Files:**
- Modify: `python/core/eye_tracker.py:79-103`

- [ ] **Step 1: 用新算法替换 `process()` 中的坐标计算逻辑**

替换原来的 face landmark 提取和校准逻辑：

```python
def process(self, frame: np.ndarray) -> Optional[Tuple[float, float]]:
    """处理一帧图像，检测视线位置（使用虹膜相对位移算法）"""
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
    result = self._detector.detect_for_video(mp_image, self._frame_timestamp)
    self._frame_timestamp += 33  # ~30fps

    if not result.face_landmarks or len(result.face_landmarks) == 0:
        return None

    face_landmarks = result.face_landmarks[0]

    # === 提取 landmarks ===
    left_iris  = face_landmarks[LEFT_IRIS_INDEX]
    right_iris = face_landmarks[RIGHT_IRIS_INDEX]

    # 眼角中点（每只眼的水平中心）
    left_eye_center  = face_landmarks[LEFT_EYE_OUTER]
    left_eye_center  = ((face_landmarks[LEFT_EYE_OUTER].x + face_landmarks[LEFT_EYE_INNER].x) / 2,
                         (face_landmarks[LEFT_EYE_OUTER].y + face_landmarks[LEFT_EYE_INNER].y) / 2)
    right_eye_center = ((face_landmarks[RIGHT_EYE_INNER].x + face_landmarks[RIGHT_EYE_OUTER].x) / 2,
                        (face_landmarks[RIGHT_EYE_INNER].y + face_landmarks[RIGHT_EYE_OUTER].y) / 2)

    # 眼皮中点（垂直方向更稳定）
    left_lid_center  = (face_landmarks[LEFT_EYE_OUTER].x,  # x 同眼角
                        (face_landmarks[LEFT_UPPER_LID].y + face_landmarks[LEFT_LOWER_LID].y) / 2)
    right_lid_center = (face_landmarks[RIGHT_EYE_OUTER].x,
                        (face_landmarks[RIGHT_UPPER_LID].y + face_landmarks[RIGHT_LOWER_LID].y) / 2)

    # 综合参考点（加权平均：眼角权重 0.6，眼皮权重 0.4）
    eye_center_y = (left_eye_center[1] + right_eye_center[1]) / 2
    lid_center_y  = (left_lid_center[1] + right_lid_center[1]) / 2
    reference_y   = 0.6 * eye_center_y + 0.4 * lid_center_y

    # 虹膜中心（Y 方向为主）
    iris_y = (left_iris.y + right_iris.y) / 2

    # 相对偏移量
    offset_y = iris_y - reference_y

    # 指数滑动平均滤波
    if self._last_smoothed_offset_y is None:
        self._last_smoothed_offset_y = offset_y
    smoothed_offset_y = (
        self._smoothing_alpha * offset_y +
        (1 - self._smoothing_alpha) * self._last_smoothed_offset_y
    )
    self._last_smoothed_offset_y = smoothed_offset_y

    # 存储原始 offset_y（用于校准）
    self._last_raw_offset_y = offset_y  # 新增，供 get_last_offset_y() 使用

    # raw_x 仍然用虹膜水平中心（可用于辅助判断）
    self._last_raw_x = (left_iris.x + right_iris.x) / 2

    # 应用校准转换
    if self._calibrated and self._bottom_offset_y != self._top_offset_y:
        screen_y = (smoothed_offset_y - self._top_offset_y) / (self._bottom_offset_y - self._top_offset_y)
        screen_y = max(0.0, min(1.0, screen_y))
        return (float(self._last_raw_x), float(screen_y))

    # 未校准：返回原始平滑偏移量（范围大致在 [-0.1, 0.1]）
    return (float(self._last_raw_x), float(smoothed_offset_y))
```

- [ ] **Step 2: Commit**

```bash
git add python/core/eye_tracker.py
git commit -m "feat(eye_tracker): implement iris-relative offset algorithm

Replace face-normalized iris coords with offset relative to
eye corner + lid center reference points. Add exponential
smoothing (alpha=0.3).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: 更新校准方法存储 offset_y

**Files:**
- Modify: `python/core/eye_tracker.py:51-67`

- [ ] **Step 1: 更新 `calibrate_top` 和 `calibrate_bottom` 存储 offset_y**

替换两个 calibrate 方法：

```python
def calibrate_top(self, offset_y: float):
    """校准顶部（看向摄像头）"""
    self._top_offset_y = offset_y
    self._top_gaze_y = offset_y  # 兼容旧接口
    print(f"[校准] 顶部 offset_y = {offset_y:.3f}")
    self._check_calibration()

def calibrate_bottom(self, offset_y: float):
    """校准底部（看向屏幕底部）"""
    self._bottom_offset_y = offset_y
    self._bottom_gaze_y = offset_y  # 兼容旧接口
    print(f"[校准] 底部 offset_y = {offset_y:.3f}")
    self._check_calibration()

def _check_calibration(self):
    """检查校准是否完成"""
    if self._top_offset_y is not None and self._bottom_offset_y is not None:
        self._calibrated = True
        print(f"[校准] 完成! top_offset={self._top_offset_y:.3f}, bottom_offset={self._bottom_offset_y:.3f}")
```

同时更新 `reset_calibration`：

```python
def reset_calibration(self):
    """重置校准"""
    self._calibrated = False
    self._top_offset_y = None
    self._bottom_offset_y = None
    self._top_gaze_y = None
    self._bottom_gaze_y = None
    self._last_smoothed_offset_y = None
    print("[校准] 已重置")
```

- [ ] **Step 2: Commit**

```bash
git add python/core/eye_tracker.py
git commit -m "feat(eye_tracker): calibrate methods store offset_y

calibrate_top/bottom now accept offset_y (iris-reference offset)
instead of raw gaze_y, matching the new algorithm.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: 添加 `get_last_offset_y()` 方法

**Files:**
- Modify: `python/core/eye_tracker.py:105-107`

- [ ] **Step 1: 在 `get_last_raw_y` 后添加 `get_last_offset_y`**

在 `get_last_raw_y` 后添加：

```python
def get_last_offset_y(self) -> Optional[float]:
    """获取上一次处理的原始 offset_y（用于校准）"""
    return getattr(self, '_last_raw_offset_y', None)
```

- [ ] **Step 2: Commit**

```bash
git add python/core/eye_tracker.py
git commit -m "feat(eye_tracker): add get_last_offset_y() for calibration

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: 验证 — 运行现有测试

**Files:**
- Test: `python/tests/test_gaze_state.py`

- [ ] **Step 1: 运行现有测试确保无回归**

```bash
cd /Users/zen/projects/scroll_page
python -m pytest python/tests/ -v
```

Expected: 所有测试通过（状态机测试不依赖 eye_tracker）

---

## Task 8: 更新 main.py 校准调用使用 get_last_offset_y()

**Files:**
- Modify: `python/main.py:126`
- Modify: `python/main.py:189, 198`

**注意：** `main.py` 在 `process()` 后调用 `get_last_raw_y()` 获取原始值传入校准。算法改后，需要改用 `get_last_offset_y()` 获取新的偏移量值。

- [ ] **Step 1: 将 `state.raw_gaze_y` 的赋值改为使用 `get_last_offset_y()`**

`python/main.py:126`:
```python
# 改前
state.raw_gaze_y = state.eye_tracker.get_last_raw_y()

# 改后（校准需要的是 offset_y，不是原始 iris y）
state.raw_gaze_y = state.eye_tracker.get_last_offset_y()
```

- [ ] **Step 2: 确认 handle_calibrate_top/bottom 无需改动**

`handle_calibrate_top` 调用 `state.eye_tracker.calibrate_top(state.raw_gaze_y)`，而 `state.raw_gaze_y` 已从 `get_last_offset_y()` 获取，无需修改校准方法调用。

- [ ] **Step 3: Commit**

```bash
git add python/main.py
git commit -m "fix(main): use get_last_offset_y() for calibration

calibrate_top/bottom now accept offset_y values, so pass
the offset (from get_last_offset_y) instead of raw iris y.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: 主观测试验证

- [ ] **Step 1: 启动 Python 后端**

```bash
cd /Users/zen/projects/scroll_page/python
source .venv/bin/activate
EYE_SCROLL_DEBUG=1 python main.py
```

观察日志中 `[校准] 顶部 offset_y = X.XXX` 和 `[校准] 底部 offset_y = X.XXX` 的数值差异是否在 0.03 以上。

- [ ] **Step 2: 校准后观察 gaze dot**

- 头固定，只用眼睛向上/向下看
- gaze dot 应该跟随眼睛移动，而不会因头动大幅漂移

---

## 验证检查清单

- [ ] 所有 Task commit 完成
- [ ] pytest 测试通过
- [ ] 校准日志显示 offset_y 差异 ≥ 0.03
- [ ] 主观测试：头固定时 gaze dot 跟随眼动
