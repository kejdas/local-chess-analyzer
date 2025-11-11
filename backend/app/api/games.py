from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, field_serializer
from datetime import datetime
import asyncio
from io import StringIO
import chess.pgn

from ..db.database import get_db_session
from ..crud import games as crud_games
from ..db.models import Game
from ..services.stockfish_service import (
    analyze_game_async,
    get_game_analysis,
    has_game_analysis
)
from ..db.database import async_session


router = APIRouter()


class GameResponse(BaseModel):
    id: int
    chess_com_id: str
    pgn: Optional[str] = None
    white_player: Optional[str] = None
    black_player: Optional[str] = None
    white_rating: Optional[int] = None
    black_rating: Optional[int] = None
    time_class: Optional[str] = None
    result: Optional[str] = None
    game_date: Optional[str] = None
    import_date: datetime
    analysis_status: str
    has_analysis: bool = False  # Whether analysis file exists
    # Optional time metadata derived from PGN headers (UTCDate/UTCTime or EndTime)
    utc_date: Optional[str] = None
    utc_time: Optional[str] = None
    game_datetime_utc: Optional[str] = None  # ISO string if available

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
    time_class: Optional[str] = None,
    sort_by: Optional[str] = 'date',
    sort_order: Optional[str] = 'desc',
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get paginated list of games with optional filters and sorting.
    Automatically detects if analysis files exist for each game.

    Args:
        skip: Number of games to skip (for pagination)
        limit: Maximum number of games to return (max 1000)
        date_from: Filter games from this date (format: YYYY-MM-DD)
        date_to: Filter games to this date (format: YYYY-MM-DD)
        status: Filter by analysis status (queued/analyzing/completed)
        time_class: Filter by game speed (bullet/blitz/rapid/daily/other)
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
        time_class=time_class,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search
    )
    total = await crud_games.get_games_count(
        db,
        date_from=date_from_db,
        date_to=date_to_db,
        status=status,
        time_class=time_class,
        search=search
    )

    # Convert to response models and check for analysis files
    game_responses: list[GameResponse] = []
    for game in games:
        # Derive UTC date/time from PGN if available
        utc_date = None
        utc_time = None
        game_dt_iso = None
        try:
            if game.pgn:
                g = chess.pgn.read_game(StringIO(game.pgn))
                if g and g.headers:
                    utc_date = g.headers.get('UTCDate') or g.headers.get('Date') or None
                    utc_time = g.headers.get('UTCTime') or g.headers.get('EndTime') or g.headers.get('StartTime') or None
                    if utc_date and utc_time:
                        # Normalize separators
                        d = utc_date.replace('-', '.')
                        # Compose ISO if parsable
                        try:
                            # Chess.com UTCDate format often is YYYY.MM.DD and UTCTime HH:MM:SS
                            dt = datetime.strptime(f"{d} {utc_time}", "%Y.%m.%d %H:%M:%S")
                            game_dt_iso = dt.isoformat() + "Z"
                        except Exception:
                            game_dt_iso = None
        except Exception:
            # Ignore PGN parse errors silently for listing
            pass

        game_dict = {
            "id": game.id,
            "chess_com_id": game.chess_com_id,
            "white_player": game.white_player,
            "black_player": game.black_player,
            "white_rating": game.white_rating,
            "black_rating": game.black_rating,
            "time_class": game.time_class,
            "result": game.result,
            "game_date": game.game_date,
            "import_date": game.import_date,
            "analysis_status": game.analysis_status,
            "has_analysis": has_game_analysis(game.id),
            "utc_date": utc_date,
            "utc_time": utc_time,
            "game_datetime_utc": game_dt_iso
        }

        # Auto-detect: if analysis file exists, status should be "completed"
        if game_dict["has_analysis"] and game_dict["analysis_status"] != "completed":
            game_dict["analysis_status"] = "completed"
            # Update database status if it's different
            await crud_games.update_game_analysis_status(db, game.id, "completed")

        game_responses.append(GameResponse(**game_dict))

    # Stable tie-breaker: if sorting by date, order same-day games by UTC time when available
    if sort_by == 'date':
        def sort_key(gr: GameResponse):
            # Use game_date and game_datetime_utc; missing times go to start/end depending on order
            date_part = gr.game_date or ""
            dt_part = gr.game_datetime_utc or ("0000-01-01T00:00:00Z" if sort_order == 'asc' else "9999-12-31T23:59:59Z")
            return (date_part, dt_part)
        reverse = (sort_order != 'asc')
        game_responses.sort(key=sort_key, reverse=reverse)

    return GamesListResponse(
        games=game_responses,
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


@router.get("/api/games/{game_id}", response_model=GameResponse)
async def get_game(
    game_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get a single game by ID.

    Args:
        game_id: Database ID of the game

    Returns:
        Game data with metadata
    """
    game = await crud_games.get_game_by_id(db, game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Create response with analysis detection
    # Derive UTC date/time from PGN if available
    utc_date = None
    utc_time = None
    game_dt_iso = None
    try:
        if game.pgn:
            g = chess.pgn.read_game(StringIO(game.pgn))
            if g and g.headers:
                utc_date = g.headers.get('UTCDate') or g.headers.get('Date') or None
                utc_time = g.headers.get('UTCTime') or g.headers.get('EndTime') or g.headers.get('StartTime') or None
                if utc_date and utc_time:
                    d = utc_date.replace('-', '.')
                    try:
                        dt = datetime.strptime(f"{d} {utc_time}", "%Y.%m.%d %H:%M:%S")
                        game_dt_iso = dt.isoformat() + "Z"
                    except Exception:
                        game_dt_iso = None
    except Exception:
        pass

    game_dict = {
        "id": game.id,
        "chess_com_id": game.chess_com_id,
        "pgn": game.pgn,
        "white_player": game.white_player,
        "black_player": game.black_player,
        "white_rating": game.white_rating,
        "black_rating": game.black_rating,
        "time_class": game.time_class,
        "result": game.result,
        "game_date": game.game_date,
        "import_date": game.import_date,
        "analysis_status": game.analysis_status,
        "has_analysis": has_game_analysis(game.id),
        "utc_date": utc_date,
        "utc_time": utc_time,
        "game_datetime_utc": game_dt_iso
    }

    # Auto-detect: if analysis file exists, status should be "completed"
    if game_dict["has_analysis"] and game_dict["analysis_status"] != "completed":
        game_dict["analysis_status"] = "completed"
        await crud_games.update_game_analysis_status(db, game.id, "completed")

    return GameResponse(**game_dict)


@router.post("/api/games/{game_id}/analyze")
async def analyze_game(
    game_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Analyze a game using Stockfish and save results to JSON file.

    Args:
        game_id: Database ID of the game to analyze

    Returns:
        Dictionary with analysis status and results
    """
    # Get the game from database
    game = await crud_games.get_game_by_id(db, game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Check if already analyzed
    if has_game_analysis(game_id):
        return {
            "success": True,
            "message": "Game already analyzed",
            "game_id": game_id,
            "status": "already_completed"
        }

    try:
        # Update status to analyzing
        await crud_games.update_game_analysis_status(db, game_id, "analyzing")

        # Run analysis
        result = await analyze_game_async(
            game_id=game_id,
            pgn_text=game.pgn,
            db=db
        )

        # Update status to completed
        await crud_games.update_game_analysis_status(db, game_id, "completed")

        return {
            "success": True,
            "message": "Game analyzed successfully",
            "game_id": game_id,
            "total_moves": result["total_moves"],
            "analysis_file": result["analysis_file"],
            "status": "completed"
        }

    except Exception as e:
        # Reset status to queued on error
        await crud_games.update_game_analysis_status(db, game_id, "queued")

        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@router.get("/api/games/{game_id}/analysis")
async def get_analysis(
    game_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get analysis results for a game.

    Args:
        game_id: Database ID of the game

    Returns:
        Analysis data if available, 404 if not found
    """
    # Check if game exists
    game = await crud_games.get_game_by_id(db, game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Get analysis from JSON file
    analysis = get_game_analysis(game_id)

    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found. Please analyze this game first."
        )

    return {
        "success": True,
        "game_id": game_id,
        "analysis": analysis
    }


class BulkAnalyzeRequest(BaseModel):
    game_ids: List[int]
    concurrency: Optional[int] = 3
    skip_already_analyzed: Optional[bool] = True


@router.post("/api/games/bulk-analyze")
async def bulk_analyze_games(
    request: BulkAnalyzeRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Analyze multiple games in parallel on the server with a concurrency cap.
    Returns a summary of results when all requested analyses complete.
    """
    if not request.game_ids:
        raise HTTPException(status_code=400, detail="No game IDs provided")

    # Sanitize concurrency
    concurrency = request.concurrency or 1
    if concurrency < 1:
        concurrency = 1
    if concurrency > 8:
        concurrency = 8

    # Filter out already analyzed if requested
    to_analyze_ids: List[int] = []
    already_completed = 0
    for gid in request.game_ids:
        if request.skip_already_analyzed and has_game_analysis(gid):
            already_completed += 1
            continue
        to_analyze_ids.append(gid)

    if not to_analyze_ids:
        return {
            "success": True,
            "message": "No games to analyze",
            "requested": len(request.game_ids),
            "already_completed": already_completed,
            "started": 0,
            "completed": 0,
            "failed": 0,
            "details": []
        }

    semaphore = asyncio.Semaphore(concurrency)
    results: List[Dict[str, Any]] = []
    completed = 0
    failed = 0

    async def analyze_one(game_id: int):
        nonlocal completed, failed
        async with semaphore:
            # Use an independent DB session for each task
            async with async_session() as task_db:
                # Fetch the game
                game = await crud_games.get_game_by_id(task_db, game_id)
                if not game:
                    failed += 1
                    results.append({
                        "game_id": game_id,
                        "status": "not_found"
                    })
                    return

                # If analysis file was created since filtering, skip
                if request.skip_already_analyzed and has_game_analysis(game_id):
                    results.append({
                        "game_id": game_id,
                        "status": "already_completed"
                    })
                    return

                try:
                    await crud_games.update_game_analysis_status(task_db, game_id, "analyzing")
                    await analyze_game_async(
                        game_id=game_id,
                        pgn_text=game.pgn,
                        db=task_db
                    )
                    await crud_games.update_game_analysis_status(task_db, game_id, "completed")
                    completed += 1
                    results.append({
                        "game_id": game_id,
                        "status": "completed"
                    })
                except Exception as e:
                    await crud_games.update_game_analysis_status(task_db, game_id, "queued")
                    failed += 1
                    results.append({
                        "game_id": game_id,
                        "status": "failed",
                        "error": str(e)
                    })

    await asyncio.gather(*(analyze_one(gid) for gid in to_analyze_ids))

    return {
        "success": True,
        "message": "Bulk analysis completed",
        "requested": len(request.game_ids),
        "already_completed": already_completed,
        "started": len(to_analyze_ids),
        "completed": completed,
        "failed": failed,
        "details": results
    }
