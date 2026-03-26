"""
EyeScroll 眼球追踪模块
使用 MediaPipe Face Mesh 检测虹膜位置
"""
from pathlib import Path
import numpy as np
from typing import Optional, Tuple
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


LEFT_IRIS_INDEX = 468
RIGHT_IRIS_INDEX = 473

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

MODEL_DIR = Path(__file__).parent.parent / ".models"
MODEL_PATH = MODEL_DIR / "face_landmarker.task"


def _get_model_path() -> str:
    """获取模型文件路径"""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return str(MODEL_PATH)


class EyeTracker:
    """眼球追踪器"""

    def __init__(self, confidence_threshold: float = 0.5):
        self.confidence_threshold = confidence_threshold
        self._frame_timestamp = 0

        # 默认校准参数（虹膜相对位置）
        self._calibrated = True
        self._top_offset_y = 0.30    # 向上看时的 iris_relative_y（约 0.25-0.35）
        self._bottom_offset_y = 0.70  # 向下看时的 iris_relative_y（约 0.65-0.75）

        # 指数滑动平均参数
        self._smoothing_alpha = 0.3   # 越小越平滑
        self._last_smoothed_offset_y = None  # 上一帧的平滑 offset_y

        # 保留旧的校准变量别名以兼容外部调用（main.py 仍用 _top_gaze_y / _bottom_gaze_y）
        self._top_gaze_y = None
        self._bottom_gaze_y = None

        base_options = python.BaseOptions(
            model_asset_path=_get_model_path()
        )
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=confidence_threshold,
            min_face_presence_confidence=confidence_threshold,
            min_tracking_confidence=confidence_threshold,
        )
        self._detector = vision.FaceLandmarker.create_from_options(options)

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

    def is_calibrated(self) -> bool:
        return self._calibrated

    def reset_calibration(self):
        """重置校准到默认值"""
        # 默认校准值（虹膜相对位置）
        self._top_offset_y = 0.30
        self._bottom_offset_y = 0.70
        self._top_gaze_y = self._top_offset_y
        self._bottom_gaze_y = self._bottom_offset_y
        self._calibrated = True
        self._last_smoothed_offset_y = None
        print(f"[校准] 已重置到默认值: top={self._top_offset_y:.4f}, bottom={self._bottom_offset_y:.4f}")

    def process(self, frame: np.ndarray) -> Optional[Tuple[float, float]]:
        """处理一帧图像，检测视线位置

        使用虹膜相对于眼眶的位置，而不是绝对坐标，以提高距离不变性
        """
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        result = self._detector.detect_for_video(mp_image, self._frame_timestamp)
        self._frame_timestamp += 33  # ~30fps

        if not result.face_landmarks or len(result.face_landmarks) == 0:
            return None

        face_landmarks = result.face_landmarks[0]

        # 虹膜中心
        left_iris  = face_landmarks[LEFT_IRIS_INDEX]
        right_iris = face_landmarks[RIGHT_IRIS_INDEX]
        self._last_raw_x = (left_iris.x + right_iris.x) / 2

        # 眼眶边界
        left_eye_top = face_landmarks[LEFT_UPPER_LID]
        left_eye_bottom = face_landmarks[LEFT_LOWER_LID]
        right_eye_top = face_landmarks[RIGHT_UPPER_LID]
        right_eye_bottom = face_landmarks[RIGHT_LOWER_LID]

        # 计算虹膜在眼眶内的相对位置（距离无关）
        left_eye_height = left_eye_bottom.y - left_eye_top.y
        right_eye_height = right_eye_bottom.y - right_eye_top.y

        # 防止除零
        if abs(left_eye_height) < 0.001 or abs(right_eye_height) < 0.001:
            return None

        left_iris_relative = (left_iris.y - left_eye_top.y) / left_eye_height
        right_iris_relative = (right_iris.y - right_eye_top.y) / right_eye_height

        # 双眼平均（范围约 0.2~0.8）
        iris_relative_y = (left_iris_relative + right_iris_relative) / 2

        # 指数滑动平均滤波
        if self._last_smoothed_offset_y is None:
            self._last_smoothed_offset_y = iris_relative_y
        smoothed_y = (
            self._smoothing_alpha * iris_relative_y +
            (1 - self._smoothing_alpha) * self._last_smoothed_offset_y
        )
        self._last_smoothed_offset_y = smoothed_y

        # 存储用于校准
        self._last_raw_offset_y = iris_relative_y

        # 应用校准转换
        if self._calibrated and self._bottom_offset_y != self._top_offset_y:
            # 反转方向：向下看时 iris_relative_y 增大，屏幕 y 也应该增大
            screen_y = (smoothed_y - self._top_offset_y) / (self._bottom_offset_y - self._top_offset_y)
            screen_y = max(0.0, min(1.0, screen_y))
            return (float(self._last_raw_x), float(screen_y))

        # 未校准：返回 0.5（中立位置，不触发滚动）
        return (float(self._last_raw_x), 0.5)

    def get_last_raw_y(self) -> Optional[float]:
        """获取上一次处理的原始 y 值（用于校准）"""
        return getattr(self, '_last_raw_y', None)

    def get_last_offset_y(self) -> Optional[float]:
        """获取上一次处理的原始 offset_y（用于校准）"""
        return getattr(self, '_last_raw_offset_y', None)

    def close(self):
        """关闭追踪器"""
        self._detector.close()
