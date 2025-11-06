from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, field_serializer
from datetime import datetime
import re

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
    # Computed from PGN (not stored in DB)
    white_rating: Optional[int] = None
    black_rating: Optional[int] = None

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
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: Optional[str] = 'date',
    sort_order: Optional[str] = 'desc',
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get paginated list of games with optional filters and sorting.

    Args:
        skip: Number of games to skip (for pagination)
        limit: Maximum number of games to return (max 1000)
        date_from: Filter games from this date (format: YYYY-MM-DD)
        date_to: Filter games to this date (format: YYYY-MM-DD)
        status: Filter by analysis status (queued/analyzing/completed)
        sort_by: Field to sort by (date/result/status)
        sort_order: Sort order (asc/desc)

    Returns:
        List of games with pagination metadata
    """
    if limit > 1000:
        limit = 1000

    # Convert date format from YYYY-MM-DD to YYYY.MM.DD for database comparison
    date_from_db = date_from.replace('-', '.') if date_from else None
    date_to_db = date_to.replace('-', '.') if date_to else None

    games = await crud_games.get_all_games(
        db,
        skip=skip,
        limit=limit,
        date_from=date_from_db,
        date_to=date_to_db,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order
    )
    total = await crud_games.get_games_count(
        db,
        date_from=date_from_db,
        date_to=date_to_db,
        status=status
    )

    # # Helper to extract ratings from PGN tags
    def extract_ratings_from_pgn(pgn_text: Optional[str]) -> tuple[Optional[int], Optional[int]]:
        if not pgn_text:
            return None, None

        def find_first_int(patterns: List[str]) -> Optional[int]:
            for pat in patterns:
                m = re.search(pat, pgn_text)
                if m:
                    try:
                        return int(m.group(1))
                    except ValueError:
                        continue
            return None

        # Support common PGN tags: WhiteElo/BlackElo, WhiteRating/BlackRating, WhiteRatingAfter/BlackRatingAfter
        white = find_first_int([
            r"\[WhiteRatingAfter\s+\"(\d+)\"\]",
            r"\[WhiteEloAfter\s+\"(\d+)\"\]",
            r"\[WhiteElo\s+\"(\d+)\"\]",
            r"\[WhiteRating\s+\"(\d+)\"\]",
        ])
        black = find_first_int([
            r"\[BlackRatingAfter\s+\"(\d+)\"\]",
            r"\[BlackEloAfter\s+\"(\d+)\"\]",
            r"\[BlackElo\s+\"(\d+)\"\]",
            r"\[BlackRating\s+\"(\d+)\"\]",
        ])
        return white, black

    # Transform games to include computed ratings parsed from PGN
    response_games: List[GameResponse] = []
    for game in games:
        white_rating, black_rating = extract_ratings_from_pgn(getattr(game, "pgn", None))
        base = GameResponse.model_validate(game, from_attributes=True).model_dump()
        base["white_rating"] = white_rating
        base["black_rating"] = black_rating
        response_games.append(GameResponse(**base))

    return GamesListResponse(
        games=response_games,
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
