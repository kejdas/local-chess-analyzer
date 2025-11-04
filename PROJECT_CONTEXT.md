# Local Chess Analyzer - AI Agent Context Guide

> **For AI Agents:** This document is structured to help you quickly understand the project state, make informed decisions, and avoid known pitfalls. Critical sections are marked with 🚨 and common patterns with ✅.

---

## 🎯 Quick Start: What You Need to Know First

### Project Identity
- **Name:** Local Chess Analyzer
- **Purpose:** Self-hosted Chess.com game analysis using Stockfish
- **Current Phase:** Steps 1-7 Complete → **Next: Step 8 (Stockfish Analysis Integration)**
- **Last Updated:** November 4, 2025
- **Project Root:** `/root/docker/local-chess-analyzer/`

### Critical "Don't Break This" Rules 🚨
1. **Date Format:** Database uses `YYYY.MM.DD` (dots), API uses `YYYY-MM-DD` (dashes) - convert at boundaries
2. **Filtering:** Always filter at SQL level BEFORE pagination (never client-side for paginated data)
3. **Routing:** Use hash-based routing `#/path` (NOT path-based `/path`)
4. **Docker Commands:** Always use full path: `docker compose -f /root/docker/local-chess-analyzer/docker-compose.yml ...`
5. **Permissions:** Set 0666 on DB file, 0777 on data directory on every startup
6. **Multi-Player:** Never assume single player - always support player selection
7. **WAL Checkpoint:** Call `PRAGMA wal_checkpoint(TRUNCATE)` before serving DB files

### User Preferences (High Priority)
- **Professional UI:** Modern, card-based design with clean styling
- **Clear Feedback:** Loading states, success messages, error notifications
- **Confirmation Dialogs:** Always confirm destructive actions
- **Fast Performance:** Keep API responses under 50ms
- **No Unnecessary Complexity:** Simple, direct solutions preferred

---

## 📁 File Locations (Absolute Paths)

### Critical Files You'll Modify Often
```
Backend:
  /root/docker/local-chess-analyzer/backend/app/api/games.py          # Game endpoints
  /root/docker/local-chess-analyzer/backend/app/crud/games.py         # DB queries
  /root/docker/local-chess-analyzer/backend/app/models.py             # Schema

Frontend:
  /root/docker/local-chess-analyzer/frontend/src/lib/components/Games.svelte    # Games UI
  /root/docker/local-chess-analyzer/frontend/src/lib/components/Settings.svelte # Settings UI
  /root/docker/local-chess-analyzer/frontend/src/lib/api/client.js              # API calls

Database:
  /root/docker/local-chess-analyzer/data/games.db                     # SQLite DB

Docker:
  /root/docker/local-chess-analyzer/docker-compose.yml                # Services config
```

### When to Edit Each File
```
Adding Filter?
  → backend/app/api/games.py      (add query param)
  → backend/app/crud/games.py     (add WHERE clause)
  → frontend/src/lib/components/Games.svelte  (add UI control)
  → frontend/src/lib/api/client.js (update API call)

New API Endpoint?
  → backend/app/api/[module].py   (create function)
  → frontend/src/lib/api/client.js (add client function)
  → frontend/src/lib/components/[Component].svelte (call function)

Schema Change?
  → backend/app/models.py         (modify model)
  → backend/app/crud/*.py         (update queries)
  → frontend/src/lib/components/*.svelte (update UI)
  ⚠️  Requires database recreation!

UI Change?
  → frontend/src/lib/components/*.svelte (component)
  → frontend/src/app.css (global styles if needed)
```

---

## 🏗️ Tech Stack & Architecture

### Backend (FastAPI + SQLAlchemy)
```python
# Ports & Access
Backend API: http://192.168.0.102:42069
API Docs:    http://192.168.0.102:42069/docs

# Key Libraries
FastAPI      # Web framework
SQLAlchemy   # ORM (async mode)
aiosqlite    # Async SQLite driver
python-chess # PGN parsing
psutil       # System resources
```

