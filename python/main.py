"""
EyeScroll Python 后端
HTTP Server + WebSocket 提供 API 给 Tauri UI
"""
import asyncio
import atexit
import json
import signal
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

import sys
sys.path.insert(0, str(Path(__file__).parent))

from core.camera import Camera
from core.eye_tracker import EyeTracker
from core.gaze_state import GazeStateMachine
from core.scroll_controller import ScrollController
from config import config


# 全局状态
class AppState:
    def __init__(self):
        self.camera: Optional[Camera] = None
        self.eye_tracker: Optional[EyeTracker] = None
        self.gaze_state: Optional[GazeStateMachine] = None
        self.scroll_controller: Optional[ScrollController] = None
        self.running = False
        self.enabled = True
        self.gaze_point: Optional[Tuple[float, float]] = None
        self.raw_gaze_y: Optional[float] = None
        self.state = GazeStateMachine.STATE_IDLE
        self.lock = threading.Lock()


state = AppState()


def cleanup():
    """清理所有资源 - 确保摄像头被释放"""
    print("[Cleanup] Starting cleanup...")
    state.running = False

    if state.scroll_controller:
        try:
            state.scroll_controller.stop()
        except Exception:
            pass

    if state.camera:
        try:
            state.camera.release()
            print("[Cleanup] Camera released")
        except Exception as e:
            print(f"[Cleanup] Camera release error: {e}")

    if state.eye_tracker:
        try:
            state.eye_tracker.close()
        except Exception:
            pass

    print("[Cleanup] Cleanup complete")


def signal_handler(signum, frame):
    """处理退出信号"""
    print(f"\n[Signal] Received signal {signum}, shutting down...")
    cleanup()
    sys.exit(0)


# 注册信号处理和 atexit
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(cleanup)


def initialize():
    """初始化所有模块"""
    try:
        state.camera = Camera()
        state.eye_tracker = EyeTracker(
            confidence_threshold=config.detection_confidence
        )
        state.gaze_state = GazeStateMachine(
            dwell_time_ms=config.dwell_time_ms,
            scroll_zone_ratio=config.scroll_zone_ratio,
            up_scroll_enabled=config.up_scroll_enabled,
            up_scroll_ratio=config.up_scroll_ratio,
            up_dwell_time_ms=config.up_dwell_time_ms,
        )
        state.scroll_controller = ScrollController(
            scroll_distance=config.scroll_distance,
            scroll_interval_ms=config.scroll_interval_ms,
            up_scroll_distance=config.up_scroll_distance,
            up_scroll_interval_ms=config.up_scroll_interval_ms,
        )
        state.running = True
        return True
    except Exception as e:
        print(f"初始化失败: {e}")
        return False


def tracking_loop():
    """追踪主循环"""
    while state.running:
        if not state.enabled:
            time.sleep(0.1)
            continue

        if state.camera is None:
            time.sleep(0.1)
            continue

        frame = state.camera.read()
        if frame is None:
            time.sleep(0.1)
            continue

        gaze_point = state.eye_tracker.process(frame)
        state.raw_gaze_y = state.eye_tracker.get_last_raw_y()

        if gaze_point is None:
            state.gaze_state.no_face_detected()
        else:
            state.gaze_state.update_gaze(gaze_point)

        current_state = state.gaze_state.get_state()

        if current_state == GazeStateMachine.STATE_SCROLLING_DOWN:
            state.scroll_controller.scroll_down()
        elif current_state == GazeStateMachine.STATE_SCROLLING_UP:
            state.scroll_controller.scroll_up()
        else:
            state.scroll_controller.stop()

        with state.lock:
            state.gaze_point = gaze_point
            state.state = current_state

        time.sleep(1 / 30)


# ==================== HTTP API ====================

async def handle_gaze(request):
    """GET /api/gaze - 获取当前 gaze 位置"""
    with state.lock:
        data = {
            "raw_x": state.gaze_point[0] if state.gaze_point else None,
            "raw_y": state.raw_gaze_y,
            "screen_y": state.gaze_point[1] if state.gaze_point else None,
            "zone": _get_zone(state.gaze_point, state.gaze_state) if state.gaze_point else None,
        }
    return data


def _get_zone(gaze_point, gaze_state):
    if gaze_point is None:
        return "none"
    y = gaze_point[1]
    if gaze_state is None:
        return "unknown"
    if y > gaze_state._down_threshold_y:
        return "down"
    elif y < gaze_state._up_threshold_y:
        return "up"
    else:
        return "reading"


async def handle_state(request):
    """GET /api/state - 获取状态机状态"""
    with state.lock:
        data = {
            "state": state.state,
            "gaze_point": state.gaze_point,
        }
    return data


async def handle_calibrate_top(request):
    """POST /api/calibrate/top - 校准顶部"""
    raw_y = state.raw_gaze_y
    if raw_y is None:
        return {"error": "No gaze detected"}
    state.eye_tracker.calibrate_top(raw_y)
    return {"success": True, "top_y": raw_y}


async def handle_calibrate_bottom(request):
    """POST /api/calibrate/bottom - 校准底部"""
    raw_y = state.raw_gaze_y
    if raw_y is None:
        return {"error": "No gaze detected"}
    state.eye_tracker.calibrate_bottom(raw_y)
    return {"success": True, "bottom_y": raw_y}


