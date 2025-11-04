# Step 5: Backend - Resource Detection & Stockfish Config

## Overview

Implement system resource detection to help users configure Stockfish optimally based on their hardware capabilities. This will provide automatic detection of CPU cores and available RAM, allowing the application to suggest optimal Stockfish configuration.

## Goals

1. **Add psutil Library**
   - Install `psutil` for system resource detection
   - Verify it works in Docker container

2. **Create System Resources Endpoint**
   - Implement `GET /api/system-resources` endpoint
   - Return CPU core count
   - Return total RAM amount
   - Return available RAM
   - Provide recommended settings based on hardware

3. **Extend Settings Logic**
   - Validate Stockfish path exists and is executable
   - Validate thread count is within system limits
   - Validate hash size is within available RAM
   - Update PUT /api/settings with validation

## Implementation Plan

### 1. Dependencies

Add to `requirements.txt`:
```
psutil
```

### 2. System Resources Service

Create `backend/app/services/system_resources.py`:
- Detect CPU cores (physical and logical)
- Detect total RAM
- Detect available RAM
- Calculate recommended Stockfish settings
- Validate Stockfish binary path

### 3. API Endpoint

Create `GET /api/system-resources`:
```json
{
  "cpu": {
    "physical_cores": 4,
    "logical_cores": 8,
    "recommended_threads": 6
  },
  "memory": {
    "total_mb": 16384,
    "available_mb": 8192,
    "recommended_hash_mb": 2048
  },
  "stockfish": {
    "path": "/app/stockfish/stockfish_binary",
    "exists": true,
    "executable": true
  }
}
```

### 4. Settings Validation

Extend `PUT /api/settings`:
- Validate Stockfish path exists
- Validate threads <= logical_cores
- Validate hash_mb <= available_memory
- Return validation errors with helpful messages

## Expected Outcomes

After implementation:
- ✅ Users can see their system capabilities
- ✅ Application suggests optimal Stockfish settings
- ✅ Settings validation prevents invalid configurations
- ✅ Frontend can display hardware info
- ✅ Better user experience with smart defaults

## Technical Details

### psutil Usage

```python
import psutil

# CPU information
physical_cores = psutil.cpu_count(logical=False)
logical_cores = psutil.cpu_count(logical=True)

# Memory information
memory = psutil.virtual_memory()
total_mb = memory.total / (1024 * 1024)
available_mb = memory.available / (1024 * 1024)
```

### Recommended Settings Logic

**Threads:**
- Leave 1-2 cores for system
- Recommended: max(1, logical_cores - 2)

**Hash Size:**
- Use 10-20% of available RAM
- Minimum: 128 MB
- Maximum: min(available_ram * 0.2, 2048)

### Stockfish Path Validation

```python
import os

def validate_stockfish_path(path: str) -> tuple[bool, str]:
    if not os.path.exists(path):
        return False, "Path does not exist"
    if not os.path.isfile(path):
        return False, "Path is not a file"
    if not os.access(path, os.X_OK):
        return False, "File is not executable"
    return True, "Valid"
```

## Testing Plan

1. **Test Resource Detection:**
   - Verify CPU count is accurate
   - Verify RAM detection is correct
   - Test in Docker container

2. **Test Stockfish Validation:**
   - Test with valid path
   - Test with invalid path
   - Test with non-executable file

3. **Test Settings Validation:**
   - Try to set threads > cpu_count
   - Try to set hash > available_ram
   - Verify error messages are helpful

## Next Steps After Completion

1. **Frontend Integration:**
   - Display system resources on Settings page
   - Show recommended values
   - Add "Use Recommended" button

2. **Auto-Configuration:**
   - Detect on first run
   - Apply recommended settings
   - Allow user override

3. **Performance Monitoring:**
   - Track Stockfish resource usage
   - Alert if settings are suboptimal

## Notes

- psutil works in Docker containers
- Container sees host resources if no limits set
- May need to adjust for container resource limits
- Stockfish binary should be validated on startup

---

**Status:** 🚧 In Progress
**Priority:** High
**Dependencies:** Backend Step 1-3 completed
