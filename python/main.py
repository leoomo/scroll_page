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

import sys
sys.path.insert(0, str(Path(__file__).parent))

from core.camera import Camera
from core.head_tracker import HeadTracker
from core.head_state import HeadStateMachine, STATE_IDLE
from core.scroll_controller import ScrollController
from config import config, DEFAULT_CONFIG

# 校准数据文件
CALIBRATION_FILE = Path(__file__).parent / "calibration.json"


def save_calibration():
    """保存校准数据到文件"""
    if state.head_tracker and state.head_tracker.is_calibrated():
        data = {
            "neutral_y": state.head_tracker.get_neutral_y(),
        }
        with open(CALIBRATION_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    return False


def load_calibration():
    """从文件加载校准数据"""
    if CALIBRATION_FILE.exists() and state.head_tracker:
        try:
            with open(CALIBRATION_FILE, 'r') as f:
                data = json.load(f)
            neutral_y = data.get("neutral_y")
            if neutral_y is not None:
                state.head_tracker._neutral_y = neutral_y
                state.head_tracker._calibrated = True
                state.head_tracker._smooth_offset = 0.0
                print(f"[Calibration] Loaded: neutral_y={neutral_y:.6f}")
            return True
        except Exception as e:
            print(f"[Calibration] Failed to load: {e}")
    return False


# 全局状态
class AppState:
    def __init__(self):
        self.camera = None
        self.head_tracker = None
        self.head_state = None
        self.scroll_controller = None
        self.running = False
        self.enabled = True
        self.head_offset = None  # float | None
        self.face_detected = False
        self.lock = threading.Lock()
        self._last_calibration_result = None


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

    if state.head_tracker:
        try:
            state.head_tracker.close()
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
        state.head_tracker = HeadTracker(
            confidence_threshold=config.detection_confidence,
            ema_alpha=config.get("head_ema_alpha", 0.15),
            down_threshold=config.get("head_down_threshold", 0.03),
            up_threshold=config.get("head_up_threshold", -0.03),
        )
        state.head_state = HeadStateMachine(
            down_threshold=config.get("head_down_threshold", 0.03),
            up_threshold=config.get("head_up_threshold", -0.03),
            deadzone=config.get("head_deadzone", 0.01),
            dwell_time_ms=config.get("head_dwell_time_ms", 300),
            continuous_threshold_ms=config.get("head_continuous_threshold_ms", 2000),
            scroll_interval_ms=config.scroll_interval_ms,
        )
        state.scroll_controller = ScrollController(
            scroll_distance=config.scroll_distance,
            scroll_interval_ms=config.scroll_interval_ms,
            up_scroll_distance=config.up_scroll_distance,
            up_scroll_interval_ms=config.up_scroll_interval_ms,
        )
        # 加载保存的校准数据
        load_calibration()
        state.running = True
        return True
    except Exception as e:
        print(f"初始化失败: {e}")
        return False


def tracking_loop():
    """追踪主循环"""
    while state.running:
        if not state.enabled:
            time.sleep(0.033)
            continue

        if state.camera is None:
            time.sleep(0.033)
            continue

        frame = state.camera.read()
        if frame is None:
            time.sleep(0.033)
            continue

        result = state.head_tracker.process(frame)

        if result is None:
            state.head_state.no_face_detected()
            state.head_offset = None
            state.face_detected = False
        else:
            _, offset_y = result
            state.head_offset = offset_y
            state.face_detected = True

            # Check if calibration collection period is done
            if state.head_tracker.is_calibration_done():
                cal_result = state.head_tracker.stop_calibration()
                state._last_calibration_result = cal_result

            action = state.head_state.update(offset_y)

            if action == "scroll_down":
                state.scroll_controller.scroll_up()
            elif action == "scroll_up":
                state.scroll_controller.scroll_down()

        with state.lock:
            pass  # state is already updated on the attributes directly

        time.sleep(0.005)


# ==================== HTTP API ====================

async def handle_state(request):
    """GET /api/state - 获取状态"""
    with state.lock:
        data = {
            "state": state.head_state.get_state(),
            "head_offset": state.head_offset,
            "calibrated": state.head_tracker.is_calibrated() if state.head_tracker else False,
            "neutral_y": state.head_tracker.get_neutral_y() if state.head_tracker else None,
            "enabled": state.enabled,
            "face_detected": state.face_detected,
        }
    return data


async def handle_calibrate_neutral(request):
    """POST /api/calibrate/neutral - 开始中性点校准"""
    if state.head_tracker:
        state.head_tracker.start_calibration(3.0)
        return {"success": True, "status": "collecting", "duration": 3.0}
    return {"error": "Tracker not initialized"}


async def handle_calibrate_neutral_stop(request):
    """POST /api/calibrate/neutral/stop - 停止校准"""
    if state.head_tracker:
        result = state.head_tracker.stop_calibration()
        state._last_calibration_result = result
        return result
    return {"error": "Tracker not initialized"}


async def handle_calibrate_result(request):
    """GET /api/calibrate/result - 获取校准结果"""
    if state._last_calibration_result:
        return state._last_calibration_result
    return {"status": "no_result"}


async def handle_calibration_save(request):
    """POST /api/calibration/save - 保存校准数据"""
    if save_calibration():
        return {"success": True, "message": "Calibration saved"}
    return {"success": False, "error": "No calibration to save"}


async def handle_calibration_load(request):
    """POST /api/calibration/load - 加载校准数据"""
    if load_calibration():
        return {"success": True, "message": "Calibration loaded"}
    return {"success": False, "error": "No calibration file found"}


async def handle_calibration_reset(request):
    """POST /api/calibration/reset - 重置校准"""
    if state.head_tracker:
        state.head_tracker.reset_calibration()
    if CALIBRATION_FILE.exists():
        CALIBRATION_FILE.unlink()
    return {"success": True}


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
    try:
        body = await request.json()
        for key, value in body.items():
            if hasattr(config, key):
                config.set(key, value)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def handle_enable(request):
    """POST /api/enable - 启用追踪"""
    state.enabled = True
    return {"success": True}


async def handle_disable(request):
    """POST /api/disable - 禁用追踪"""
    state.enabled = False
    if state.scroll_controller:
        state.scroll_controller.stop()
    if state.head_state:
        state.head_state.reset()
    return {"success": True}


async def handle_set_enabled(request):
    """POST /api/enabled - 设置启用状态"""
    try:
        body = await request.json()
        enabled = body.get('enabled', True)
        state.enabled = enabled
        if not enabled:
            if state.scroll_controller:
                state.scroll_controller.stop()
            if state.head_state:
                state.head_state.reset()
        return {"success": True, "enabled": state.enabled}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
    """定时广播状态更新"""
    while state.running:
        if ws_manager.clients:
            with state.lock:
                data = {
                    "type": "state_update",
                    "data": {
                        "state": state.head_state.get_state(),
                        "head_offset": state.head_offset,
                        "face_detected": state.face_detected,
                    }
                }
            await ws_manager.broadcast(data)
        await asyncio.sleep(1 / 30)


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
        if path == '/api/state':
            data = await handle_state(None)
            content = json.dumps(data).encode()
        elif path == '/api/calibrate/neutral':
            data = await handle_calibrate_neutral(None)
            content = json.dumps(data).encode()
        elif path == '/api/calibrate/neutral/stop':
            data = await handle_calibrate_neutral_stop(None)
            content = json.dumps(data).encode()
        elif path == '/api/calibrate/result':
            data = await handle_calibrate_result(None)
            content = json.dumps(data).encode()
        elif path == '/api/calibration/save':
            data = await handle_calibration_save(None)
            content = json.dumps(data).encode()
        elif path == '/api/calibration/load':
            data = await handle_calibration_load(None)
            content = json.dumps(data).encode()
        elif path == '/api/calibration/reset':
            data = await handle_calibration_reset(None)
            content = json.dumps(data).encode()
        elif path == '/api/config':
            if method == 'GET':
                data = await handle_config_get(None)
                content = json.dumps(data).encode()
            elif method == 'PUT':
                # 读取请求体
                content_length = int(headers.get('content-length', 0))
                body = await reader.read(content_length) if content_length > 0 else b'{}'
                try:
                    updates = json.loads(body.decode())
                    for key, value in updates.items():
                        if key in DEFAULT_CONFIG:
                            config.set(key, value)
                    content = b'{"success": true}'
                except Exception as e:
                    status = b'HTTP/1.1 400 Bad Request'
                    content = json.dumps({"error": str(e)}).encode()
        elif path == '/api/enable':
            data = await handle_enable(None)
            content = json.dumps(data).encode()
        elif path == '/api/disable':
            data = await handle_disable(None)
            content = json.dumps(data).encode()
        elif path == '/api/enabled':
            content_length = int(headers.get('content-length', 0))
            body = await reader.read(content_length) if content_length > 0 else b'{}'
            class FakeRequest:
                async def json(self): return json.loads(body.decode())
            data = await handle_set_enabled(FakeRequest())
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
