# 实时游戏支持 - 实现方案

## 📋 概述

本文档描述了为支持实时游戏场景所做的分析和实现。目标是让 MCP 客户端能够以 **30-60 FPS** 的高帧率、**低延迟**（<33ms）从游戏中捕获和分析屏幕内容。

## 🎯 实现状态

### ✅ 已完成（v2.6.0）

1. **详细性能分析** - `GAMING_MODE_ANALYSIS.md`
   - 当前系统瓶颈分析
   - 游戏场景需求定义
   - 性能预算计算
   - 三种模式对比（质量/平衡/性能）

2. **游戏模式核心模块** - `screenmonitormcp_v2/core/gaming_mode.py`
   - `PerformanceMode` 枚举：4 种预设模式
   - `GameStreamConfig` 配置类
   - `FrameMetrics` 性能监控
   - `AdaptiveQualityController` 自适应质量
   - `FrameSkipper` 帧跳过机制

3. **配置支持** - `screenmonitormcp_v2/server/config.py`
   - `enable_gaming_mode` - 启用游戏模式
   - `gaming_max_fps` - 最大 FPS（60）
   - `gaming_quality` - 图像质量（50）
   - `gaming_enable_frame_skip` - 启用帧跳过
   - `gaming_adaptive_quality` - 自适应质量
   - `gaming_cache_size` - 缓存大小（120 帧）

### 🚧 待实施（优先级排序）

#### 高优先级（立即需要）

1. **集成游戏模式到 SSE 服务器**
   - 修改 `mcp_sse_server.py` 使用 `gaming_mode.py`
   - 应用帧跳过逻辑
   - 应用自适应质量

2. **提高系统 FPS 限制**
   - 将 `max_stream_fps` 从 10 → 60
   - 将 `_MAX_CACHE_SIZE` 从 10 → 120

3. **性能监控端点**
   - 添加 `/mcp/metrics` 端点
   - 实时 FPS、延迟、丢帧率

#### 中优先级（短期）

4. **WebSocket 游戏流**
   - 专用 WebSocket 端点 `/game-stream`
   - 双向通信（控制命令）
   - 更低延迟

5. **区域捕获优化**
   - 窗口级捕获（pygetwindow）
   - 减少捕获面积 → 更高性能

6. **游戏模式 MCP 工具**
   - `enable_gaming_mode(mode, fps, quality)`
   - `get_gaming_metrics()`
   - `adjust_gaming_quality(quality)`

#### 低优先级（长期）

7. **预设配置文件**
   - `gaming_presets.json`
   - 不同游戏类型的预设

8. **GPU 客户端解码**
   - 客户端硬件加速
   - 降低服务器负载

## 📊 性能基准

### 当前性能（v2.6.0）

| 模式 | FPS | 质量 | 格式 | 延迟 | 状态 |
|------|-----|------|------|------|------|
| 标准 | 10 | 75% | JPEG | ~50ms | ✅ 可用 |
| 高质量 | 5 | 95% | PNG | ~80ms | ✅ 可用 |

### 目标性能（游戏模式）

| 模式 | FPS | 质量 | 格式 | 目标延迟 | 预计 | 状态 |
|------|-----|------|------|----------|------|------|
| **平衡** | 30 | 75% | JPEG | <33ms | 8-12ms | 🚧 待测试 |
| **性能** | 60 | 50% | JPEG | <17ms | 5-8ms | 🚧 待测试 |
| **极限** | 120 | 30% | JPEG | <8ms | 3-5ms | 🚧 待测试 |

### 延迟分解（60 FPS 性能模式）

```
总预算：16.67ms（60 FPS）

组件延迟：
- 捕获（DXGI）：    1-3ms  ✅
- 编码（JPEG 50%）： 1-2ms  ✅
- 传输（本地）：     1-2ms  ✅
- 余量：            10-13ms ✅

总计：3-7ms ✅ 满足 60 FPS 要求
```

## 🔧 使用方法

### 方法 1：环境变量启用

```bash
# .env 文件
ENABLE_GAMING_MODE=true
GAMING_MAX_FPS=60
GAMING_QUALITY=50
GAMING_ENABLE_FRAME_SKIP=true
GAMING_ADAPTIVE_QUALITY=true
```

