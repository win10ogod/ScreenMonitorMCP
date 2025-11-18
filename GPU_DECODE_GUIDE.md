# GPU Decode Support Guide

> **Version:** 2.7.0
> **Purpose:** Client-side GPU-accelerated decoding for gaming streams
> **Last Updated:** 2025-11-18

## Overview

While ScreenMonitorMCP v2.7+ provides server-side GPU-accelerated **capture** (DXGI/WGC on Windows), this guide focuses on client-side GPU-accelerated **decoding** for optimal gaming stream performance.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Server (ScreenMonitorMCP v2.7+)                        │
│  ┌────────────────┐     ┌────────────────┐            │
│  │ GPU Capture    │ --> │ JPEG Encode    │ ─┐         │
│  │ (DXGI/WGC)     │     │ (CPU/GPU)      │  │         │
│  └────────────────┘     └────────────────┘  │         │
└─────────────────────────────────────────────┼─────────┘
                                              │
                            Network (WebSocket/SSE)
                                              │
┌─────────────────────────────────────────────┼─────────┐
│  Client                                     │         │
│                                             ▼         │
│  ┌────────────────┐     ┌────────────────────────┐   │
│  │ JPEG Decode    │ --> │ GPU Rendering          │   │
│  │ (GPU-accel)    │     │ (WebGL/Canvas)         │   │
│  └────────────────┘     └────────────────────────┘   │
└───────────────────────────────────────────────────────┘
```

## Client-Side GPU Decoding

### Web Browsers (Recommended)

Modern browsers provide automatic GPU-accelerated JPEG/PNG decoding:

**Supported Browsers:**
- **Chrome/Edge**: Hardware-accelerated by default
- **Firefox**: GPU-accelerated since version 75+
- **Safari**: Metal-accelerated on macOS

**Optimal Setup:**
1. Use Chrome/Edge for best performance
2. Enable hardware acceleration in settings
3. Use `<img>` tags or Canvas API for rendering
4. Consider WebGL for advanced rendering

**Example Implementation:**

```javascript
// WebSocket client with GPU-accelerated rendering
const ws = new WebSocket('ws://localhost:8000/mcp/game-stream');

// Create canvas for rendering
const canvas = document.getElementById('game-canvas');
const ctx = canvas.getContext('2d');

ws.onmessage = async (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'frame') {
        // Browser automatically uses GPU for JPEG decoding
        const img = new Image();
        img.onload = () => {
            // GPU-accelerated rendering
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        };
        img.src = 'data:image/jpeg;base64,' + message.data;
    }
};
```

### WebGL GPU Rendering

For maximum performance with post-processing:

```javascript
// WebGL-based GPU rendering
const gl = canvas.getContext('webgl2');

// Create texture
const texture = gl.createTexture();
gl.bindTexture(gl.TEXTURE_2D, texture);

async function renderFrame(base64Image) {
    const img = new Image();
    img.onload = () => {
        gl.bindTexture(gl.TEXTURE_2D, texture);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);

        // GPU-accelerated texture rendering
        // ... WebGL rendering code ...
    };
    img.src = 'data:image/jpeg;base64,' + base64Image;
}
```

### Native Applications

For native desktop applications consuming the gaming stream:

#### Python (PyQt/PySide)

```python
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel
import base64

class GameStreamViewer:
    def __init__(self):
        self.label = QLabel()
        # Qt automatically uses GPU for rendering when available

    def display_frame(self, base64_data):
        # Decode base64
        image_bytes = base64.b64decode(base64_data)

        # QImage uses GPU-accelerated decoding
        qimage = QImage.fromData(image_bytes)
        pixmap = QPixmap.fromImage(qimage)

        # GPU-accelerated rendering
        self.label.setPixmap(pixmap)
```

#### C++ (Qt with Hardware Acceleration)

```cpp
#include <QLabel>
#include <QPixmap>
#include <QImage>

class GameStreamViewer : public QWidget {
private:
    QLabel* imageLabel;

public:
    void displayFrame(const QByteArray& jpegData) {
        // Qt uses hardware acceleration automatically
        QImage image = QImage::fromData(jpegData, "JPEG");

        // GPU-accelerated rendering
        imageLabel->setPixmap(QPixmap::fromImage(image));
    }
};
```

#### Rust (GPU-accelerated with wgpu)

```rust
use image;
use wgpu;
use base64;