**Architecture Pattern:**
```
Request → API Layer (validation) → CRUD Layer (queries) → Database
         ↑                         ↑
    Services (business logic)  Models (schema)
```

### Frontend (Svelte 5)
```javascript
// Ports & Access
Frontend: http://192.168.0.102:6969/#/

// Stack
Svelte 5              // Framework
Vite 7                // Build tool
svelte-spa-router     // Hash-based routing (#/path)
Fetch API             // HTTP client
Vanilla CSS           // Styling
```

**Component Pattern:**
```
App.svelte (router) → Page Components → API Client → Backend
                           ↓
                    Reactive State ($:)
```

### Database (SQLite)
```sql
-- Location: /app/data/games.db (inside container)
-- Host:     /root/docker/local-chess-analyzer/data/games.db

-- Two Tables Only:
games     # 9 columns (id, chess_com_id, pgn, players, result, dates, analysis)
settings  # 2 columns (key, value) - key-value store
```

---

## 🗄️ Database Schema (Detailed Reference)

### Games Table
```sql
CREATE TABLE games (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    chess_com_id     TEXT UNIQUE NOT NULL,        -- e.g., "12345678901"
    pgn              TEXT NOT NULL,               -- Full PGN notation
    white_player     TEXT NOT NULL,               -- e.g., "Hikaru"
    black_player     TEXT NOT NULL,               -- e.g., "orzelmocnygaz"
    result           TEXT NOT NULL,               -- "1-0" | "0-1" | "1/2-1/2"
    game_date        TEXT NOT NULL,               -- "YYYY.MM.DD" (DOTS! Not dashes)
    import_date      DATETIME DEFAULT CURRENT_TIMESTAMP,
    analysis_status  TEXT DEFAULT 'queued',       -- 'queued' | 'analyzing' | 'completed'
    analysis_data    TEXT                         -- JSON string or NULL
);

-- Indexes (recommended but not yet added - technical debt)
-- CREATE INDEX idx_game_date ON games(game_date);
-- CREATE INDEX idx_analysis_status ON games(analysis_status);
-- CREATE INDEX idx_white_player ON games(white_player);
-- CREATE INDEX idx_black_player ON games(black_player);
```

**Important Notes:**
- `chess_com_id` is UNIQUE - prevents duplicate imports
- `game_date` uses DOTS not dashes (convert when querying!)
- `analysis_data` is TEXT field storing JSON (not JSON type)
- `result` values are standard PGN format

### Settings Table
```sql
CREATE TABLE settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);

-- Current Settings (key → value):
chess_com_username → "" (empty string initially)
stockfish_threads  → "4"
stockfish_hash     → "512"
analysis_depth     → "20"
analysis_time_ms   → "1000"
```

**Pattern:** Settings stored as strings, converted to int/bool in code

---

## 🌐 API Endpoints (Complete Reference)

### Games Endpoints
```http
GET /api/games
  Query Params:
    - skip: int = 0                # Pagination offset
    - limit: int = 20              # Results per page (max 1000)
    - date_from: str = None        # "YYYY-MM-DD" (dashes!)
    - date_to: str = None          # "YYYY-MM-DD" (dashes!)
    - status: str = None           # "queued" | "analyzing" | "completed"
    - sort_by: str = "date"        # "date" | "result" | "status"
    - sort_order: str = "desc"     # "asc" | "desc"
  
  Response:
    {
      "games": [...],              # List of game objects
      "total": 873,                # Total matching games
      "skip": 0,
      "limit": 20
    }

GET /api/games/stats
  Response:
    {
      "total_games": 873,
      "queued": 0,
      "analyzing": 0,
      "completed": 873,
      "last_sync": "2025-11-04T18:30:00"
    }
```

### Settings Endpoints
```http
GET /api/settings
  Response: { "chess_com_username": "", "stockfish_threads": "4", ... }

PUT /api/settings
  Body: { "chess_com_username": "Hikaru", ... }
  Validation: Threads ≤ CPU cores, Hash ≤ Available RAM
  Response: { ...updated_settings... }
```

