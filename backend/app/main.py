from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .db.database import engine, Base
from .db.models import Game, Setting
from sqlalchemy.sql import text

from .api import settings as settings_api
from .api import sync as sync_api
from .api import games as games_api
from .api import system_resources as system_resources_api

@asynccontextmanager
async def lifespan(app: FastAPI):
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

@app.get("/")
def read_root():
    print("hello world")