async fn render_frame(base64_data: &str, device: &wgpu::Device, queue: &wgpu::Queue) {
    // Decode base64
    let image_bytes = base64::decode(base64_data).unwrap();

    // Decode JPEG (CPU, but fast)
    let img = image::load_from_memory(&image_bytes).unwrap();

    // Upload to GPU texture
    let dimensions = img.dimensions();
    let rgba = img.to_rgba8();

    let texture = device.create_texture(&wgpu::TextureDescriptor {
        size: wgpu::Extent3d {
            width: dimensions.0,
            height: dimensions.1,
            depth_or_array_layers: 1,
        },
        // ... texture configuration
    });

    // Copy to GPU
    queue.write_texture(
        texture.as_image_copy(),
        &rgba,
        wgpu::ImageDataLayout { /* ... */ },
        texture.size(),
    );

    // GPU rendering happens here
}
```

## Performance Optimization

### 1. Format Selection

**JPEG (Recommended for Gaming):**
- ✅ Smaller file size → Lower network latency
- ✅ Hardware-accelerated decoding in most browsers
- ✅ Better for high FPS scenarios
- ❌ Lossy compression

**PNG (For High Quality):**
- ✅ Lossless compression
- ✅ Better for screenshots/documentation
- ❌ Larger file size → Higher network latency
- ❌ Slower decoding

**Recommendation:**
```javascript
// For gaming (60+ FPS)
use_gaming_preset('competitive_gaming')  // Uses JPEG at 50% quality

// For screenshots
use_gaming_preset('screenshot')  // Uses PNG at 95% quality
```

### 2. Resolution and Quality Trade-offs

**Competitive Gaming (60 FPS):**
```json
{
  "fps": 60,
  "quality": 50,
  "format": "jpeg",
  "expected_decode_time_ms": "2-4"
}
```

**Esports (120 FPS):**
```json
{
  "fps": 120,
  "quality": 30,
  "format": "jpeg",
  "expected_decode_time_ms": "1-2"
}
```

### 3. Browser Optimization

**Enable Hardware Acceleration:**

**Chrome/Edge:**
1. Go to `chrome://settings/system`
2. Enable "Use hardware acceleration when available"
3. Restart browser

**Firefox:**
1. Go to `about:preferences`
2. Enable "Use recommended performance settings"
3. Enable "Use hardware acceleration when available"

**Safari:**
- Hardware acceleration enabled by default on macOS

### 4. Canvas Optimization

```javascript
// Use OffscreenCanvas for background decoding
const offscreen = canvas.transferControlToOffscreen();
const worker = new Worker('decode-worker.js');
worker.postMessage({ canvas: offscreen }, [offscreen]);

// Worker handles decoding in parallel
// decode-worker.js
self.onmessage = (e) => {
    const ctx = e.data.canvas.getContext('2d');
    // Decode and render frames here
};
```

## Platform-Specific Recommendations

### Windows

**Best Setup:**
- **Server:** DXGI/WGC capture (GPU-accelerated)
- **Client:** Chrome/Edge browser
- **Format:** JPEG 50-75% quality
- **Expected Total Latency:** 8-12ms (60 FPS)

```bash
# Install Windows optimization
pip install pywin32

# Verify GPU capture is active
get_capture_backend_info()
# Should show: "Windows Optimization Active: True"
```

### macOS

**Best Setup:**
- **Server:** MSS capture (CPU-based)
- **Client:** Safari or Chrome
- **Format:** JPEG 60-75% quality
- **Expected Total Latency:** 12-18ms (30-60 FPS)

### Linux

**Best Setup:**
- **Server:** MSS capture
- **Client:** Chrome/Firefox
- **Format:** JPEG 50-70% quality
- **Expected Total Latency:** 10-15ms (60 FPS)

## Measuring Client Performance

### Browser Performance API

```javascript
// Measure decode + render time
const startTime = performance.now();

const img = new Image();
img.onload = () => {
    ctx.drawImage(img, 0, 0);
    const endTime = performance.now();
    console.log(`Decode + Render: ${endTime - startTime}ms`);
};
img.src = 'data:image/jpeg;base64,' + frameData;
```

### Full Pipeline Latency

```javascript
let serverTimestamp;

ws.onmessage = (event) => {
    const clientReceiveTime = performance.now();
    const message = JSON.parse(event.data);

    if (message.type === 'frame') {
        const serverTime = new Date(message.metadata.timestamp).getTime();
        const networkLatency = clientReceiveTime - serverTime;

        const img = new Image();
        img.onload = () => {
            const renderStart = performance.now();
            ctx.drawImage(img, 0, 0);
            const renderEnd = performance.now();

            const totalLatency = renderEnd - serverTime;
            const decodeRender = renderEnd - clientReceiveTime;

            console.log(`
                Network: ${networkLatency}ms
                Decode+Render: ${decodeRender}ms
                Total: ${totalLatency}ms
            `);
        };
        img.src = 'data:image/jpeg;base64,' + message.data;
    }
};
```

## Advanced: Video Codec Hardware Decoding

For even better performance, consider using video codecs with hardware decoding:

### H.264 Hardware Decoding

**Server-side (Future Enhancement):**
```python
# Encode frames to H.264 using GPU
# Requires additional implementation
```