### Sync Endpoints
```http
POST /api/sync
  Body: { "username": "Hikaru" }
  Background Task: Fetches games from Chess.com
  Response: { "status": "started", "message": "..." }

GET /api/sync/status
  Response: { "status": "idle|syncing|completed", "progress": { ... } }
```

### Database Management
```http
GET /api/database/download
  Response: Binary .db file (timestamped filename)
  🚨 Runs WAL checkpoint first!

POST /api/database/upload
  Body: multipart/form-data with .db file
  🚨 Creates backup before replacing!
  Response: { "success": true, "game_count": 873 }

DELETE /api/database/clear
  Response: { "success": true, "deleted_count": 873 }
  🚨 Runs VACUUM after delete!

POST /api/database/initialize
  Response: { "success": true }
```

### System Resources
```http
GET /api/system-resources
  Response: {
    "cpu": { "physical": 4, "logical": 8 },
    "memory": { "total": 16GB, "available": 8GB },
    "stockfish": { "path": "/app/stockfish/...", "valid": true }
  }
```

---

## 🚨 Critical Implementation Details (Must Know!)

### 1. Date Format Hell (Biggest Gotcha!)
```
🔴 WRONG:
  - Store dates in database with dashes: "2025-11-04"
  - Use dots in API: "2025.11.04"
  - Mix formats anywhere

✅ CORRECT Pattern:
  Frontend:  Uses "YYYY-MM-DD" (native <input type="date">)
      ↓
  API:       Receives "YYYY-MM-DD"
      ↓
  Backend:   Converts to "YYYY.MM.DD" for SQL query
      ↓
  Database:  Stores "YYYY.MM.DD"
      ↓
  Response:  Returns "YYYY.MM.DD" to frontend
      ↓
  Frontend:  Displays as-is or converts for date inputs

Code Example (backend):
  date_from = request.args.get('date_from')  # "2025-11-04"
  date_from_db = date_from.replace('-', '.') # "2025.11.04"
  query = query.where(Game.game_date >= date_from_db)
```

### 2. Filter Architecture (Avoid Pagination Bug!)
```
🔴 WRONG:
  1. Backend returns 20 games (page 1)
  2. Frontend filters those 20 games
  3. User sees 0 results even though 100 matches exist
  Problem: Filtering paginated data = broken!

✅ CORRECT:
  1. Frontend sends filter params to backend
  2. Backend applies WHERE clauses in SQL
  3. Backend paginates AFTER filtering
  4. Frontend receives correct page of filtered data

Backend Filters (SQL WHERE):
  - Date range
  - Status
  - Sort order

Client-Side Filters (JavaScript):
  - Player name + Result (needs game context)
  - Text search (real-time, current page only)

Why split? Backend filtering is required for pagination to work.
Client-side filtering is for UX (instant feedback, no API call).
```

### 3. Multi-Player Database Pattern
```
❌ BAD: Assume database has one player
✅ GOOD: Support multiple players

Pattern:
  1. Let user select/enter player name
  2. Filter results by that player
  3. Calculate wins/losses/draws for that player
  4. Case-insensitive matching

Example:
  User selects: "hikaru" (lowercase)
  Database has: "Hikaru" (capitalized)
  Match: white_player.lower() == "hikaru" OR black_player.lower() == "hikaru"
```

### 4. Svelte Reactive Statement Patterns
```javascript
// 🔴 WRONG - Causes infinite loop:
$: if (dateFrom !== undefined || statusFilter !== undefined) {
  loadGames(); // Sets loading = true → triggers this again!
}

// ✅ CORRECT - Use guard flag:
let hasInitialLoad = false;

$: if (hasInitialLoad && (dateFrom || statusFilter !== 'all')) {
  currentPage = 0;  // Reset pagination
  loadGames();
}

onMount(async () => {
  await loadGames();
  hasInitialLoad = true;  // Enable reactive statements
});
```

