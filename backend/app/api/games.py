from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, field_serializer
from datetime import datetime

from ..db.database import get_db_session
from ..crud import games as crud_games
from ..db.models import Game


router = APIRouter()


class GameResponse(BaseModel):
    id: int
    chess_com_id: str
    white_player: Optional[str] = None
    black_player: Optional[str] = None
    result: Optional[str] = None
    game_date: Optional[str] = None
    import_date: datetime
    analysis_status: str

    @field_serializer('import_date')
    def serialize_import_date(self, import_date: datetime, _info):
        return import_date.isoformat() if import_date else None

    class Config:
        from_attributes = True


class GamesListResponse(BaseModel):
    games: List[GameResponse]
    total: int
    skip: int
    limit: int


@router.get("/api/games", response_model=GamesListResponse)
async def get_games(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get paginated list of games.

    Args:
        skip: Number of games to skip (for pagination)
        limit: Maximum number of games to return (max 1000)

    Returns:
        List of games with pagination metadata
    """
    if limit > 1000:
        limit = 1000

    games = await crud_games.get_all_games(db, skip=skip, limit=limit)
    total = await crud_games.get_games_count(db)

    return GamesListResponse(
        games=games,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/api/games/stats")
async def get_games_stats(db: AsyncSession = Depends(get_db_session)):
    """
    Get statistics about games in the database.

    Returns:
        Dictionary with game statistics
    """
    total = await crud_games.get_games_count(db)
    queued = await crud_games.get_games_by_analysis_status(db, 'queued')
    analyzing = await crud_games.get_games_by_analysis_status(db, 'analyzing')
    completed = await crud_games.get_games_by_analysis_status(db, 'completed')

    return {
        'total': total,
        'queued': len(queued),
        'analyzing': len(analyzing),
        'completed': len(completed)
    }
