# 实时游戏支持分析与改进方案

## 当前系统性能分析

### 现有能力

✅ **已实现的优化：**
1. Windows GPU 加速捕获（DXGI/WGC）- 1-5ms/帧
2. 自动推送流式传输（SSE 模式）
3. 资源 URI 缓存机制
4. 可配置的 FPS 和质量
5. 多种图像格式（PNG/JPEG）

### 性能瓶颈

❌ **当前限制：**

| 限制项 | 当前值 | 游戏需求 | 差距 |
|--------|--------|----------|------|
| **最大 FPS** | 10 fps | 30-60 fps | 3-6x 不足 |
| **图像缓存** | 10 帧 | 60-120 帧 | 6-12x 不足 |
| **延迟监控** | 无 | <16ms (60fps) | 需要添加 |
| **帧跳过** | 无 | 必需 | 需要添加 |
| **自适应质量** | 无 | 推荐 | 需要添加 |
| **区域捕获** | 有但未优化 | 推荐 | 需要优化 |
| **内存管理** | 基础 | 严格 | 需要增强 |

## 实时游戏场景需求

### 1. 帧率要求

```
低帧率游戏：  15-30 FPS  (策略游戏、回合制)
标准游戏：    30-60 FPS  (大多数游戏)
高帧率游戏：  60-120 FPS (竞技游戏、FPS)
```

### 2. 延迟要求

```
可接受：  < 100ms  (策略、慢节奏)
良好：    < 50ms   (动作、冒险)
优秀：    < 33ms   (竞技、FPS)
完美：    < 16ms   (电竞级别)
```

### 3. 性能预算（每帧）

```
60 FPS 预算：16.67ms
- 捕获：    1-5ms   (DXGI/WGC)
- 编码：    2-5ms   (JPEG 低质量)
- 传输：    1-3ms   (本地网络)
- 分析：    5-8ms   (AI 视觉)
- 余量：    1-3ms
总计：      10-24ms ❌ 超出预算
```

**结论：60 FPS + AI 分析不可行，需要优化**

## 改进方案

### 方案 A：性能优先模式（推荐）

**适用场景：** 实时游戏监控、自动化

**配置：**
```python
# 高性能游戏配置
GAME_MODE_CONFIG = {
    "max_stream_fps": 60,           # 提升到 60 FPS
    "default_quality": 50,          # 降低质量
    "default_format": "jpeg",       # 使用 JPEG
    "max_cache_size": 120,          # 2 秒缓存 (60fps * 2)
    "enable_frame_skip": True,      # 启用帧跳过
    "adaptive_quality": True,       # 自适应质量
    "capture_region_only": True,    # 仅捕获游戏窗口
    "priority_mode": "performance", # 性能优先
}
```

**预期性能：**
- 捕获：1-3ms (DXGI + 区域捕获)
- 编码：1-2ms (JPEG 50% 质量)
- 传输：1-2ms (本地)
- **总计：3-7ms/帧 ✅ 满足 60 FPS**

### 方案 B：质量平衡模式

**适用场景：** 游戏录制、内容创作

**配置：**
```python
# 平衡模式配置
BALANCED_MODE_CONFIG = {
    "max_stream_fps": 30,
    "default_quality": 75,
    "default_format": "jpeg",
    "max_cache_size": 60,
    "enable_frame_skip": False,
    "adaptive_quality": True,
    "capture_region_only": False,
    "priority_mode": "balanced",
}
```

### 方案 C：质量优先模式

**适用场景：** 截图、分析、调试

**配置：**
```python
# 质量优先配置
QUALITY_MODE_CONFIG = {
    "max_stream_fps": 10,
    "default_quality": 95,
    "default_format": "png",
    "max_cache_size": 30,
    "enable_frame_skip": False,
    "adaptive_quality": False,
    "capture_region_only": False,
    "priority_mode": "quality",
}
```

## 具体改进点

### 1. 提高 FPS 限制

**当前代码（pyproject.toml）：**
```toml
MAX_STREAM_FPS=10
```

**改进：**
```toml
# 基础限制
MAX_STREAM_FPS=10

# 游戏模式限制（可选）
MAX_STREAM_FPS_GAMING=60
MAX_STREAM_FPS_EXTREME=120  # 需要顶级硬件
```

**代码位置：** `screenmonitormcp_v2/server/config.py`

### 2. 帧跳过机制

**当前问题：** 如果处理速度跟不上捕获速度，会累积延迟

