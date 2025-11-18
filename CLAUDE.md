# CLAUDE.md - AI Assistant Guide for ScreenMonitorMCP v2

> **Last Updated:** 2025-11-18
> **Version:** 2.0.9
> **Purpose:** Comprehensive guide for AI assistants working on this codebase

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture & Design Philosophy](#architecture--design-philosophy)
3. [Repository Structure](#repository-structure)
4. [Core Modules & Components](#core-modules--components)
5. [Development Workflows](#development-workflows)
6. [Testing Guidelines](#testing-guidelines)
7. [Configuration & Environment](#configuration--environment)
8. [Common Tasks & Patterns](#common-tasks--patterns)
9. [Troubleshooting](#troubleshooting)
10. [Important Architectural Considerations](#important-architectural-considerations)

---

## Project Overview

**ScreenMonitorMCP v2** is a Model Context Protocol (MCP) server that provides AI assistants with real-time vision capabilities through screen capture and analysis. It bridges the gap between AI and visual computing.

### Key Capabilities

- **Screen Capture**: Cross-platform screenshot capabilities using `mss` library
- **AI Analysis**: Vision-based screen content analysis (currently via external APIs)
- **Streaming**: Real-time screen streaming with memory integration
- **Memory System**: Persistent SQLite storage for analysis results
- **Multi-Protocol**: Supports MCP (stdio), HTTP/SSE, and WebSocket protocols

### Primary Use Cases

- UI/UX analysis and testing
- Visual debugging assistance
- Automated documentation and screenshots
- Accessibility compliance checking
- System monitoring and performance tracking

---

## Architecture & Design Philosophy

### Design Principles

1. **Single Responsibility**: Each module has one clear purpose
2. **Async First**: All I/O operations use async/await
3. **Type Safety**: Comprehensive type hints with Pydantic models
4. **Clean Architecture**: Clear separation between protocol, service, and data layers
5. **Resource Management**: Built-in limits, pooling, and cleanup mechanisms

### Architecture Layers

```
┌─────────────────────────────────────────────────────┐
│  Protocol Layer (MCP, HTTP/SSE, WebSocket)          │
│  - mcp_server.py, server/routes.py                  │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  Core Services Layer                                 │
│  - AI Service, Screen Capture, Streaming, Memory    │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  Data & Configuration Layer                          │
│  - Models (Pydantic), Config, Database Pool         │
└─────────────────────────────────────────────────────┘
```

### Three Modes of Operation

1. **MCP Server Mode** (stdio transport)
   - Entry: `python -m screenmonitormcp_v2.mcp_main`
   - For: Claude Desktop and MCP clients
   - Protocol: JSON-RPC over stdin/stdout

2. **HTTP/SSE Server Mode**
   - Entry: `python -m screenmonitormcp_v2`
   - For: Web applications and REST APIs
   - Protocol: HTTP REST + Server-Sent Events

3. **CLI Mode**
   - Entry: `screenmonitormcp-v2-cli [command]`
   - For: Testing, automation, and debugging

---

## Repository Structure

```
screenmonitormcp/
├── screenmonitormcp_v2/              # Main package
│   ├── __init__.py                   # Package initialization
│   ├── __main__.py                   # HTTP server entry point
│   ├── mcp_main.py                   # MCP server entry point
│   ├── cli.py                        # Click-based CLI
│   │
│   ├── core/                         # Core business logic
│   │   ├── ai_service.py             # AI vision & analysis [KEY]
│   │   ├── screen_capture.py         # mss-based capture [KEY]
│   │   ├── streaming.py              # Stream management [KEY]
│   │   ├── memory_system.py          # SQLite persistence [KEY]
│   │   ├── database_pool.py          # Connection pooling
│   │   ├── mcp_server.py             # FastMCP implementation [KEY]
│   │   ├── connection.py             # WebSocket connections
│   │   ├── command_handler.py        # WS command processing
│   │   └── performance_monitor.py    # System health monitoring
│   │
│   ├── server/                       # HTTP/SSE server
│   │   ├── app.py                    # FastAPI factory
│   │   ├── config.py                 # Unified configuration [KEY]
│   │   ├── routes.py                 # API route handlers
│   │   └── main.py                   # Server entry point
│   │
│   └── models/                       # Data models
│       ├── requests.py               # Request schemas
│       └── responses.py              # Response schemas
│
├── tests/                            # Test suite
│   ├── test_api.py                   # API endpoint tests
│   ├── test_integration.py           # Integration tests
│   └── conftest.py                   # Pytest fixtures
│
├── mcp_main.py                       # Root MCP entry (legacy)
├── mcp_debug.py                      # MCP debugging tools
├── mcp_client_examples.py            # Usage examples
│
├── pyproject.toml                    # Modern packaging [KEY]
├── requirements.txt                  # Core dependencies
├── requirements-dev.txt              # Dev tools
├── requirements-test.txt             # Test dependencies
│
├── Dockerfile                        # Multi-stage build
├── .env.example                      # Environment template
├── .gitignore                        # Git ignore patterns
│
├── README.md                         # User documentation
├── MCP_SETUP_GUIDE.md               # MCP client setup
├── CONTRIBUTING.md                  # Contribution guide
├── CHANGELOG.md                     # Version history
└── CLAUDE.md                        # This file
```

**[KEY]** = Critical files to understand before making changes

---

## Core Modules & Components

### 1. AI Service (`core/ai_service.py`)

**Purpose:** Unified AI vision and analysis service

**Key Responsibilities:**
- Image analysis via vision models
- Chat completion support
- Memory-integrated analysis
- Specialized detection (UI elements, anomalies, performance)

**Important Methods:**
```python
async def analyze_image(
    image_data: str,          # Base64 encoded image
    prompt: str,              # Analysis prompt
    model: Optional[str] = None,
    max_tokens: int = 1000
) -> str:
    """Analyze image with AI vision model"""

async def chat_completion(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    max_tokens: int = 500
) -> str:
    """Generate text completion"""

async def detect_ui_elements(
    image_data: str,
    element_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Detect UI elements in screenshot"""
```

**Configuration:**
- `OPENAI_API_KEY` - Required
- `OPENAI_BASE_URL` - Supports OpenRouter, Azure, etc.
- `OPENAI_MODEL` - Model identifier
- `OPENAI_TIMEOUT` - Request timeout (default: 30s)

**Current Implementation:** Uses OpenAI-compatible API

**⚠️ Architectural Note:** Currently requires external AI API. See [Important Architectural Considerations](#important-architectural-considerations).

### 2. Screen Capture (`core/screen_capture.py`)

**Purpose:** Cross-platform screen capture using `mss`

**Key Methods:**
```python
async def capture_screen(
    monitor_id: int = 0,
    region: Optional[Dict[str, int]] = None,
    format: str = "png",
    quality: int = 85
) -> Dict[str, Any]:
    """
    Capture screenshot and return as base64

    Returns:
        {
            "image": "base64_encoded_data",
            "format": "png",
            "monitor": 0,
            "width": 1920,
            "height": 1080,
            "timestamp": "2025-11-18T10:30:00Z"
        }
    """

async def get_monitors() -> List[Dict[str, int]]:
    """Get list of available monitors"""
```

**Important Details:**
- Uses `mss` library (faster than PIL.ImageGrab)
- Async execution to prevent blocking
- Supports region-based capture
- Quality control for JPEG format
- Multi-monitor detection

**Common Patterns:**
```python
# Capture primary monitor
result = await capture_screen(monitor_id=0)

# Capture specific region
result = await capture_screen(
    monitor_id=0,
    region={"left": 100, "top": 100, "width": 800, "height": 600}
)

# Low-quality for streaming
result = await capture_screen(format="jpeg", quality=50)
```

### 3. Streaming (`core/streaming.py`)

**Purpose:** Real-time screen streaming with memory integration

**Key Features:**
- Multiple concurrent streams
- FPS and quality control
- Frame buffering
- Memory integration (stores analysis periodically)
- Automatic cleanup

**Stream Lifecycle:**
```python
# 1. Create stream
stream_id = await streaming.create_stream(
    monitor_id=0,
    fps=5,
    quality=75,
    analyze_frames=True,
    analysis_interval=10  # Analyze every 10th frame
)

# 2. Start streaming
await streaming.start_stream(stream_id)

# 3. Broadcast frames (automatic in background)
# Frames sent via WebSocket/SSE to subscribers

# 4. Stop stream
await streaming.stop_stream(stream_id)
```

**Resource Limits:**
- `MAX_CONCURRENT_STREAMS` - Default: 25
- `MAX_STREAM_FPS` - Default: 10
- `MAX_STREAM_QUALITY` - Default: 75

### 4. Memory System (`core/memory_system.py`)

**Purpose:** Persistent storage for AI analysis results

**Database Schema:**
```sql
CREATE TABLE memory_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT,
    tags TEXT
);
```

**Key Methods:**
```python
async def add_entry(
    entry_type: str,        # "screen_analysis", "ui_detection", etc.
    content: str,           # Analysis result
    metadata: Optional[Dict] = None,
    tags: Optional[List[str]] = None
) -> int:
    """Store analysis result"""

async def query_entries(
    entry_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    tags: Optional[List[str]] = None,
    limit: int = 100
) -> List[Dict]:
    """Retrieve stored analyses"""

async def cleanup_old_entries(
    retention_hours: int = 24
) -> int:
    """Remove old entries"""
```

**Storage Location:** `~/.screenmonitormcp/memory.db`

**Connection Pool:** Uses `database_pool.py` for connection management

### 5. MCP Server (`core/mcp_server.py`)

**Purpose:** Model Context Protocol implementation using FastMCP

**Available Tools (20+):**

**Screen Analysis:**
- `analyze_screen` - Capture and analyze with AI
- `analyze_image` - Analyze provided image
- `detect_ui_elements` - UI element detection
- `assess_system_performance` - Performance analysis
- `detect_anomalies` - Anomaly detection

**Streaming:**
- `create_stream` - Initialize stream
- `list_streams` - Get active streams
- `start_stream` - Begin streaming
- `stop_stream` - Stop streaming
- `get_stream_info` - Stream details

**Memory:**
- `query_memory` - Search stored analyses
- `add_memory_entry` - Store custom data
- `analyze_scene_from_memory` - Multi-frame analysis
- `cleanup_old_memories` - Cleanup task

**System:**
- `get_system_status` - Health check
- `get_performance_metrics` - Resource usage
- `get_database_pool_stats` - DB pool statistics
- `database_pool_health_check` - DB health

**Tool Implementation Pattern:**
```python
@mcp.tool()
async def analyze_screen(
    monitor_id: int = 0,
    prompt: str = "Analyze this screen",
    store_in_memory: bool = True
) -> str:
    """
    Capture and analyze screen with AI

    Args:
        monitor_id: Monitor to capture (0 = primary)
        prompt: Analysis instructions
        store_in_memory: Save result to memory

    Returns:
        AI analysis result as string
    """
    # 1. Capture screen
    capture_result = await screen_capture.capture_screen(monitor_id)

    # 2. Analyze with AI
    analysis = await ai_service.analyze_image(
        capture_result["image"],
        prompt
    )

    # 3. Store in memory
    if store_in_memory:
        await memory_system.add_entry(
            entry_type="screen_analysis",
            content=analysis,
            metadata={"monitor": monitor_id, "prompt": prompt}
        )

    return analysis
```

**Protocol Compliance:**
- Minimal logging (stderr only, INFO level minimum)
- Proper error handling and serialization
- No stdout contamination

### 6. Configuration (`server/config.py`)

**Purpose:** Unified configuration management using Pydantic Settings

**Configuration Structure:**
```python
class Config(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    api_key: Optional[str] = None

    # AI Provider
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"
    openai_timeout: int = 30

    # Streaming
    max_stream_fps: int = 10
    max_stream_quality: int = 75
    max_concurrent_streams: int = 25

    # Performance
    max_connections: int = 250
    connection_timeout: int = 20
    request_timeout: int = 30

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    class Config:
        env_file = ".env"
        case_sensitive = False
```

**Usage:**
```python
from screenmonitormcp_v2.server.config import get_config

config = get_config()
api_key = config.openai_api_key
```

---

## Development Workflows

### Setting Up Development Environment

```bash
# 1. Clone repository
git clone https://github.com/inkbytefo/ScreenMonitorMCP.git
cd ScreenMonitorMCP

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -e .                    # Core package
pip install -r requirements-dev.txt  # Dev tools
pip install -r requirements-test.txt # Test tools

# 4. Copy environment template
cp .env.example .env
# Edit .env with your API keys

# 5. Run tests
pytest

# 6. Start development server
python -m screenmonitormcp_v2
```

### Code Quality Standards

**Black** (formatting):
```bash
black screenmonitormcp_v2/
black tests/
```

**isort** (import sorting):
```bash
isort screenmonitormcp_v2/
isort tests/
```

**mypy** (type checking):
```bash
mypy screenmonitormcp_v2/
```

**flake8** (linting):
```bash
flake8 screenmonitormcp_v2/
```

**Run all checks:**
```bash
black . && isort . && mypy . && flake8 . && pytest
```

### Git Workflow

**Branch Naming:**
- `feature/feature-name` - New features
- `bugfix/bug-name` - Bug fixes
- `docs/doc-name` - Documentation
- `refactor/refactor-name` - Code refactoring
- `test/test-name` - Test improvements

**Commit Message Format:**
```
<type>: <description>

[optional body]

[optional footer]
```

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `test` - Test additions/changes
- `refactor` - Code refactoring
- `perf` - Performance improvements
- `chore` - Maintenance tasks

**Example:**
```
feat: add OCR text extraction to screen capture

- Implement Tesseract integration
- Add text extraction method to screen_capture.py
- Update analyze_screen tool to include OCR
- Add tests for text extraction

Closes #123
```

### Making Changes

**Step-by-Step Workflow:**

1. **Create feature branch:**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes and test:**
   ```bash
   # Edit files
   # Run tests
   pytest tests/test_my_feature.py -v
   ```

3. **Format and lint:**
   ```bash
   black .
   isort .
   mypy .
   flake8 .
   ```

4. **Commit changes:**
   ```bash
   git add .
   git commit -m "feat: add my feature"
   ```

5. **Push and create PR:**
   ```bash
   git push -u origin feature/my-feature
   # Create PR on GitHub
   ```

### Adding a New MCP Tool

**Example: Adding `extract_text` tool**

1. **Add method to appropriate service** (e.g., `screen_capture.py`):
   ```python
   async def extract_text_from_screen(
       monitor_id: int = 0,
       region: Optional[Dict[str, int]] = None
   ) -> str:
       """Extract text from screen using OCR"""
       # Implementation
       pass
   ```

2. **Add tool to `mcp_server.py`:**
   ```python
   @mcp.tool()
   async def extract_text(
       monitor_id: int = 0,
       region: Optional[Dict[str, int]] = None
   ) -> str:
       """
       Extract text from screen using OCR

       Args:
           monitor_id: Monitor to capture
           region: Optional region to extract from

       Returns:
           Extracted text
       """
       return await screen_capture.extract_text_from_screen(
           monitor_id, region
       )
   ```

3. **Add tests** (`tests/test_api.py`):
   ```python
   async def test_extract_text():
       result = await screen_capture.extract_text_from_screen(0)
       assert isinstance(result, str)
   ```

4. **Update documentation** (README.md, MCP_SETUP_GUIDE.md)

5. **Add to CHANGELOG.md:**
   ```markdown
   ## [Unreleased]
   ### Added
   - New `extract_text` MCP tool for OCR text extraction
   ```

### Adding a New API Endpoint

**Example: Adding `/api/v2/extract-text` endpoint**

1. **Add to `server/routes.py`:**
   ```python
   @router.post("/api/v2/extract-text")
   async def extract_text_endpoint(
       request: ExtractTextRequest,
       api_key: str = Depends(verify_api_key)
   ):
       """Extract text from screen"""
       try:
           result = await screen_capture.extract_text_from_screen(
               request.monitor_id,
               request.region
           )
           return ExtractTextResponse(text=result)
       except Exception as e:
           logger.error("text_extraction_failed", error=str(e))
           raise HTTPException(status_code=500, detail=str(e))
   ```

2. **Add models to `models/`:**
   ```python
   # models/requests.py
   class ExtractTextRequest(BaseModel):
       monitor_id: int = 0
       region: Optional[Dict[str, int]] = None

   # models/responses.py
   class ExtractTextResponse(BaseModel):
       text: str
   ```

3. **Add tests:**
   ```python
   def test_extract_text_endpoint(client, api_key):
       response = client.post(
           "/api/v2/extract-text",
           json={"monitor_id": 0},
           headers={"Authorization": f"Bearer {api_key}"}
       )
       assert response.status_code == 200
   ```

---

## Testing Guidelines

### Test Structure

```
tests/
├── conftest.py              # Fixtures and configuration
├── test_api.py             # API endpoint tests
└── test_integration.py     # Integration tests
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=screenmonitormcp_v2 --cov-report=html

# Run specific test file
pytest tests/test_api.py -v

# Run specific test
pytest tests/test_api.py::test_health_endpoint -v

# Run with markers
pytest -m "not slow"
pytest -m integration
```

### Writing Tests

**Unit Test Example:**
```python
import pytest
from screenmonitormcp_v2.core import screen_capture

@pytest.mark.asyncio
async def test_capture_screen_basic():
    """Test basic screen capture"""
    result = await screen_capture.capture_screen(monitor_id=0)

    assert "image" in result
    assert "format" in result
    assert result["format"] == "png"
    assert len(result["image"]) > 0

@pytest.mark.asyncio
async def test_capture_screen_invalid_monitor():
    """Test capture with invalid monitor"""
    with pytest.raises(ValueError):
        await screen_capture.capture_screen(monitor_id=999)
```

**API Test Example:**
```python
def test_list_streams_endpoint(client, api_key):
    """Test GET /api/v2/streams"""
    response = client.get(
        "/api/v2/streams",
        headers={"Authorization": f"Bearer {api_key}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "streams" in data
    assert isinstance(data["streams"], list)
```

**Integration Test Example:**
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_analysis_workflow():
    """Test complete screen capture -> AI analysis workflow"""
    # 1. Capture screen
    capture = await screen_capture.capture_screen(0)

    # 2. Analyze with AI
    analysis = await ai_service.analyze_image(
        capture["image"],
        "What is on this screen?"
    )

    # 3. Store in memory
    entry_id = await memory_system.add_entry(
        entry_type="screen_analysis",
        content=analysis,
        tags=["integration_test"]
    )

    # 4. Verify storage
    entries = await memory_system.query_entries(
        tags=["integration_test"]
    )

    assert len(entries) > 0
    assert entries[0]["content"] == analysis
```

### Test Fixtures

**Common fixtures in `conftest.py`:**
```python
import pytest
from fastapi.testclient import TestClient
from screenmonitormcp_v2.server.app import create_app

@pytest.fixture
def app():
    """Create FastAPI app for testing"""
    return create_app()

@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)

@pytest.fixture
def api_key():
    """Get API key for authenticated requests"""
    return "test-api-key-123"

@pytest.fixture
async def clean_database():
    """Clean database before test"""
    await memory_system.clear_all()
    yield
    await memory_system.clear_all()
```

### Test Markers

```python
# Slow tests (skip by default)
@pytest.mark.slow
def test_long_running_operation():
    pass

# Integration tests
@pytest.mark.integration
async def test_integration():
    pass

# Unit tests
@pytest.mark.unit
def test_unit():
    pass
```

---

## Configuration & Environment

### Environment Variables

**Required:**
- `OPENAI_API_KEY` - AI service API key

**Optional:**
```bash
# Server
HOST=0.0.0.0
PORT=8000
API_KEY=your-secret-key

# AI Provider
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=gpt-4o
OPENAI_TIMEOUT=30

# Streaming
MAX_STREAM_FPS=10
MAX_STREAM_QUALITY=75
MAX_CONCURRENT_STREAMS=25

# Performance
MAX_CONNECTIONS=250
CONNECTION_TIMEOUT=20
REQUEST_TIMEOUT=30

# Database
DB_POOL_MIN_SIZE=1
DB_POOL_MAX_SIZE=10
DB_RETENTION_HOURS=24

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Configuration Files

**`.env`** - Local environment (not in git)
```env
OPENAI_API_KEY=sk-your-actual-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
```

**`claude_desktop_config.json`** - MCP client configuration
```json
{
  "mcpServers": {
    "screenmonitormcp-v2": {
      "command": "python",
      "args": ["-m", "screenmonitormcp_v2.mcp_main"],
      "env": {
        "OPENAI_API_KEY": "your-key",
        "OPENAI_MODEL": "gpt-4o"
      }
    }
  }
}
```

### Logging Configuration

**Structured Logging with structlog:**
```python
import structlog

logger = structlog.get_logger()

# Good logging practices
logger.info("stream_created", stream_id=stream_id, fps=fps)
logger.warning("connection_timeout", connection_id=conn_id)
logger.error("capture_failed", monitor=monitor_id, error=str(e))
```

**Log Levels:**
- `DEBUG` - Detailed debugging information
- `INFO` - General informational messages
- `WARNING` - Warning messages
- `ERROR` - Error messages
- `CRITICAL` - Critical errors

**⚠️ MCP Server Logging:**
- Use stderr only
- Minimum level: INFO
- No stdout contamination
- JSON format for structured parsing

---

## Common Tasks & Patterns

### Task 1: Adding Support for a New AI Provider

**Example: Adding Anthropic Claude support**

1. **Update `core/ai_service.py`:**
   ```python
   async def analyze_image_anthropic(
       self,
       image_data: str,
       prompt: str,
       model: str = "claude-3.5-sonnet-20250219"
   ) -> str:
       """Analyze image using Anthropic Claude"""
       # Implementation using anthropic library
       pass
   ```

2. **Add to config:**
   ```python
   # server/config.py
   anthropic_api_key: Optional[str] = None
   use_anthropic: bool = False
   ```

3. **Update `.env.example`:**
   ```env
   ANTHROPIC_API_KEY=your-key
   USE_ANTHROPIC=false
   ```

### Task 2: Implementing Image Preprocessing

**Add to `screen_capture.py`:**
```python
async def preprocess_image(
    image_data: str,
    resize: Optional[Tuple[int, int]] = None,
    enhance: bool = False,
    grayscale: bool = False
) -> str:
    """
    Preprocess image before analysis

    Args:
        image_data: Base64 encoded image
        resize: Target size (width, height)
        enhance: Apply image enhancement
        grayscale: Convert to grayscale

    Returns:
        Preprocessed base64 image
    """
    # Decode base64
    img_bytes = base64.b64decode(image_data)
    img = Image.open(io.BytesIO(img_bytes))

    # Apply transformations
    if resize:
        img = img.resize(resize)
    if grayscale:
        img = img.convert("L")
    if enhance:
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)

    # Encode back to base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()
```

### Task 3: Adding Custom Memory Queries

**Extend `memory_system.py`:**
```python
async def query_by_content(
    self,
    search_text: str,
    fuzzy: bool = False
) -> List[Dict]:
    """
    Search memory by content text

    Args:
        search_text: Text to search for
        fuzzy: Enable fuzzy matching

    Returns:
        Matching memory entries
    """
    async with self.pool.get_connection() as conn:
        if fuzzy:
            query = """
                SELECT * FROM memory_entries
                WHERE content LIKE ?
                ORDER BY timestamp DESC
            """
            cursor = await conn.execute(query, (f"%{search_text}%",))
        else:
            query = """
                SELECT * FROM memory_entries
                WHERE content = ?
                ORDER BY timestamp DESC
            """
            cursor = await conn.execute(query, (search_text,))

        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
```

### Task 4: Performance Optimization

**Common optimization patterns:**

1. **Use connection pooling:**
   ```python
   # Good
   async with database_pool.get_connection() as conn:
       result = await conn.execute(query)

   # Bad - creates new connection each time
   conn = await aiosqlite.connect("memory.db")
   ```

2. **Batch operations:**
   ```python
   # Good - batch insert
   async with pool.get_connection() as conn:
       await conn.executemany(
           "INSERT INTO memory_entries (...) VALUES (...)",
           entries
       )

   # Bad - individual inserts
   for entry in entries:
       await add_entry(entry)
   ```

3. **Use async for I/O:**
   ```python
   # Good
   async def capture():
       return await asyncio.to_thread(blocking_capture)

   # Bad - blocks event loop
   def capture():
       return blocking_capture()
   ```

---

## Troubleshooting

### Common Issues

#### Issue: MCP Server Not Starting

**Symptoms:**
- Claude Desktop shows "Server failed to start"
- No response from MCP tools

**Solutions:**
1. Check Claude Desktop logs:
   ```bash
   # macOS
   tail -f ~/Library/Logs/Claude/mcp*.log

   # Windows
   type %APPDATA%\Claude\logs\mcp*.log
   ```

2. Verify Python path:
   ```bash
   which python  # Should match claude_desktop_config.json
   ```

3. Test manually:
   ```bash
   python -m screenmonitormcp_v2.mcp_main
   # Should not error, waits for input
   ```

4. Check environment variables:
   ```bash
   # Required
   echo $OPENAI_API_KEY
   ```

#### Issue: AI Analysis Failing

**Symptoms:**
- `analyze_screen` returns errors
- "API key invalid" messages

**Solutions:**
1. Verify API key:
   ```bash
   curl -H "Authorization: Bearer $OPENAI_API_KEY" \
        https://api.openai.com/v1/models
   ```

2. Check API URL:
   ```python
   # For OpenRouter
   OPENAI_BASE_URL=https://openrouter.ai/api/v1

   # For OpenAI
   OPENAI_BASE_URL=https://api.openai.com/v1
   ```

3. Test model availability:
   ```bash
   # Check if model exists
   curl https://openrouter.ai/api/v1/models
   ```

#### Issue: Screen Capture Black Screen

**Symptoms:**
- Screenshots are completely black
- Empty or corrupted images

**Solutions:**
1. Check display permissions (macOS):
   - System Preferences → Security & Privacy → Screen Recording
   - Enable for Terminal/Python

2. Test with different monitor:
   ```python
   await capture_screen(monitor_id=1)  # Try different IDs
   ```

3. Check monitor list:
   ```python
   monitors = await get_monitors()
   print(monitors)
   ```

#### Issue: Memory Database Locked

**Symptoms:**
- "Database is locked" errors
- Memory queries failing

**Solutions:**
1. Check connection pool:
   ```python
   stats = await database_pool.get_stats()
   print(stats)
   ```

2. Enable WAL mode (already default):
   ```python
   # In database_pool.py
   await conn.execute("PRAGMA journal_mode=WAL")
   ```

3. Increase timeout:
   ```python
   # In database_pool.py
   timeout = 30.0  # Increase from default
   ```

#### Issue: High Memory Usage

**Symptoms:**
- Process using excessive RAM
- Out of memory errors

**Solutions:**
1. Limit concurrent streams:
   ```env
   MAX_CONCURRENT_STREAMS=10  # Reduce from 25
   ```

2. Reduce stream quality:
   ```env
   MAX_STREAM_QUALITY=50  # Reduce from 75
   ```

3. Enable aggressive cleanup:
   ```env
   DB_RETENTION_HOURS=1  # Reduce from 24
   ```

4. Monitor performance:
   ```python
   metrics = await performance_monitor.get_metrics()
   print(metrics["memory_usage"])
   ```

### Debugging Tips

**Enable debug logging:**
```bash
LOG_LEVEL=DEBUG python -m screenmonitormcp_v2
```

**Test MCP tools independently:**
```python
# In Python REPL
from screenmonitormcp_v2.core import screen_capture, ai_service

# Test capture
result = await screen_capture.capture_screen(0)
print(f"Captured: {len(result['image'])} bytes")

# Test AI
analysis = await ai_service.analyze_image(
    result["image"],
    "What is on this screen?"
)
print(analysis)
```

**Monitor database:**
```bash
sqlite3 ~/.screenmonitormcp/memory.db
> SELECT COUNT(*) FROM memory_entries;
> SELECT * FROM memory_entries ORDER BY timestamp DESC LIMIT 5;
```

**Check WebSocket connections:**
```python
from screenmonitormcp_v2.core import connection_manager

stats = connection_manager.get_statistics()
print(f"Active connections: {stats['active_connections']}")
```

---

## Important Architectural Considerations

### ✅ External AI Dependency - RESOLVED (v2.1+)

**Previous Design (v2.0.x - Deprecated):**
- Required external AI API (OpenAI, OpenRouter, etc.)
- Added complexity with API keys and external dependencies
- Security concerns with API key management
- Additional costs for API usage

**⚠️ Architectural Concern Raised:**

> "I think requiring additional models is not good. We should try to let the MCP client execute completely - this is safer and more conventional."

**✅ NEW Architecture (v2.1+ - IMPLEMENTED):**

The system has been refactored to follow MCP best practices by leveraging the MCP client's built-in AI capabilities:

1. **✅ Simplified Security**: No API key management needed
2. **✅ Reduced Dependencies**: OpenAI API is now optional
3. **✅ Improved Privacy**: No data sent to external services by default
4. **✅ Lower Costs**: No API usage fees required
5. **✅ Better Integration**: Claude Desktop and other MCP clients handle analysis

**Implementation:**

**NEW Recommended Tool:**
```python
@mcp.tool()
async def capture_screen_image(
    monitor: int = 0,
    format: str = "png",
    quality: int = 85,
    include_metadata: bool = True
) -> str:
    """Capture screen and return raw image data for client-side analysis

    This is the RECOMMENDED approach - capture the image and let the MCP client
    (like Claude Desktop) analyze it using its own vision capabilities.
    """
    capture = await screen_capture.capture_screen(monitor)
    return json.dumps({
        "success": True,
        "image_base64": capture["image_data"],
        "format": format,
        "monitor": monitor,
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "width": capture.get("width"),
            "height": capture.get("height")
        }
    })
```

**Workflow:**
1. User asks Claude: "What's on my screen?"
2. Claude calls `capture_screen_image(monitor=0)`
3. Tool returns base64 image data
4. Claude analyzes image using its own vision model
5. Claude responds with analysis

**Legacy Tools (Deprecated but maintained):**
- `analyze_screen` - Marked as deprecated, requires external AI
- `detect_ui_elements` - Marked as deprecated
- `assess_system_performance` - Marked as deprecated
- `detect_anomalies` - Marked as deprecated
- `generate_monitoring_report` - Marked as deprecated
- `chat_completion` - Marked as deprecated

All deprecated tools now display helpful messages guiding users to use `capture_screen_image` instead.

**Migration Path:**
- Existing users can continue using legacy tools if they have AI API configured
- New users should use `capture_screen_image` (no configuration needed)
- See MIGRATION.md for detailed upgrade instructions

**Benefits Achieved:**
- **Simpler Setup**: Works out of the box, no API keys needed
- **More Secure**: No external API key management
- **Standard Compliance**: Follows MCP protocol best practices
- **Privacy-Focused**: Images not sent to external services
- **Cost-Free**: No AI API usage charges
- **Better Performance**: Direct client analysis, no network latency

### Other Design Considerations

**1. Database Choice:**
- Currently using SQLite (lightweight, serverless)
- Consider PostgreSQL for production deployments
- Redis for caching and real-time features

**2. Streaming Architecture:**
- Current: In-process streaming
- Consider: Separate streaming service for scalability
- WebRTC for peer-to-peer streaming

**3. Performance Monitoring:**
- Add OpenTelemetry for distributed tracing
- Prometheus metrics export
- Grafana dashboards

**4. Security:**
- Add rate limiting
- Implement request signing
- Add audit logging
- Consider encryption at rest for memory DB

---

## Quick Reference

### Essential Commands

```bash
# Development
python -m screenmonitormcp_v2              # Start HTTP server
python -m screenmonitormcp_v2.mcp_main    # Start MCP server
screenmonitormcp-v2-cli serve             # CLI server mode

# Testing
pytest                                     # Run all tests
pytest --cov                              # With coverage
pytest -v -k "test_name"                  # Specific test

# Code Quality
black .                                    # Format code
isort .                                    # Sort imports
mypy .                                     # Type check
flake8 .                                   # Lint

# Docker
docker build -t screenmonitormcp .        # Build image
docker run -p 8000:8000 screenmonitormcp  # Run container

# Package
python -m build                           # Build distribution
pip install -e .                          # Install editable
```

### Key Files to Check Before Changes

1. `core/mcp_server.py` - MCP tool definitions
2. `server/config.py` - Configuration settings
3. `core/ai_service.py` - AI integration
4. `core/screen_capture.py` - Screen capture logic
5. `pyproject.toml` - Dependencies and metadata
6. `tests/` - Existing test coverage

### Documentation to Update

When making changes, update:
- `CHANGELOG.md` - Version history
- `README.md` - User-facing documentation
- `MCP_SETUP_GUIDE.md` - MCP client setup
- `CLAUDE.md` - This file (AI assistant guide)
- Docstrings in code
- Type hints

### Getting Help

- **Issues**: https://github.com/inkbytefo/ScreenMonitorMCP/issues
- **Discussions**: GitHub Discussions
- **Documentation**: README.md, MCP_SETUP_GUIDE.md
- **Examples**: mcp_client_examples.py

---

## Version History

- **v2.0.9** (2025-11-18): Dependencies cleanup, removed 11 unused packages
- **v2.0.7** (Recent): Major architecture refactoring, 40-50% memory reduction
- **v2.0.5** (Recent): Enhanced AI monitor analysis capabilities

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

---

**Last Updated:** 2025-11-18
**Maintainer:** [inkbytefo](https://github.com/inkbytefo)
**For AI Assistants:** This guide is designed to help you understand and contribute to the ScreenMonitorMCP codebase effectively.
