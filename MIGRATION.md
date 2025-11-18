# Migration Guide: v2.0.x → v2.1+ (Client-Side Analysis)

## Overview

ScreenMonitorMCP v2.1+ introduces a significant architectural improvement that makes the system simpler, more secure, and follows MCP best practices.

**What Changed:**
- **Before (v2.0.x)**: Server performed AI analysis using external APIs (OpenAI, OpenRouter)
- **After (v2.1+)**: Server only captures screens; your MCP client analyzes images with its own vision model

**Why This Change:**
- ✅ **No API Keys Required** - Works out of the box
- ✅ **More Secure** - No external API key management
- ✅ **Better Privacy** - Images not sent to third-party services
- ✅ **Cost-Free** - No AI API usage charges
- ✅ **Simpler Setup** - Just install and use
- ✅ **Follows MCP Best Practices** - Let the client do what it does best

## For New Users

**You don't need to do anything special!**

1. Install ScreenMonitorMCP:
   ```bash
   pip install screenmonitormcp-v2
   ```

2. Add to Claude Desktop config (no API keys needed):
   ```json
   {
     "mcpServers": {
       "screenmonitormcp-v2": {
         "command": "python",
         "args": ["-m", "screenmonitormcp_v2.mcp_main"]
       }
     }
   }
   ```

3. Restart Claude Desktop and start using:
   ```
   User: "What's on my screen right now?"
   Claude: *uses capture_screen_image tool*
   Claude: "I can see..."
   ```

That's it! No configuration files, no API keys, no complexity.

## For Existing Users (Upgrading from v2.0.x)

### Option 1: Migrate to Client-Side Analysis (Recommended)

**Benefits:** Simpler, more secure, no API costs

**Steps:**

1. **Update your Claude Desktop config:**

   **Old configuration (v2.0.x):**
   ```json
   {
     "mcpServers": {
       "screenmonitormcp-v2": {
         "command": "python",
         "args": ["-m", "screenmonitormcp_v2.mcp_main"],
         "env": {
           "OPENAI_API_KEY": "sk-...",
           "OPENAI_BASE_URL": "https://api.openai.com/v1",
           "OPENAI_MODEL": "gpt-4o"
         }
       }
     }
   }
   ```

   **New configuration (v2.1+):**
   ```json
   {
     "mcpServers": {
       "screenmonitormcp-v2": {
         "command": "python",
         "args": ["-m", "screenmonitormcp_v2.mcp_main"]
       }
     }
   }
   ```