### 方法 2：Python 配置

```python
from screenmonitormcp_v2.core.gaming_mode import GameStreamConfig, PerformanceMode

# 使用预设
config = GameStreamConfig(mode=PerformanceMode.PERFORMANCE)
# 结果：60 FPS, 50% quality, JPEG, frame skip enabled

# 自定义配置
config = GameStreamConfig(
    fps=120,
    quality=30,
    format="jpeg",
    enable_frame_skip=True,
    adaptive_quality=True
)
```

### 方法 3：MCP 工具（待实现）

```python
# 未来的 API
await session.call_tool("enable_gaming_mode", {
    "mode": "performance",  # or "balanced", "quality", "extreme"
    "target_fps": 60
})

# 获取性能指标
metrics = await session.call_tool("get_gaming_metrics", {})
print(f"Current FPS: {metrics['current_fps']}")
print(f"Frame Time: {metrics['avg_frame_time_ms']}ms")
print(f"Dropped Frames: {metrics['dropped_frames']}")
```

## 📈 性能指标说明

### FrameMetrics 提供的指标

```python
{
    # FPS 指标
    "current_fps": 58.5,           # 当前 FPS
    "avg_session_fps": 57.2,       # 会话平均 FPS

    # 帧时间（毫秒）
    "avg_frame_time_ms": 17.1,     # 平均帧时间
    "min_frame_time_ms": 14.2,     # 最小帧时间
    "max_frame_time_ms": 23.5,     # 最大帧时间
    "p50_frame_time_ms": 16.8,     # 50th percentile
    "p95_frame_time_ms": 20.1,     # 95th percentile
    "p99_frame_time_ms": 22.3,     # 99th percentile

    # 组件耗时
    "avg_capture_ms": 2.5,         # 平均捕获时间
    "avg_encode_ms": 1.8,          # 平均编码时间
    "avg_network_ms": 1.2,         # 平均网络时间

    # 帧统计
    "total_frames": 3432,          # 总帧数
    "dropped_frames": 12,          # 丢帧数
    "skipped_frames": 45,          # 跳帧数
    "drop_rate_percent": 0.35,     # 丢帧率
    "skip_rate_percent": 1.31,     # 跳帧率

    # 会话信息
    "session_duration_seconds": 60.0,  # 会话时长
    "sample_window_size": 100          # 采样窗口
}
```

## 🎮 游戏类型推荐配置

### 策略游戏（文明、全战）

```python
config = GameStreamConfig(
    mode=PerformanceMode.BALANCED,
    fps=30,
    quality=75,
    adaptive_quality=True
)
```

**理由：** 策略游戏节奏慢，可以牺牲帧率换取画质

### 动作游戏（刺客信条、战神）

```python
config = GameStreamConfig(
    mode=PerformanceMode.PERFORMANCE,
    fps=60,
    quality=60,
    enable_frame_skip=True
)
```

**理由：** 需要平衡帧率和画质

### 竞技游戏（CS:GO、LOL、DOTA2）

```python
config = GameStreamConfig(
    mode=PerformanceMode.EXTREME,
    fps=120,
    quality=40,
    enable_frame_skip=True,
    adaptive_quality=True
)
```

**理由：** 帧率优先，画质次要

### 回合制（炉石、Slay the Spire）

```python
config = GameStreamConfig(
    mode=PerformanceMode.QUALITY,
    fps=15,
    quality=90,
    enable_frame_skip=False
)
```

**理由：** 不需要高帧率，追求画质

## ⚠️ 限制和注意事项

### 硬件要求

**最低配置（30 FPS）：**
- CPU: Intel i5-8400 / AMD Ryzen 5 2600
- GPU: 集成显卡（支持 DXGI）
- RAM: 4GB
- 存储: SSD 推荐

**推荐配置（60 FPS）：**
- CPU: Intel i7-9700K / AMD Ryzen 7 3700X
- GPU: NVIDIA GTX 1060 / AMD RX 580（支持 WGC）
- RAM: 8GB
- 存储: NVMe SSD

