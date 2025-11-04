from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .db.database import engine, Base
from .db.models import Game, Setting
from sqlalchemy.sql import text
import os
import stat

from .api import settings as settings_api
from .api import sync as sync_api
from .api import games as games_api
from .api import system_resources as system_resources_api
from .api import database as database_api

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure data directory exists with proper permissions
    data_dir = "/app/data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, mode=0o777, exist_ok=True)
    else:
        # Ensure directory has write permissions
        os.chmod(data_dir, 0o777)

    # Check if database file exists, if so ensure it's writable
    db_path = "/app/data/games.db"
    if os.path.exists(db_path):
        try:
            os.chmod(db_path, 0o666)
        except Exception as e:
            print(f"Warning: Could not set database permissions: {e}")

    # Initialize database tables and default settings
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('chess_com_username', NULL)"))
        await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('stockfish_path', '/app/stockfish/stockfish_binary')"))
        await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('stockfish_threads', '1')"))
        await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('stockfish_hash_mb', '128')"))
        await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('analysis_depth', '15')"))
        await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('analysis_time_ms', '1000')"))
        await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_sync_enabled', 'false')"))
        await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('theme', 'default')"))

    # Ensure newly created database file has proper permissions
    if os.path.exists(db_path):
        os.chmod(db_path, 0o666)

    yield


app = FastAPI(lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(settings_api.router)
app.include_router(sync_api.router)
app.include_router(games_api.router)
app.include_router(system_resources_api.router)
app.include_router(database_api.router)

@app.get("/")
def read_root():
    print("hello world")