**改进：**
```python
# 在 mcp_sse_server.py 中添加
async def _auto_push_stream_frames(stream_id: str, interval: float = 1.0):
    """Auto-push with frame skipping."""
    last_push_time = time.time()
    skipped_frames = 0

    while True:
        current_time = time.time()
        elapsed = current_time - last_push_time

        # 帧跳过：如果上一帧还在处理，跳过本帧
        if elapsed < interval:
            await asyncio.sleep(interval - elapsed)
            continue

        # 检测延迟累积
        if elapsed > interval * 2:
            # 跳过帧以追赶
            skipped_frames += 1
            logger.warning(f"Frame skip detected: {elapsed:.3f}s (expected {interval:.3f}s)")

        # 捕获并推送
        try:
            await capture_and_broadcast_frame(stream_id)
            last_push_time = current_time
        except Exception as e:
            logger.error(f"Frame capture failed: {e}")

        # 性能监控
        if skipped_frames > 0:
            logger.info(f"Skipped frames: {skipped_frames}")
```

### 3. 自适应质量调整

**概念：** 根据系统负载动态调整图像质量

```python
class AdaptiveQualityController:
    def __init__(self):
        self.target_fps = 60
        self.current_quality = 75
        self.min_quality = 30
        self.max_quality = 95

    async def adjust_quality(self, actual_fps: float, cpu_usage: float):
        """根据性能动态调整质量"""

        # FPS 低于目标，降低质量
        if actual_fps < self.target_fps * 0.9:
            self.current_quality = max(
                self.min_quality,
                self.current_quality - 5
            )

        # FPS 高且 CPU 空闲，提高质量
        elif actual_fps >= self.target_fps and cpu_usage < 50:
            self.current_quality = min(
                self.max_quality,
                self.current_quality + 5
            )

        return self.current_quality
```

### 4. 扩大资源缓存

**当前代码（mcp_server.py）：**
```python
_MAX_CACHE_SIZE = 10  # 只缓存 10 帧
```

**改进：**
```python
# 根据 FPS 动态计算缓存大小
def calculate_cache_size(fps: int, buffer_seconds: int = 2) -> int:
    """计算缓存大小

    Args:
        fps: 目标帧率
        buffer_seconds: 缓冲时长（秒）

    Returns:
        缓存大小
    """
    # 至少保留 2 秒的帧
    min_size = fps * buffer_seconds
    # 最多保留 5 秒的帧
    max_size = fps * 5

    return min(max_size, max(min_size, 60))

# 使用示例
_MAX_CACHE_SIZE = calculate_cache_size(60, 2)  # 60 FPS -> 120 帧缓存
```

### 5. 区域捕获优化

**问题：** 捕获整个屏幕浪费性能

**改进：** 只捕获游戏窗口

```python
async def capture_game_window(window_title: str) -> dict:
    """捕获指定窗口（仅游戏区域）

    Args:
        window_title: 窗口标题（如 "League of Legends"）

    Returns:
        捕获结果
    """
    import pygetwindow as gw

    # 查找窗口
    windows = gw.getWindowsWithTitle(window_title)
    if not windows:
        raise ValueError(f"Window not found: {window_title}")

    window = windows[0]

    # 获取窗口区域
    region = {
        "left": window.left,
        "top": window.top,
        "width": window.width,
        "height": window.height
    }

    # 使用区域捕获（性能更好）
    return await screen_capture.capture_screen(
        monitor=0,
        region=region
    )
```

### 6. 性能监控和指标

**添加实时性能监控：**

```python
class GameStreamMetrics:
    def __init__(self):
        self.frame_times = []
        self.capture_times = []
        self.encode_times = []
        self.network_times = []

    def add_frame(self, capture_ms: float, encode_ms: float, network_ms: float):
        """记录单帧性能"""
        total_ms = capture_ms + encode_ms + network_ms
        self.frame_times.append(total_ms)
        self.capture_times.append(capture_ms)
        self.encode_times.append(encode_ms)
        self.network_times.append(network_ms)

        # 只保留最近 100 帧
        if len(self.frame_times) > 100:
            self.frame_times.pop(0)
            self.capture_times.pop(0)
            self.encode_times.pop(0)
            self.network_times.pop(0)

    def get_stats(self) -> dict:
        """获取性能统计"""
        if not self.frame_times:
            return {}

        import statistics

        return {
            "avg_fps": 1000 / statistics.mean(self.frame_times),
            "avg_frame_time_ms": statistics.mean(self.frame_times),
            "avg_capture_ms": statistics.mean(self.capture_times),
            "avg_encode_ms": statistics.mean(self.encode_times),
            "avg_network_ms": statistics.mean(self.network_times),
            "p95_frame_time_ms": statistics.quantiles(self.frame_times, n=20)[18],
            "p99_frame_time_ms": statistics.quantiles(self.frame_times, n=100)[98],
        }
```

