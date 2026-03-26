"""
EyeScroll 校准模块
用于校准眼球追踪的准确度
"""
from typing import Tuple, List


class Calibration:
    """眼球追踪校准器"""

    def __init__(self):
        self._calibration_points: List[Tuple[float, float]] = []
        self._offset_x = 0.0
        self._offset_y = 0.0

    def add_calibration_point(
        self,
        screen_x: float,
        screen_y: float,
        gaze_x: float,
        gaze_y: float,
    ):
        """
        添加校准点

        Args:
            screen_x, screen_y: 屏幕上的目标点位置
            gaze_x, gaze_y: 对应的视线位置
        """
        self._calibration_points.append((screen_x, screen_y, gaze_x, gaze_y))
        self._update_offset()

    def _update_offset(self):
        """更新偏移量"""
        if not self._calibration_points:
            return

        total_x = sum(p[2] - p[0] for p in self._calibration_points)
        total_y = sum(p[3] - p[1] for p in self._calibration_points)
        n = len(self._calibration_points)

        self._offset_x = total_x / n
        self._offset_y = total_y / n

    def apply_calibration(self, gaze_x: float, gaze_y: float) -> Tuple[float, float]:
        """
        应用校准偏移

        Args:
            gaze_x, gaze_y: 原始视线坐标

        Returns:
            Tuple[float, float]: 校准后的视线坐标
        """
        return (
            gaze_x - self._offset_x,
            gaze_y - self._offset_y,
        )

    def reset(self):
        """重置校准"""
        self._calibration_points.clear()
        self._offset_x = 0.0
        self._offset_y = 0.0
