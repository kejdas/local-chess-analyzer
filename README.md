# Local Chess Analyzer

A full-stack web application for importing, analyzing, and managing chess games from Chess.com using the Stockfish engine.

## Architecture

This application uses a containerized microservices architecture with Docker Compose:

- **Backend**: FastAPI (Python) - REST API server
- **Frontend**: Svelte 5 + Vite - Modern reactive UI
- **Database**: SQLite with async support (aiosqlite)
- **Chess Engine**: Stockfish (included as binary)
- **Web Server**: Nginx (for frontend)

## Project Structure

```
local-chess-analyzer/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── games.py           # Game retrieval endpoints
│   │   │   ├── settings.py        # Settings management endpoints
│   │   │   └── sync.py            # Chess.com sync endpoints
│   │   ├── crud/
│   │   │   ├── games.py           # Game database operations
│   │   │   └── settings.py        # Settings database operations
│   │   ├── db/
│   │   │   ├── database.py        # Database configuration
│   │   │   └── models.py          # SQLAlchemy models
│   │   ├── services/
│   │   │   └── chess_com.py       # Chess.com API client
│   │   └── main.py                # FastAPI application entry
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.svelte             # Main Svelte component
│   │   ├── main.js                # Entry point
│   │   └── lib/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
│
├── stockfish/
│   ├── src/                       # Stockfish source code
│   └── stockfish_binary           # Compiled engine (78MB)
│
├── data/
│   └── games.db                   # SQLite database
│
└── docker-compose.yml
```

## Features

### Implemented

- **Chess.com Integration**
  - Fetch games from Chess.com public API
  - Support for monthly archives
  - Automatic duplicate detection using chess_com_id
  - Background sync to avoid blocking requests

- **Game Management**
  - Store games with PGN notation
  - Track players, results, and game dates
  - Pagination support for large game collections
  - Game statistics by analysis status

- **Settings Management**
  - Configurable Chess.com username
  - Stockfish engine parameters (threads, hash size)
  - Analysis parameters (depth, time)
  - Theme preferences

- **API Features**
  - RESTful API with FastAPI
  - CORS support for frontend-backend communication
  - Interactive API documentation (Swagger UI)
  - Async/await for efficient I/O operations

## Getting Started

### Prerequisites

- Docker
- Docker Compose

### Installation & Running

1. Clone the repository:
```bash
cd /root/docker/local-chess-analyzer
```

2. Build and start the containers:
```bash
docker compose -f /root/docker/local-chess-analyzer/docker-compose.yml up --build
```

3. Access the application:
   - **Frontend**: http://localhost:6969
   - **Backend API**: http://localhost:42069
   - **API Docs**: http://localhost:42069/docs

### Stopping the Application

```bash
docker compose -f /root/docker/local-chess-analyzer/docker-compose.yml down
```

## API Endpoints

### Settings

```bash
# Get all settings
GET http://localhost:42069/api/settings

# Update settings
PUT http://localhost:42069/api/settings
Content-Type: application/json
{
  "chess_com_username": "your_username",
  "analysis_depth": "20"
}
```

### Chess.com Sync

```bash
# Start sync (fetches games from Chess.com)
POST http://localhost:42069/api/sync
Content-Type: application/json
{
  "username": "hikaru",        # optional, uses settings if not provided
  "limit_months": 1            # optional, fetches last N months only
}

# Check sync status
GET http://localhost:42069/api/sync/status
```

### Games

```bash
# Get paginated list of games
GET http://localhost:42069/api/games?skip=0&limit=100

# Get game statistics
GET http://localhost:42069/api/games/stats
```

## Database Schema

### Games Table

| Column           | Type      | Description                              |
|------------------|-----------|------------------------------------------|
| id               | Integer   | Primary key                              |
| chess_com_id     | String    | Unique Chess.com game identifier         |
| pgn              | Text      | Full game in PGN notation                |
| white_player     | String    | White player username                    |
| black_player     | String    | Black player username                    |
| result           | String    | Game result (1-0, 0-1, 1/2-1/2)         |
| game_date        | String    | Date the game was played                 |
| import_date      | Timestamp | When the game was imported               |
| analysis_status  | String    | queued / analyzing / completed           |
| analysis_data    | Text      | JSON with Stockfish analysis (future)    |