### 7. WebSocket 替代 SSE

**问题：** SSE 是单向的，不适合游戏交互

**改进：** 使用 WebSocket 实现双向实时通信

```python
# 新增 WebSocket 端点用于游戏流
@ws_router.websocket("/game-stream")
async def game_stream_websocket(websocket: WebSocket):
    """游戏专用 WebSocket 流

    特点：
    - 双向通信
    - 更低延迟
    - 支持控制命令
    """
    await websocket.accept()

    try:
        # 接收配置
        config = await websocket.receive_json()

        fps = config.get("fps", 60)
        quality = config.get("quality", 50)
        window_title = config.get("window", None)

        # 创建流
        stream_id = await stream_manager.create_stream(
            "game",
            fps=fps,
            quality=quality,
            format="jpeg"
        )

        # 自动推送帧
        interval = 1.0 / fps

        while True:
            start = time.time()

            # 捕获帧
            if window_title:
                frame = await capture_game_window(window_title)
            else:
                frame = await screen_capture.capture_screen(0)

            # 发送帧
            await websocket.send_json({
                "type": "frame",
                "data": frame["image_data"],
                "timestamp": time.time(),
                "metadata": {
                    "width": frame["width"],
                    "height": frame["height"]
                }
            })

            # 控制帧率
            elapsed = time.time() - start
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)

            # 检查客户端命令
            try:
                command = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=0.001
                )

                if command["type"] == "stop":
                    break
                elif command["type"] == "adjust_quality":
                    quality = command["quality"]

            except asyncio.TimeoutError:
                pass  # 无命令，继续

    finally:
        await stream_manager.stop_stream(stream_id)
        await websocket.close()
```

## 推荐实现优先级

### 高优先级（立即实施）

1. ✅ **提高 FPS 限制** - 从 10 → 60
2. ✅ **扩大缓存** - 从 10 → 120 帧
3. ✅ **降低默认质量** - 游戏模式 50-60% JPEG
4. ✅ **添加帧跳过** - 防止延迟累积

### 中优先级（短期实施）

5. ⚠️ **性能监控** - 实时 FPS、延迟指标
6. ⚠️ **区域捕获优化** - 窗口级捕获
7. ⚠️ **WebSocket 流** - 替代 SSE

### 低优先级（长期优化）

8. 📋 **自适应质量** - 动态调整
9. 📋 **预设配置** - 游戏/质量/平衡模式
10. 📋 **GPU 解码** - 客户端硬件加速

## 使用示例

### 游戏监控（60 FPS）

```python
# 客户端代码
import asyncio
import websockets

async def monitor_game():
    async with websockets.connect("ws://localhost:8000/game-stream") as ws:
        # 配置高性能游戏模式
        await ws.send(json.dumps({
            "fps": 60,
            "quality": 50,
            "format": "jpeg",
            "window": "League of Legends"  # 只捕获游戏窗口
        }))

        # 接收帧
        while True:
            frame_data = await ws.recv()
            frame = json.loads(frame_data)

            # 处理帧（如：AI 分析、显示等）
            process_frame(frame)

            # 性能监控
            print(f"FPS: {calculate_fps()}")

asyncio.run(monitor_game())
```

### 质量截图（高质量）

```python
# 使用现有 MCP 工具
result = await session.call_tool("capture_screen", {
    "monitor": 0,
    "format": "png",  # 无损
    "quality": 100
})
```

## 硬件要求

### 最低配置（30 FPS）
- CPU: 4 核 2.5GHz
- RAM: 4GB
- GPU: 集成显卡（支持 DXGI）
- 网络: 100 Mbps（本地）

### 推荐配置（60 FPS）
- CPU: 6 核 3.0GHz
- RAM: 8GB
- GPU: 独立显卡（支持 WGC）
- 网络: 1 Gbps（本地）

### 高端配置（120 FPS）
- CPU: 8 核 3.5GHz+
- RAM: 16GB
- GPU: RTX 2060 或更高
- 网络: 10 Gbps（本地）

## 总结

当前系统可以通过以下改进支持实时游戏：

1. **提升 FPS** - 10 → 60/120
2. **优化性能** - JPEG + 低质量 + GPU 加速
3. **添加帧跳过** - 防止延迟累积
4. **扩大缓存** - 支持更高帧率
5. **WebSocket 流** - 更低延迟
6. **性能监控** - 实时指标

**预计性能：**
- 60 FPS @ 50% JPEG：~5-8ms/帧 ✅
- 30 FPS @ 75% JPEG：~8-12ms/帧 ✅
- 60 FPS @ 95% PNG：~15-25ms/帧 ❌（不推荐）