**Client-side:**
```javascript
// Use MediaSource API for H.264 hardware decoding
const mediaSource = new MediaSource();
video.src = URL.createObjectURL(mediaSource);

mediaSource.addEventListener('sourceopen', () => {
    const sourceBuffer = mediaSource.addSourceBuffer('video/mp4; codecs="avc1.42E01E"');

    // Browser uses GPU hardware decoder automatically
    ws.onmessage = (event) => {
        const h264Data = event.data;
        sourceBuffer.appendBuffer(h264Data);
    };
});
```

**Benefits:**
- ✅ 10-50x better compression than JPEG
- ✅ Hardware decoding on all modern GPUs
- ✅ Lower network bandwidth
- ❌ Requires more complex server implementation
- ❌ Additional latency from video encoding

## Troubleshooting

### Issue: High Client CPU Usage

**Solution 1: Verify Hardware Acceleration**
```javascript
// Check if canvas is hardware accelerated
const canvas = document.getElementById('game-canvas');
const ctx = canvas.getContext('2d', {
    alpha: false,
    desynchronized: true  // Allows GPU to run independently
});

console.log('Hardware acceleration:', ctx.getContextAttributes());
```

**Solution 2: Reduce Quality**
```javascript
// Lower server-side quality
use_gaming_preset('competitive_gaming', quality=40);
```

### Issue: Stuttering/Frame Drops

**Solution 1: Use RequestAnimationFrame**
```javascript
let latestFrame = null;

ws.onmessage = (event) => {
    latestFrame = event.data;
};

function render() {
    if (latestFrame) {
        const img = new Image();
        img.onload = () => {
            ctx.drawImage(img, 0, 0);
        };
        img.src = 'data:image/jpeg;base64,' + latestFrame;
        latestFrame = null;
    }
    requestAnimationFrame(render);
}
requestAnimationFrame(render);
```

**Solution 2: Enable Frame Skipping**
```javascript
// Server-side
use_gaming_preset('competitive_gaming', fps=60);
// Frame skipping enabled by default in competitive presets
```

### Issue: High Latency

**Checklist:**
1. ✅ Server GPU capture enabled (Windows)
2. ✅ Client hardware acceleration enabled
3. ✅ Using WebSocket (not SSE)
4. ✅ Using JPEG format
5. ✅ Quality 30-60%
6. ✅ Frame skipping enabled
7. ✅ Low network latency

## Performance Targets

### Target Breakdown (60 FPS Gaming)

| Component | Target | Description |
|-----------|--------|-------------|
| Server Capture | 1-3ms | DXGI/WGC GPU capture |
| Server Encode | 1-2ms | JPEG compression |
| Network | 1-5ms | LAN: <1ms, Internet: 5-50ms |
| Client Decode | 2-4ms | GPU-accelerated JPEG decode |
| Client Render | 1-2ms | Canvas/WebGL rendering |
| **Total** | **6-16ms** | **Achievable for 60 FPS** |

### Expected Performance by Preset

| Preset | FPS | Quality | Total Latency | GPU Required |
|--------|-----|---------|---------------|--------------|
| Screenshot | 1 | 95% | 50-100ms | No |
| Casual Gaming | 30 | 75% | 8-12ms | No |
| **Competitive** | 60 | 50% | 5-8ms | Recommended |
| **Esports** | 120 | 30% | 3-5ms | **Required** |

## Future Enhancements

### Planned (Not Yet Implemented)

1. **VP9/AV1 Video Encoding**
   - Better compression than H.264
   - Hardware encoding/decoding support
   - Lower bandwidth usage

2. **WebCodecs API**
   - Native browser video codec access
   - Lower latency than MediaSource
   - Better control over encoding parameters

3. **WebGPU Compute Shaders**
   - Custom GPU decoders
   - Post-processing effects
   - Upscaling/downscaling

4. **WebRTC Data Channels**
   - Peer-to-peer streaming
   - Automatic quality adaptation
   - Built-in congestion control

## Resources

**Browser APIs:**
- [Canvas API](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API)
- [WebGL](https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API)
- [MediaSource API](https://developer.mozilla.org/en-US/docs/Web/API/MediaSource)
- [WebCodecs API](https://developer.mozilla.org/en-US/docs/Web/API/WebCodecs_API)

**Performance:**
- [Performance API](https://developer.mozilla.org/en-US/docs/Web/API/Performance)
- [requestAnimationFrame](https://developer.mozilla.org/en-US/docs/Web/API/window/requestAnimationFrame)

**ScreenMonitorMCP Docs:**
- [Gaming Mode Implementation](GAMING_MODE_IMPLEMENTATION.md)
- [Gaming Mode Analysis](GAMING_MODE_ANALYSIS.md)
- [README](README.md)

---

**Last Updated:** 2025-11-18
**Version:** 2.7.0
**Maintainer:** [inkbytefo](https://github.com/inkbytefo)