**高端配置（120 FPS）：**
- CPU: Intel i9-12900K / AMD Ryzen 9 5900X
- GPU: NVIDIA RTX 3060+
- RAM: 16GB
- 存储: NVMe SSD

### Windows 优化依赖

**获得最佳性能需要：**

```bash
# DXGI 支持（推荐）
pip install screenmonitormcp-v2[windows-perf]

# 或 WGC 支持
pip install screenmonitormcp-v2[windows-wgc]

# 或两者都安装
pip install screenmonitormcp-v2[windows-all]
```

**性能对比：**
- **MSS**（无优化）: 20-50ms/帧
- **DXGI**: 1-5ms/帧（4-10x 更快）
- **WGC**: 1-5ms/帧（4-10x 更快）

### 网络要求

| FPS | 质量 | 带宽需求（本地） | 带宽需求（远程） |
|-----|------|-----------------|-----------------|
| 30 | 75% | ~10 Mbps | ~50 Mbps |
| 60 | 50% | ~15 Mbps | ~80 Mbps |
| 120 | 30% | ~20 Mbps | ~120 Mbps |

**推荐：**
- 本地连接：千兆以太网（1 Gbps）
- 远程连接：100 Mbps+ 网络，低延迟

## 📝 实现进度

### v2.6.0（已完成）

- [x] 性能分析文档
- [x] 游戏模式核心模块
- [x] 配置支持
- [x] 预设模式（4种）
- [x] 性能指标类
- [x] 自适应质量控制器
- [x] 帧跳过器

### v2.7.0（计划中）

- [ ] 集成到 SSE 服务器
- [ ] 提高 FPS 限制（10 → 60）
- [ ] WebSocket 游戏流端点
- [ ] 游戏模式 MCP 工具
- [ ] 性能监控端点
- [ ] 单元测试和集成测试

### v2.8.0（未来）

- [ ] 区域捕获优化
- [ ] 游戏窗口检测
- [ ] 预设配置文件
- [ ] 性能可视化仪表板
- [ ] GPU 客户端解码支持

## 🔗 相关文档

- [GAMING_MODE_ANALYSIS.md](GAMING_MODE_ANALYSIS.md) - 详细性能分析
- [README.md](README.md) - 项目文档
- [CHANGELOG.md](CHANGELOG.md) - 更新日志
- [MCP_SSE_GUIDE.md](MCP_SSE_GUIDE.md) - SSE 模式指南

## 💡 最佳实践

### 1. 性能优化建议

```python
# ✅ 好：使用游戏模式预设
config = GameStreamConfig(mode=PerformanceMode.PERFORMANCE)

# ✅ 好：启用帧跳过
config.enable_frame_skip = True

# ✅ 好：启用自适应质量
config.adaptive_quality = True

# ❌ 差：禁用帧跳过且追求高 FPS
config.enable_frame_skip = False
config.fps = 120  # 会导致延迟累积

# ❌ 差：高 FPS + 高质量 + PNG
config.fps = 120
config.quality = 95
config.format = "png"  # 性能灾难
```

### 2. 监控性能

```python
# 定期检查性能指标
metrics = frame_metrics.get_stats()

# 警告：丢帧率过高
if metrics['drop_rate_percent'] > 5.0:
    logger.warning("High drop rate, consider reducing FPS or quality")

# 警告：帧时间过长
if metrics['p95_frame_time_ms'] > target_frame_time:
    logger.warning("Frame time too high, enable adaptive quality")
```

### 3. 渐进式优化

```
第一步：使用平衡模式（30 FPS, 75% quality）
  ↓ 如果性能充足
第二步：提升到性能模式（60 FPS, 50% quality）
  ↓ 如果仍然充足
第三步：尝试极限模式（120 FPS, 30% quality）
  ↓ 如果出现问题
回退：降低 FPS 或启用自适应质量
```

## 🤝 贡献

欢迎贡献游戏模式相关的改进！

**优先需求：**
1. 不同游戏的性能测试数据
2. 更多的预设配置
3. WebSocket 实现
4. 性能优化建议

---

**版本**: v2.6.0
**最后更新**: 2025-11-18
**维护者**: inkbytefo
