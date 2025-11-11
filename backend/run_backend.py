#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import uvicorn


def resolve_data_dir() -> str:
    # Prefer DATA_DIR if set (desktop bundle / dev override)
    env_dir = os.environ.get("DATA_DIR")
    if env_dir:
        Path(env_dir).mkdir(parents=True, exist_ok=True)
        return env_dir
    # Default to a user data directory to avoid permission issues
    # e.g., ~/.local-chess-analyzer/data on Unix, %APPDATA% on Windows
    base = Path.home() / ".local-chess-analyzer"
    data = base / "data"
    data.mkdir(parents=True, exist_ok=True)
    return str(data)


def resolve_stockfish_path() -> str:
    # If set explicitly, honor it
    sf = os.environ.get("STOCKFISH_PATH")
    if sf and Path(sf).exists():
        return sf
    # Try adjacent to the executable (PyInstaller build)
    exe_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    candidate = exe_dir / "stockfish" / "stockfish_binary"
    if sys.platform.startswith("win"):
        candidate = candidate.with_suffix(".exe")
    if candidate.exists():
        return str(candidate)
    # Fallback to Docker path; backend will surface errors if missing
    return "/app/stockfish/stockfish_binary"


def main():
    # Ensure envs for backend initialization
    os.environ.setdefault("DATA_DIR", resolve_data_dir())
    os.environ.setdefault("STOCKFISH_PATH", resolve_stockfish_path())

    port = int(os.environ.get("PORT", "42069"))
    host = "127.0.0.1"
    # Run FastAPI app
    uvicorn.run("app.main:app", host=host, port=port, factory=False)


if __name__ == "__main__":
    main()


