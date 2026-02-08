"""
三次 Bézier 曲线计算工具
用于轨迹插值
"""
import math
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class Point:
    """坐标点"""
    lng: float  # 经度
    lat: float  # 纬度


@dataclass
class BezierControlPoint(Point):
    """带手柄的贝塞尔控制点"""
    in_handle_dx: float = 0.0
    in_handle_dy: float = 0.0
    out_handle_dx: float = 0.0
    out_handle_dy: float = 0.0
    handles_locked: bool = True


def calculate_distance(p1: Point, p2: Point) -> float:
    """
    计算两点间的球面距离（米）
    使用 Haversine 公式
    """
    R = 6371000  # 地球半径（米）

    phi1 = math.radians(p1.lat)
    phi2 = math.radians(p2.lat)
    delta_phi = math.radians(p2.lat - p1.lat)
    delta_lambda = math.radians(p2.lng - p1.lng)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) *
         math.sin(delta_lambda / 2) ** 2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def linear_interpolate(a: float, b: float, t: float) -> float:
    """线性插值"""
    return a + (b - a) * t


def normalize_angle(angle: float) -> float:
    """
    归一化角度到 [0, 360)
    处理角度插值时的跳变问题
    """
    angle = angle % 360
    if angle < 0:
        angle += 360
    return angle


def interpolate_angle(start: float, end: float, t: float) -> float:
    """
    角度线性插值（考虑 359° -> 1° 的情况）
    """
    start = start % 360
    end = end % 360

    diff = end - start
    if diff > 180:
        diff -= 360
    elif diff < -180:
        diff += 360

    result = start + diff * t
    return normalize_angle(result)


class CubicBezierSegment:
    """单段三次贝塞尔曲线"""

    def __init__(
        self,
        p0: Point,
        p1: Point,  # 控制点1 (out handle of p0)
        p2: Point,  # 控制点2 (in handle of p3)
        p3: Point
    ):
        self.p0 = p0
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3

    def evaluate(self, t: float) -> Point:
        """
        计算贝塞尔曲线在参数 t 处的点
        B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃
        """
        mt = 1 - t
        mt2 = mt * mt
        mt3 = mt2 * mt
        t2 = t * t
        t3 = t2 * t

        lng = (mt3 * self.p0.lng +
               3 * mt2 * t * self.p1.lng +
               3 * mt * t2 * self.p2.lng +
               t3 * self.p3.lng)

        lat = (mt3 * self.p0.lat +
               3 * mt2 * t * self.p1.lat +
               3 * mt * t2 * self.p2.lat +
               t3 * self.p3.lat)

        return Point(lng, lat)

    def calculate_length(self, steps: int = 20) -> float:
        """
        计算曲线长度（数值积分）
        """
        length = 0.0
        prev = self.evaluate(0)

        for i in range(1, steps + 1):
            t = i / steps
            curr = self.evaluate(t)
            length += calculate_distance(prev, curr)
            prev = curr

        return length

    def get_point_at_length(self, target_length: float, steps: int = 100) -> Point:
        """
        根据弧长获取点（弧长参数化）
        """
        total_length = self.calculate_length(steps)

        if target_length <= 0:
            return self.p0
        if target_length >= total_length:
            return self.p3

        # 二分查找或线性搜索
        accumulated = 0.0
        prev = self.evaluate(0)

        for i in range(1, steps + 1):
            t = i / steps
            curr = self.evaluate(t)
            segment_length = calculate_distance(prev, curr)

            if accumulated + segment_length >= target_length:
                # 在这段内，线性插值
                remaining = target_length - accumulated
                local_t = remaining / segment_length if segment_length > 0 else 0
                local_t_param = (i - 1 + local_t) / steps
                return self.evaluate(local_t_param)

            accumulated += segment_length
            prev = curr

        return self.p3


class CubicBezierCurve:
    """多段三次贝塞尔曲线"""

    def __init__(self, points: List[Point]):
        """
        初始化曲线
        points: 包含起止点和中间控制点的列表
        """
        self.points = points
        self.segments: List[CubicBezierSegment] = []
        self.segment_lengths: List[float] = []
        self.total_length = 0.0

        self._build_segments()

    def _build_segments(self):
        """构建曲线段"""
        self.segments = []
        self.segment_lengths = []
        self.total_length = 0.0

        for i in range(len(self.points) - 1):
            # 简化版本：直接连接相邻点作为控制点
            # 实际使用时，需要从 ControlPoint 数据结构中获取手柄位置
            segment = CubicBezierSegment(
                self.points[i],
                self.points[i],  # 这里需要替换为实际的 out handle 位置
                self.points[i + 1],  # 这里需要替换为实际的 in handle 位置
                self.points[i + 1]
            )
            length = segment.calculate_length()
            self.segments.append(segment)
            self.segment_lengths.append(length)
            self.total_length += length

    def get_total_length(self) -> float:
        """获取曲线总长度"""
        return self.total_length

    def get_point_at_length(self, target_length: float) -> Point:
        """
        根据弧长获取点
        """
        if target_length <= 0:
            return self.points[0]
        if target_length >= self.total_length:
            return self.points[-1]

        # 找到所在的段
        accumulated = 0.0
        for i, (segment, seg_length) in enumerate(zip(self.segments, self.segment_lengths)):
            if accumulated + seg_length >= target_length:
                remaining = target_length - accumulated
                return segment.get_point_at_length(remaining)
            accumulated += seg_length

        return self.points[-1]

    def generate_points(self, count: int) -> List[Point]:
        """
        生成均匀分布的点
        """
        if count <= 0:
            return []
        if count == 1:
            return [self.points[0]]

        points = []
        step = self.total_length / (count - 1)

        for i in range(count):
            points.append(self.get_point_at_length(i * step))

        return points
