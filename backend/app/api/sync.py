from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
from pydantic import BaseModel

from ..db.database import get_db_session, async_session
from ..crud import settings as crud_settings
from ..crud import games as crud_games
from ..services.chess_com import ChessComAPI


router = APIRouter()


class SyncRequest(BaseModel):
    username: Optional[str] = None
    limit_months: Optional[int] = None


class SyncResponse(BaseModel):
    status: str
    message: str


# Global sync status (in production, use Redis or similar)
sync_status = {
    'is_running': False,
    'last_run': None,
    'last_result': None
}


async def sync_games_background(username: str, limit_months: Optional[int] = None):
    """
    Background task to sync games from Chess.com.

    Args:
        username: Chess.com username
        limit_months: Optional limit for number of months to fetch
    """
    global sync_status

    sync_status['is_running'] = True
    sync_status['last_result'] = None

    try:
        # Initialize Chess.com API client
        chess_com_client = ChessComAPI(username)

        # Fetch all games
        print(f"Fetching games for {username}...")
        all_games = chess_com_client.get_all_games(limit_months=limit_months)
        print(f"Fetched {len(all_games)} games from Chess.com")

        # Extract game data
        games_data = []
        for game in all_games:
            try:
                game_data = chess_com_client.extract_game_data(game)
                games_data.append(game_data)
            except Exception as e:
                print(f"Error extracting game data: {str(e)}")
                continue

        # Save games to database
        async with async_session() as db:
            result = await crud_games.bulk_create_games(db, games_data)

        sync_status['last_result'] = {
            'success': True,
            'total_fetched': len(all_games),
            'created': result['created'],
            'skipped': result['skipped'],
            'username': username
        }

        print(f"Sync completed: {result['created']} created, {result['skipped']} skipped")

    except Exception as e:
        sync_status['last_result'] = {
            'success': False,
            'error': str(e),
            'username': username
        }
        print(f"Sync failed: {str(e)}")

    finally:
        sync_status['is_running'] = False
        from datetime import datetime
        sync_status['last_run'] = datetime.now().isoformat()


@router.post("/api/sync", response_model=SyncResponse)
async def sync_chess_com_games(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Initiate syncing of games from Chess.com.

    If username is not provided, uses the one from settings.
    Uses background tasks to avoid blocking the request.
    """
    # Check if sync is already running
    if sync_status['is_running']:
        raise HTTPException(
            status_code=409,
            detail="Sync is already in progress"
        )

    # Get username from request or settings
    username = request.username
    if not username:
        settings = await crud_settings.get_all_settings(db)
        username = settings.get('chess_com_username')

    if not username:
        raise HTTPException(
            status_code=400,
            detail="No Chess.com username provided. Please provide username in request or settings."
        )

    # Add background task
    background_tasks.add_task(
        sync_games_background,
        username=username,
        limit_months=request.limit_months
    )

    return SyncResponse(
        status="started",
        message=f"Sync started for user: {username}"
    )


@router.get("/api/sync/status")
async def get_sync_status() -> Dict[str, Any]:
    """
    Get the current status of the sync operation.

    Returns:
        Dictionary with sync status information
    """
    return {
        'is_running': sync_status['is_running'],
        'last_run': sync_status['last_run'],
        'last_result': sync_status['last_result']
    }