2. **Remove or update your `.env` file:**

   You can remove these variables (they're now optional):
   ```env
   # No longer required
   # OPENAI_API_KEY=sk-...
   # OPENAI_BASE_URL=https://api.openai.com/v1
   # OPENAI_MODEL=gpt-4o
   ```

3. **Update your usage patterns:**

   **Old approach (still works but deprecated):**
   ```
   User: "Analyze my screen for UI issues"
   Claude: *uses analyze_screen tool (requires API key)*
   ```

   **New approach (recommended):**
   ```
   User: "Look at my screen and identify any UI issues"
   Claude: *uses capture_screen_image tool*
   Claude: *analyzes with own vision model*
   Claude: "I can see several UI issues..."
   ```

4. **Restart Claude Desktop**

### Option 2: Keep Using Server-Side Analysis (Not Recommended)

**When to use:** If you have specific requirements for server-side analysis

**Note:** This approach is deprecated and may be removed in future versions.

**Steps:**

1. Keep your existing configuration with API keys
2. The deprecated tools will continue to work:
   - `analyze_screen`
   - `detect_ui_elements`
   - `assess_system_performance`
   - `detect_anomalies`
   - `generate_monitoring_report`

3. Be aware of deprecation warnings in tool descriptions

## Tool Migration Reference

### Primary Screen Capture Tool

| v2.0.x | v2.1+ | Status | Notes |
|--------|-------|--------|-------|
| N/A | `capture_screen_image` | ✅ **NEW & RECOMMENDED** | Returns raw image data for client analysis |

### Deprecated Tools (Still functional but not recommended)

| Tool | Status | Recommended Alternative |
|------|--------|------------------------|
| `analyze_screen` | ⚠️ Deprecated | Use `capture_screen_image` + ask client to analyze |
| `detect_ui_elements` | ⚠️ Deprecated | Use `capture_screen_image` + ask "identify UI elements" |
| `assess_system_performance` | ⚠️ Deprecated | Use `capture_screen_image` + ask about performance |
| `detect_anomalies` | ⚠️ Deprecated | Use `capture_screen_image` + ask about anomalies |
| `generate_monitoring_report` | ⚠️ Deprecated | Use `capture_screen_image` + ask for report |
| `chat_completion` | ⚠️ Deprecated | Use your MCP client's native chat |
| `list_ai_models` | ⚠️ Deprecated | Not needed with client-side analysis |
| `get_ai_status` | ⚠️ Deprecated | Not needed with client-side analysis |

### Unchanged Tools (Still fully supported)

| Tool | Status | Notes |
|------|--------|-------|
| `create_stream` | ✅ Supported | Streaming functionality unchanged |
| `list_streams` | ✅ Supported | Stream management unchanged |
| `stop_stream` | ✅ Supported | Stream control unchanged |
| `get_stream_info` | ✅ Supported | Stream info unchanged |
| `get_performance_metrics` | ✅ Supported | System metrics unchanged |
| `get_system_status` | ✅ Supported | Status monitoring unchanged |
| `query_memory` | ✅ Supported | Memory system unchanged |
| All database tools | ✅ Supported | Database management unchanged |

## Common Migration Scenarios

### Scenario 1: UI/UX Testing

**Old approach:**
```
User: "Detect all UI elements on my screen"
→ Uses analyze_screen or detect_ui_elements (requires API)
```

**New approach:**
```
User: "Look at my screen and identify all UI elements"
→ Claude uses capture_screen_image
→ Claude analyzes with own vision model
→ No API key needed
```

### Scenario 2: Performance Monitoring

**Old approach:**
```
User: "Assess the system performance shown on screen"
→ Uses assess_system_performance (requires API)
```

**New approach:**
```
User: "What does the system performance look like?"
→ Claude uses capture_screen_image
→ Claude analyzes performance metrics
→ More natural conversation
```

### Scenario 3: Anomaly Detection

**Old approach:**
```
User: "Detect any anomalies on my screen"
→ Uses detect_anomalies (requires API)
```

**New approach:**
```
User: "Do you see anything unusual on my screen?"
→ Claude uses capture_screen_image
→ Claude identifies anomalies
→ More conversational
```

## Troubleshooting

### Issue: "External AI service not configured" error

**Solution:** This means you're trying to use a deprecated tool without API keys.

**Option A (Recommended):** Switch to client-side analysis
- Simply ask Claude naturally: "What's on my screen?"
- Claude will use `capture_screen_image` automatically

**Option B:** Configure external AI (not recommended)
- Add `OPENAI_API_KEY` to your environment
- See `.env.example` for configuration options

### Issue: Tool not working after migration

**Checklist:**
1. ✅ Restart Claude Desktop after config changes
2. ✅ Verify tool is not deprecated (check tool list above)
3. ✅ For deprecated tools, switch to `capture_screen_image`
4. ✅ Check Claude Desktop logs for errors

### Issue: Image quality concerns

**Solutions:**
- Adjust quality parameter: `capture_screen_image(quality=95)`
- Use PNG format for higher quality: `capture_screen_image(format="png")`
- Default PNG at 85 quality is recommended for most use cases

## Benefits Summary

### Before Migration (v2.0.x)

- ❌ Required external AI API configuration
- ❌ API key management complexity
- ❌ Additional costs for AI API usage
- ❌ Privacy concerns (images sent to external services)
- ❌ Network latency for analysis
- ❌ Dependency on external service availability

### After Migration (v2.1+)

- ✅ No external AI API required
- ✅ No API key management
- ✅ No additional costs
- ✅ Better privacy (client-side analysis)
- ✅ Faster analysis (no network calls)
- ✅ Works offline (for capture)
- ✅ Follows MCP best practices
- ✅ Simpler setup and maintenance

## FAQ

**Q: Will my existing code break?**
A: No. Deprecated tools still work if you have API keys configured. You'll just see deprecation notices.

**Q: When will deprecated tools be removed?**
A: They will be maintained for several major versions to allow smooth migration. An announcement will be made before removal.

**Q: Can I use both approaches?**
A: Yes, but it's not recommended. Choose one approach for consistency.

**Q: What if my MCP client doesn't have vision capabilities?**
A: You can continue using the deprecated server-side analysis tools with API configuration.

**Q: Is the new approach as accurate?**
A: Yes! Modern MCP clients like Claude Desktop have excellent vision models. Often better than using external APIs.

**Q: What about the memory system?**
A: Memory system works with both approaches. Client-side analysis results can still be stored.

**Q: Can I still use streaming?**
A: Yes! Streaming is unchanged and works with both approaches.

## Need Help?

- **Documentation**: See [CLAUDE.md](CLAUDE.md) for detailed technical information
- **Issues**: Report problems at https://github.com/inkbytefo/ScreenMonitorMCP/issues
- **Setup Guide**: See [MCP_SETUP_GUIDE.md](MCP_SETUP_GUIDE.md) for configuration help

---

**Recommendation:** Migrate to client-side analysis (Option 1) for the best experience. It's simpler, more secure, and follows MCP best practices.
