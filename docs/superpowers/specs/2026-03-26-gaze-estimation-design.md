# EyeScroll 眼球追踪改进设计

## 问题

MediaPipe Face Mesh 的 iris landmarks (468/473) 返回归一化到人脸边框的坐标。当头动时，整个人脸框移动，归一化后虹膜坐标几乎不变；而纯眼睛在眼眶内移动，归一化后变化极小(~0.02)。校准捕捉到的主要是头位信号，而非真正的视线方向。

## 解决思路

用虹膜相对于眼部参考点（眼角/眼皮）的偏移量，而非相对于整个人脸的偏移。头动时参考点和虹膜一起动，偏移量对冲；纯眼动时偏移量如实反映。

## 核心算法

### 旧算法

```python
raw_y = (left_iris.y + right_iris.y) / 2  # 归一化到整个人脸
# 头动: raw_y 变化 ~0.15，眼动: raw_y 变化 ~0.02
```

### 新算法

```python
# 眼角 landmarks
LEFT_EYE_OUTER = 33    # 左眼外角
LEFT_EYE_INNER = 133   # 左眼内角
RIGHT_EYE_INNER = 263  # 右眼内角
RIGHT_EYE_OUTER = 362  # 右眼外角

# 眼皮 landmarks（上/下眼皮两侧中点）
LEFT_UPPER_LID = 159   # 左眼上眼皮左角
LEFT_LOWER_LID = 145   # 左眼下眼皮左角
RIGHT_UPPER_LID = 386  # 右眼上眼皮右角
RIGHT_LOWER_LID = 23   # 右眼下眼皮右角

# 1. 计算眼角中点
left_eye_center  = (landmarks[33] + landmarks[133]) / 2
right_eye_center = (landmarks[263] + landmarks[362]) / 2

# 2. 计算眼皮中点
left_lid_center  = (landmarks[159] + landmarks[145]) / 2   # 垂直方向
right_lid_center = (landmarks[386] + landmarks[23]) / 2   # 垂直方向

# 3. 综合参考点（加权平均）
eye_center_y = (left_eye_center.y + right_eye_center.y) / 2
lid_center_y = (left_lid_center.y + right_lid_center.y) / 2
reference_y  = 0.6 * eye_center_y + 0.4 * lid_center_y  # 眼角权重高

# 4. 虹膜相对偏移
iris_y   = (left_iris.y + right_iris.y) / 2
offset_y = iris_y - reference_y
```

## 校准

保持 2 点校准（用户体验不变）：

- **顶部校准**（看摄像头）→ 记录 `top_offset_y`
- **底部校准**（看屏幕底部）→ 记录 `bottom_offset_y`

映射到屏幕坐标：

```python
screen_y = (offset_y - top_offset_y) / (bottom_offset_y - top_offset_y)
screen_y = clamp(screen_y, 0.0, 1.0)
```

## 噪声过滤

指数滑动平均：

```python
alpha = 0.3  # 越小越平滑
smoothed_offset = alpha * current_offset + (1 - alpha) * previous_offset
```

## 代码改动范围

只改 `python/core/eye_tracker.py`，其他文件不动：

| 文件 | 改动 |
|------|------|
| `python/core/eye_tracker.py` | 重写 `process()`，添加眼角/眼皮 landmarks 计算和偏移量映射 |
| `python/core/gaze_state.py` | 无需改动 |
| `python/main.py` | 无需改动 |

## 实现顺序

1. 打印 raw debug 数据：`offset_y`, `eye_center_y`, `lid_center_y` 验证计算正确
2. 确认"向上看"vs"向下看"的 offset_y 差异足够大（预期 0.05-0.15）
3. 接入校准映射，验证 screen_y 范围合理
4. 添加滑动平均滤波
5. 主观测试：头固定时 gaze dot 跟随眼睛移动，头动时保持稳定

## 验证方式

**主观体验测试**：人在摄像头前，头固定、只动眼睛，UI 上的 gaze dot 能跟上眼睛移动，而不会因头动大幅漂移。