async def handle_config_get(request):
    """GET /api/config - 获取配置"""
    return {
        "scroll_zone_ratio": config.scroll_zone_ratio,
        "dwell_time_ms": config.dwell_time_ms,
        "scroll_distance": config.scroll_distance,
        "scroll_interval_ms": config.scroll_interval_ms,
        "detection_confidence": config.detection_confidence,
        "up_scroll_enabled": config.up_scroll_enabled,
        "up_scroll_ratio": config.up_scroll_ratio,
        "up_dwell_time_ms": config.up_dwell_time_ms,
        "up_scroll_distance": config.up_scroll_distance,
        "up_scroll_interval_ms": config.up_scroll_interval_ms,
    }


async def handle_config_put(request):
    """PUT /api/config - 更新配置"""
    # TODO: 实现配置更新
    return {"success": True}


async def handle_enable(request):
    """POST /api/enable - 启用追踪"""
    state.enabled = True
    return {"success": True}


async def handle_disable(request):
    """POST /api/disable - 禁用追踪"""
    state.enabled = False
    if state.scroll_controller:
        state.scroll_controller.stop()
    if state.gaze_state:
        state.gaze_state.reset()
    return {"success": True}


# ==================== WebSocket ====================

class WebSocketManager:
    def __init__(self):
        self.clients = set()

    def add_client(self, websocket):
        self.clients.add(websocket)

    def remove_client(self, websocket):
        self.clients.discard(websocket)

    async def broadcast(self, data):
        """广播消息到所有客户端"""
        message = json.dumps(data)
        dead_clients = set()
        for client in self.clients:
            try:
                await client.send(message)
            except Exception:
                dead_clients.add(client)
        for client in dead_clients:
            self.clients.discard(client)


ws_manager = WebSocketManager()


async def websocket_handler(websocket, path):
    """WebSocket 连接处理"""
    ws_manager.add_client(websocket)
    try:
        async for message in websocket:
            # 客户端消息处理（预留）
            pass
    except Exception:
        pass
    finally:
        ws_manager.remove_client(websocket)


async def gaze_broadcaster():
    """定时广播 gaze 更新"""
    while state.running:
        if ws_manager.clients:
            with state.lock:
                data = {
                    "type": "gaze_update",
                    "data": {
                        "raw_x": state.gaze_point[0] if state.gaze_point else None,
                        "raw_y": state.raw_gaze_y,
                        "screen_y": state.gaze_point[1] if state.gaze_point else None,
                        "zone": _get_zone(state.gaze_point, state.gaze_state),
                        "state": state.state,
                    }
                }
            await ws_manager.broadcast(data)
        await asyncio.sleep(1 / 30)  # ~30fps


# ==================== HTTP Server ====================

async def handle_request(reader, writer):
    """简单的 HTTP 请求处理"""
    request_line = await reader.readline()
    if not request_line:
        writer.close()
        return

    method, path, _ = request_line.decode().strip().split()

    # 读取 headers
    headers = {}
    while True:
        line = await reader.readline()
        if line in (b'\r\n', b'\n', b''):
            break
        key, value = line.decode().strip().split(': ', 1)
        headers[key.lower()] = value

    # CORS headers
    cors_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
    }

    if method == 'OPTIONS':
        writer.write(b'HTTP/1.1 200 OK\r\n')
        for k, v in cors_headers.items():
            writer.write(f'{k}: {v}\r\n'.encode())
        writer.write(b'\r\n')
        await writer.drain()
        writer.close()
        return

    # 路由
    status = b'HTTP/1.1 200 OK'
    content = b''

    try:
        if path == '/api/gaze':
            data = await handle_gaze(None)
            content = json.dumps(data).encode()
        elif path == '/api/state':
            data = await handle_state(None)
            content = json.dumps(data).encode()
        elif path == '/api/calibrate/top':
            data = await handle_calibrate_top(None)
            content = json.dumps(data).encode()
        elif path == '/api/calibrate/bottom':
            data = await handle_calibrate_bottom(None)
            content = json.dumps(data).encode()
        elif path == '/api/config':
            if method == 'GET':
                data = await handle_config_get(None)
                content = json.dumps(data).encode()
            elif method == 'PUT':
                content = b'{"success": true}'
        elif path == '/api/enable':
            data = await handle_enable(None)
            content = json.dumps(data).encode()
        elif path == '/api/disable':
            data = await handle_disable(None)
            content = json.dumps(data).encode()
        else:
            status = b'HTTP/1.1 404 Not Found'
            content = b'{"error": "Not found"}'
    except Exception as e:
        status = b'HTTP/1.1 500 Internal Server Error'
        content = json.dumps({"error": str(e)}).encode()

    writer.write(status + b'\r\n')
    writer.write(b'Content-Type: application/json\r\n')
    writer.write(f'Content-Length: {len(content)}\r\n'.encode())
    for k, v in cors_headers.items():
        writer.write(f'{k}: {v}\r\n'.encode())
    writer.write(b'\r\n')
    writer.write(content)
    await writer.drain()
    writer.close()


async def start_http_server(host='127.0.0.1', port=8765):
    """启动 HTTP 服务器"""
    server = await asyncio.start_server(handle_request, host, port)
    print(f"HTTP server started on http://{host}:{port}")
    return server


async def main():
    """主入口"""
    if not initialize():
        print("初始化失败")
        return

    # 启动追踪线程
    tracking_thread = threading.Thread(target=tracking_loop, daemon=False)  # 非 daemon，确保 cleanup 能执行
    tracking_thread.start()

    # 启动 HTTP 服务器
    server = await start_http_server()

    # 启动 WebSocket 广播
    broadcaster = asyncio.create_task(gaze_broadcaster())

    print("EyeScroll Python backend running...")
    print("Press Ctrl+C to stop")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nShutting down...")
        state.running = False
        broadcaster.cancel()
        server.close()
        await server.wait_closed()
        cleanup()


if __name__ == "__main__":
    asyncio.run(main())