### 5. Database Operations Checklist
```bash
# Before downloading database:
✅ Call PRAGMA wal_checkpoint(TRUNCATE)
✅ Create unique temp file
✅ Set cache-busting headers

# Before uploading database:
✅ Create backup of current DB
✅ Validate file is SQLite
✅ Check for required tables
✅ Dispose engine after replacing

# After deleting data:
✅ Run VACUUM to reclaim space
✅ Dispose engine to force write

# On every startup:
✅ Set directory permissions to 0777
✅ Set DB file permissions to 0666
```

### 6. Routing Configuration (Must Use Hash!)
```javascript
// ✅ CORRECT (current implementation):
import Router from 'svelte-spa-router';
<Router routes={{
  '/': Home,
  '/games': Games,
  '/settings': Settings
}} />

// URLs: http://host:6969/#/games

// 🔴 WRONG (causes blank pages):
import { Router } from 'svelte-routing';
// Had compatibility issues in production
```

### 7. API URL Dynamic Resolution
```javascript
// ✅ CORRECT (works across network):
const API_BASE_URL = window.location.hostname === 'localhost'
  ? 'http://localhost:42069'
  : `http://${window.location.hostname}:42069`;

// 🔴 WRONG (only works on localhost):
const API_BASE_URL = 'http://localhost:42069';
```

---

## 🎨 UI/UX Patterns (User Expectations)

### Color Coding Standards
```css
/* Status Badges */
.completed { background: #27ae60; color: white; }  /* Green */
.analyzing { background: #f39c12; color: white; }  /* Orange */
.queued    { background: #3498db; color: white; }  /* Blue */
.error     { background: #e74c3c; color: white; }  /* Red */

/* Action Buttons */
.success   { background: #27ae60; }  /* Download, Save */
.warning   { background: #f39c12; }  /* Upload, Edit */
.danger    { background: #e74c3c; }  /* Delete, Clear */
```

### Feedback Pattern
```javascript
// Every user action needs feedback:
1. Loading State
   - Show spinner or "Loading..."
   - Disable button while processing

2. Success Feedback
   - Show success message
   - Auto-dismiss after 3-5 seconds
   - Update UI immediately

3. Error Handling
   - Show error message
   - Keep visible until dismissed
   - Provide actionable guidance

Example:
  loading = true;
  try {
    await api.doSomething();
    showSuccess("Action completed!");
    await refreshData();
  } catch (err) {
    showError(`Failed: ${err.message}`);
  } finally {
    loading = false;
  }
```

### Confirmation Dialogs (Destructive Actions)
```javascript
// Always confirm before:
- Deleting data
- Clearing database
- Uploading database (replaces data)

Pattern:
  if (!confirm('⚠️ WARNING: This will delete all games!\nThis cannot be undone.')) {
    return;
  }
  // Proceed with action...
```

---

## 🐛 Known Issues & Their Solutions

### Issue History (Don't Repeat These!)

#### 1. Date Filtering Not Working ✅ FIXED
```
Problem: Set date filter, got 0 results
Root Cause: Client-side filtering on paginated data
Solution: Moved filtering to backend SQL queries
When: November 3, 2025
```

#### 2. Download Caching Old Data ✅ FIXED
```
Problem: Downloaded file had old data
Root Cause: Browser cached response + no WAL checkpoint
Solution: Unique temp files + WAL checkpoint + unique ETags
When: November 4, 2025
```

#### 3. Readonly Database ✅ FIXED
```
Problem: "attempt to write a readonly database"
Root Cause: Insufficient permissions
Solution: Set 0666 on file, 0777 on dir at startup
When: November 4, 2025
```

#### 4. Infinite Loading Loop ✅ FIXED
```
Problem: Page stuck on "Loading..."
Root Cause: Reactive statement triggering itself
Solution: Added hasInitialLoad guard flag
When: November 3, 2025
```

#### 5. Blank Pages ✅ FIXED
```
Problem: Navigation worked but pages empty
Root Cause: svelte-routing compatibility issues
Solution: Switched to svelte-spa-router with hash routing
When: October 30, 2025
```

---

## 🔧 Common Development Tasks

### Task 1: Add New Filter to Games List
```bash
Step 1: Backend - API Layer (api/games.py)
  def get_all_games(..., new_filter: Optional[str] = None):
      # Add parameter

Step 2: Backend - CRUD Layer (crud/games.py)
  if new_filter:
      query = query.where(Game.column == new_filter)

Step 3: Frontend - API Client (client.js)
  export function getGames({ newFilter, ... }) {
      const params = new URLSearchParams();
      if (newFilter) params.append('new_filter', newFilter);
      // ...
  }

Step 4: Frontend - UI Component (Games.svelte)
  let newFilter = '';
  // Add <select> or <input> bound to newFilter
  // Reactive statement will auto-reload

Step 5: Test
  - Apply filter alone
  - Apply with other filters
  - Check pagination works
  - Verify SQL query is correct
```

### Task 2: Add New API Endpoint
```bash
Step 1: Backend - Create Endpoint (api/module.py)
  @router.get("/endpoint")
  async def new_endpoint(db: AsyncSession = Depends(get_db)):
      # Implementation
      return {"data": result}

Step 2: Backend - Register Router (main.py)
  app.include_router(module.router, prefix="/api", tags=["module"])

Step 3: Frontend - API Client (client.js)
  export async function callNewEndpoint() {
      const response = await fetch(`${API_BASE_URL}/api/endpoint`);
      return await response.json();
  }

Step 4: Frontend - Component (Component.svelte)
  import { callNewEndpoint } from '$lib/api/client';
  
  async function handleAction() {
      loading = true;
      try {
          const result = await callNewEndpoint();
          // Update UI
      } catch (err) {
          // Handle error
      } finally {
          loading = false;
      }
  }

Step 5: Test
  - Check API docs at /docs
  - Test from browser console
  - Test from UI
  - Check error handling
```

### Task 3: Modify Database Schema
```bash
⚠️ WARNING: No migrations yet! This is destructive!

Step 1: Backend - Update Model (models.py)
  class Game(Base):
      # Add/modify/remove column
      new_column = Column(String, default="")

Step 2: Stop Backend
  docker compose down backend

Step 3: Delete Database
  rm /root/docker/local-chess-analyzer/data/games.db
  # OR use "Clear Database" button in Settings

Step 4: Restart Backend (creates tables)
  docker compose up -d backend
  # Check logs: docker compose logs backend

Step 5: Update CRUD Operations (crud/*.py)
  # Update queries to use new column

Step 6: Update API Responses (api/*.py)
  # Return new column if needed

Step 7: Update Frontend (Components/*.svelte)
  # Display new column

Step 8: Re-import Data
  # Use sync feature to re-fetch games

⚠️ Future: Add Alembic for migrations!
```

### Task 4: Debug Backend Issue
```bash
# Check container is running
docker compose ps

# View recent logs
docker compose logs backend --tail=50 --follow

# Check database directly
docker compose exec backend python -c "
import sqlite3
conn = sqlite3.connect('/app/data/games.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM games')
print(f'Games: {cursor.fetchone()[0]}')
conn.close()
"

# Check Python environment
docker compose exec backend python -c "
import sys
print(sys.version)
import fastapi
print(f'FastAPI: {fastapi.__version__}')
"

# Interactive Python shell
docker compose exec backend python

# Check file permissions
docker compose exec backend ls -la /app/data/
```

### Task 5: Debug Frontend Issue
```bash
# Rebuild frontend
docker compose up -d --build frontend

# Check logs
docker compose logs frontend --tail=50

# Browser console
# Open http://192.168.0.102:6969/#/
# Press F12 → Console tab
# Look for errors

# Check network requests
# F12 → Network tab
# Filter: XHR
# Check API calls and responses

# Check Svelte reactivity
# Add console.log in reactive statements:
# $: console.log('Filter changed:', statusFilter);
```

---

## 📊 Current Project State

### Completed Features (Steps 1-7) ✅
- ✅ Backend API with FastAPI
- ✅ Chess.com game import
- ✅ SQLite database with async
- ✅ Frontend with Svelte 5
- ✅ Dashboard with statistics
- ✅ Game library with advanced filtering
- ✅ Settings management
- ✅ System resource detection
- ✅ Setup wizard
- ✅ Database backup/restore/clear

### Statistics (As of Nov 4, 2025)
```
Database:
  - Total games: 873
  - Players: Hikaru (308), orzelmocnygaz (551), others (14)
  - Date range: 2025.10.01 to 2025.11.02
  - Status: All "completed"

Code:
  - Backend: ~1,500 lines Python
  - Frontend: ~1,200 lines Svelte
  - CSS: ~800 lines
  - Total: ~3,500 lines

Performance:
  - API response: <50ms
  - Database query: <20ms
  - Frontend render: instant
  - Sync: ~3s for 300 games
```

### Technical Debt (Known Issues) ⚠️
1. **No Automated Tests** - All testing is manual
2. **No Authentication** - Anyone on network can access
3. **No Rate Limiting** - API can be spammed
4. **No Database Migrations** - Schema changes require recreation
5. **No Indexes** - Large datasets will slow down
6. **No Caching** - Same queries hit DB every time
7. **No Logging** - Hard to debug production issues
8. **No Error Tracking** - Exceptions not captured

### What's NOT Implemented Yet 🔴
- Stockfish analysis engine integration (Step 8 - NEXT!)
- Game replay with chess board
- Analysis visualization
- Performance statistics
- Opening repertoire
- Mistake pattern detection
- Export to PGN
- Position search

---

## 🎯 Step 8 Preview: Stockfish Analysis (Next Task)

### What Needs to Be Built
```
1. Background Worker
   - Async task queue for game analysis
   - Progress tracking
   - Error handling

2. Stockfish Integration
   - Subprocess management
   - UCI protocol communication
   - Position evaluation

3. Analysis Storage
   - Store results in analysis_data (JSON)
   - Update analysis_status
   - Track progress

4. UI Updates
   - Show analysis progress
   - Display results
   - Visualization of evaluations

5. API Endpoints
   - POST /api/analysis/start (single game)
   - POST /api/analysis/batch (multiple games)
   - GET /api/analysis/status/{game_id}
   - DELETE /api/analysis/stop
```

### Key Considerations for Step 8
```
⚠️ Challenges:
- Stockfish is CPU-intensive (respect thread limits)
- Long-running tasks (need progress updates)
- Error handling (Stockfish crashes?)
- Concurrent analysis (queue management)
- Results serialization (JSON format)

✅ Best Practices:
- Use background tasks (don't block API)
- Implement task queue (Celery? or simple queue?)
- Add cancellation support
- Store intermediate results
- Log everything
- Test with real games
```

---

## 🤖 AI Agent-Specific Guidelines

### Before Making Changes
1. **Read** the relevant section in this document
2. **Check** if similar functionality exists
3. **Understand** the architectural pattern
4. **Review** known issues to avoid repeating mistakes
5. **Plan** the change across all layers (API → CRUD → Frontend)

### When Debugging
1. **Check logs** first (docker compose logs)
2. **Verify** database state (use provided queries)
3. **Test** API directly (use /docs or curl)
4. **Isolate** frontend vs backend issue
5. **Review** similar past issues in this doc

### When Proposing Solutions
1. **Explain** the problem clearly
2. **Show** code examples
3. **Mention** which files need changes
4. **Consider** backwards compatibility
5. **Think** about error cases

### Communication Style
✅ **Do:**
- Be specific: "Add date filter to Games.svelte line 47"
- Explain why: "This fixes pagination bug from Nov 3"
- Show examples: "Change `date_from.replace('-', '.')` to ..."
- Offer options: "We could do A (simple) or B (robust)"

❌ **Don't:**
- Be vague: "Update the frontend"
- Skip explanations: "Just do it"
- Assume context: "Fix the bug"
- Make unilateral decisions: "I changed everything"

### Testing Expectations
After every change, test:
1. ✅ Feature works as intended
2. ✅ Doesn't break existing features
3. ✅ Error cases handled gracefully
4. ✅ Performance is acceptable
5. ✅ UI provides clear feedback

---

## 📚 Additional Resources

### Documentation Files
```
/root/docker/local-chess-analyzer/
├── README.md                    # Project overview
├── Summary 30.10.2025.md        # Steps 4-6 session log
├── Summary 03.11.2025.md        # Step 7 session log (games list)
├── Summary 04.11.2025.md        # Database management session
├── Step 4 - completed.md        # Frontend implementation
├── Step 5 - completed.md        # Resource detection
├── Step 6 - completed.md        # Setup wizard
└── PROJECT_CONTEXT.md           # This file
```

### External Docs
- **FastAPI:** https://fastapi.tiangolo.com/
- **Svelte 5:** https://svelte.dev/docs
- **SQLAlchemy:** https://docs.sqlalchemy.org/
- **Stockfish UCI:** https://www.chessprogramming.org/UCI
- **Python-Chess:** https://python-chess.readthedocs.io/

### Quick Commands Reference
```bash
# Rebuild everything
cd /root/docker/local-chess-analyzer
docker compose down
docker compose up -d --build

# View logs
docker compose logs backend --follow
docker compose logs frontend --follow

# Database inspection
docker compose exec backend python -c "
import sqlite3
conn = sqlite3.connect('/app/data/games.db')
cursor = conn.cursor()
# Your SQL here
cursor.execute('SELECT COUNT(*) FROM games')
print(cursor.fetchone())
conn.close()
"

# Fix permissions
docker compose exec backend chmod 0666 /app/data/games.db
docker compose exec backend chmod 0777 /app/data

# Restart single service
docker compose restart backend
docker compose restart frontend
```

---

## ✅ Pre-Flight Checklist

### Before Starting New Feature
- [ ] Read relevant sections of this document
- [ ] Understand current implementation
- [ ] Check for similar existing features
- [ ] Review known issues to avoid
- [ ] Plan changes across all layers

### Before Committing Code
- [ ] Code follows established patterns
- [ ] Error handling implemented
- [ ] Loading states added
- [ ] User feedback included
- [ ] Tested manually
- [ ] No console errors
- [ ] Database queries efficient
- [ ] Doesn't break existing features

### Before Asking User for Testing
- [ ] Tested personally first
- [ ] Checked logs for errors
- [ ] Verified API responses
- [ ] Tested edge cases
- [ ] UI looks professional
- [ ] Clear instructions for testing

---

**Last Updated:** November 4, 2025  
**Version:** 2.0 (AI Agent Optimized)  
**Next Review:** After Step 8 completion  
**Maintained By:** Development team + AI assistants

---

## 🎓 Lessons Learned (Why Things Are This Way)

### Architectural Decisions

**Why SQLite instead of PostgreSQL?**
- Local deployment (no network required)
- Simple setup (single file)
- Fast enough for personal use (< 100k games)
- Future: Can migrate to Postgres if needed

**Why hash-based routing (#/)?**
- Path-based routing had issues in Docker
- Works across network without configuration
- Compatible with all browsers
- Simpler to deploy

**Why filter at SQL level?**
- Pagination requires filtered counts
- Client-side filtering breaks pagination
- Better performance for large datasets
- Allows proper use of indexes (future)

**Why separate backend/client filters?**
- Backend: Efficient at scale, enables pagination
- Client: Better UX, instant feedback
- Player-specific logic needs game context
- Real-time search doesn't need API call

**Why date format inconsistency?**
- Database: Inherited from Chess.com API format
- Frontend: Native date inputs use ISO format
- Decision: Convert at boundaries vs changing schema
- Future: Normalize to ISO 8601 everywhere

### User Feedback Integration

**"Professional UI" → Modern card-based design**
- User praised appearance: "Holy Fuck it is very good looking"
- Established as quality standard
- All new features must match this level

**"Clear Feedback" → Loading states everywhere**
- User frustrated when actions had no feedback
- Now: Every action shows loading → success/error
- Pattern: Optimistic UI updates where possible

**"Confirmation Dialogs" → Prevent accidents**
- User almost lost data without warning
- Now: All destructive actions require confirmation
- Pattern: Use native confirm() for simplicity

---

**END OF AI AGENT CONTEXT GUIDE**
