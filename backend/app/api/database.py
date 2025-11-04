from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import shutil
import os
from pathlib import Path

from ..db.database import get_db_session, engine, Base

router = APIRouter()

DATABASE_PATH = "/app/data/games.db"
BACKUP_PATH = "/app/data/games_backup.db"


@router.post("/api/database/initialize")
async def initialize_database():
    """
    Initialize or reinitialize the database.
    Creates tables and default settings.
    Useful if database was deleted or corrupted.

    Returns:
        Success message
    """
    try:
        # Ensure data directory exists
        data_dir = "/app/data"
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, mode=0o777, exist_ok=True)
        else:
            os.chmod(data_dir, 0o777)

        # Close all connections
        await engine.dispose()

        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Initialize default settings
            await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('chess_com_username', NULL)"))
            await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('stockfish_path', '/app/stockfish/stockfish_binary')"))
            await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('stockfish_threads', '1')"))
            await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('stockfish_hash_mb', '128')"))
            await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('analysis_depth', '15')"))
            await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('analysis_time_ms', '1000')"))
            await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_sync_enabled', 'false')"))
            await conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('theme', 'default')"))

        # Set proper permissions on database file
        if os.path.exists(DATABASE_PATH):
            os.chmod(DATABASE_PATH, 0o666)

        return {
            "success": True,
            "message": "Database initialized successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize database: {str(e)}")


@router.delete("/api/database/clear")
async def clear_database(db: AsyncSession = Depends(get_db_session)):
    """
    Delete all games from the database.
    Settings are preserved.

    Returns:
        Message confirming deletion and count of deleted games
    """
    try:
        # Get count before deleting
        result = await db.execute(text("SELECT COUNT(*) FROM games"))
        count = result.scalar()

        # Delete all games
        await db.execute(text("DELETE FROM games"))

        # Commit the transaction
        await db.commit()

        # VACUUM to compact the database and force write to disk
        # This is important for SQLite to physically remove the data
        await db.execute(text("VACUUM"))
        await db.commit()

        # Force close all connections and dispose engine pool
        # This ensures SQLite writes everything to disk
        await engine.dispose()

        return {
            "success": True,
            "message": f"Successfully deleted {count} games",
            "deleted_count": count
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear database: {str(e)}")


@router.get("/api/database/download")
async def download_database():
    """
    Download the entire games.db file.

    Returns:
        The database file as a downloadable attachment
    """
    try:
        if not os.path.exists(DATABASE_PATH):
            raise HTTPException(status_code=404, detail="Database file not found")

        # Force checkpoint to write all WAL changes to main db file
        import sqlite3
        conn = sqlite3.connect(DATABASE_PATH)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
        conn.close()

        # Force close all async connections
        await engine.dispose()

        # Small delay to ensure file system sync
        import asyncio
        await asyncio.sleep(0.1)

        # Generate timestamp for unique filename
        from datetime import datetime
        import uuid
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"games_backup_{timestamp}.db"

        # Create a temporary copy to avoid any caching issues
        temp_path = f"/tmp/games_download_{unique_id}.db"
        shutil.copy2(DATABASE_PATH, temp_path)

        # Return the temp file and mark it for deletion after sending
        return FileResponse(
            path=temp_path,
            filename=filename,
            media_type="application/x-sqlite3",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "ETag": unique_id
            },
            background=None  # File will be cleaned up by OS eventually
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download database: {str(e)}")


@router.post("/api/database/upload")
async def upload_database(file: UploadFile = File(...)):
    """
    Upload and replace the games.db file.
    Creates a backup of the current database before replacing.

    Args:
        file: The uploaded database file

    Returns:
        Message confirming successful upload
    """
    try:
        # Validate file type
        if not file.filename.endswith('.db'):
            raise HTTPException(status_code=400, detail="File must be a .db file")

        # Create backup of current database
        if os.path.exists(DATABASE_PATH):
            shutil.copy2(DATABASE_PATH, BACKUP_PATH)

        # Save uploaded file
        temp_path = f"{DATABASE_PATH}.temp"
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Verify it's a valid SQLite database
        try:
            import sqlite3
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            # Check if games table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='games'")
            if not cursor.fetchone():
                conn.close()
                os.remove(temp_path)
                raise HTTPException(status_code=400, detail="Invalid database: 'games' table not found")

            # Get count of games in uploaded database
            cursor.execute("SELECT COUNT(*) FROM games")
            game_count = cursor.fetchone()[0]
            conn.close()
        except sqlite3.Error as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise HTTPException(status_code=400, detail=f"Invalid SQLite database: {str(e)}")

        # Replace current database with uploaded file
        shutil.move(temp_path, DATABASE_PATH)

        # Force reconnection to the new database
        await engine.dispose()

        return {
            "success": True,
            "message": f"Successfully uploaded database with {game_count} games",
            "game_count": game_count,
            "backup_created": True
        }
    except HTTPException:
        raise
    except Exception as e:
        # Restore from backup if something went wrong
        if os.path.exists(BACKUP_PATH):
            shutil.copy2(BACKUP_PATH, DATABASE_PATH)
        raise HTTPException(status_code=500, detail=f"Failed to upload database: {str(e)}")