### Settings Table

| Column | Type   | Description                    |
|--------|--------|--------------------------------|
| key    | String | Setting key (primary key)      |
| value  | String | Setting value                  |

### Default Settings

- `chess_com_username`: null (must be set by user)
- `stockfish_path`: /app/stockfish/stockfish_binary
- `stockfish_threads`: 1
- `stockfish_hash_mb`: 128
- `analysis_depth`: 15
- `analysis_time_ms`: 1000
- `auto_sync_enabled`: false
- `theme`: default

## Usage Example

1. **Set your Chess.com username:**
```bash
curl -X PUT http://localhost:42069/api/settings \
  -H "Content-Type: application/json" \
  -d '{"chess_com_username": "hikaru"}'
```

2. **Sync your games (last month):**
```bash
curl -X POST http://localhost:42069/api/sync \
  -H "Content-Type: application/json" \
  -d '{"limit_months": 1}'
```

3. **Check sync status:**
```bash
curl http://localhost:42069/api/sync/status
```

4. **View your games:**
```bash
curl "http://localhost:42069/api/games?limit=10"
```

5. **Check statistics:**
```bash
curl http://localhost:42069/api/games/stats
```

## Testing Results

Tested with Chess.com user "hikaru" (October 2025):
- **First sync**: 308 games imported successfully
- **Second sync**: 0 new games, 308 duplicates skipped
- **Duplicate detection**: Working correctly using chess_com_id
- **Background processing**: Non-blocking, returns immediately

## Technology Stack

### Backend
- **FastAPI**: Modern, fast web framework for Python
- **SQLAlchemy**: SQL toolkit and ORM with async support
- **aiosqlite**: Async SQLite database adapter
- **python-chess**: Chess library for PGN parsing and game logic
- **requests**: HTTP library for Chess.com API calls
- **Uvicorn**: ASGI server

### Frontend
- **Svelte 5**: Reactive JavaScript framework
- **Vite 7**: Next-generation frontend build tool
- **Nginx**: Production-ready web server

### Infrastructure
- **Docker**: Containerization
- **Docker Compose**: Multi-container orchestration

## Development

### Rebuilding After Code Changes

Backend only:
```bash
docker compose -f /root/docker/local-chess-analyzer/docker-compose.yml up -d --build backend
```

Frontend only:
```bash
docker compose -f /root/docker/local-chess-analyzer/docker-compose.yml up -d --build frontend
```

Both services:
```bash
docker compose -f /root/docker/local-chess-analyzer/docker-compose.yml up --build
```

### Viewing Logs

```bash
# All services
docker compose -f /root/docker/local-chess-analyzer/docker-compose.yml logs -f

# Backend only
docker compose -f /root/docker/local-chess-analyzer/docker-compose.yml logs -f backend

# Frontend only
docker compose -f /root/docker/local-chess-analyzer/docker-compose.yml logs -f frontend
```

## Roadmap

### Next Steps

1. **Stockfish Analysis Service**
   - Implement background worker for game analysis
   - Process games with "queued" status
   - Store analysis results (best moves, evaluations, mistakes)

2. **Frontend Development**
   - Settings management UI
   - Game list with filtering and sorting
   - Interactive chess board for game replay
   - Analysis visualization
   - Sync controls and status display

3. **Advanced Features**
   - Opening repertoire analysis
   - Mistake patterns identification
   - Performance trends over time
   - Compare games against engine lines

## Contributing

This is a personal project for local chess game analysis. Feel free to fork and customize for your needs.

## License

This project includes Stockfish, which is licensed under the GNU General Public License v3.0.

## Port Configuration

- Frontend: Port 6969 → 80 (Nginx)
- Backend: Port 42069 → 42069 (Uvicorn)
