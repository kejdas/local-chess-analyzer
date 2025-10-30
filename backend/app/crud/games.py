from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from ..db.models import Game
from typing import List, Dict, Any, Optional


async def get_game_by_chess_com_id(db: AsyncSession, chess_com_id: str) -> Optional[Game]:
    """
    Get a game by its Chess.com ID.

    Args:
        db: Database session
        chess_com_id: Unique Chess.com game identifier

    Returns:
        Game object if found, None otherwise
    """
    result = await db.execute(
        select(Game).where(Game.chess_com_id == chess_com_id)
    )
    return result.scalars().first()


async def create_game(db: AsyncSession, game_data: Dict[str, Any]) -> Game:
    """
    Create a new game in the database.

    Args:
        db: Database session
        game_data: Dictionary containing game data

    Returns:
        Created Game object
    """
    game = Game(
        chess_com_id=game_data['chess_com_id'],
        pgn=game_data['pgn'],
        white_player=game_data.get('white_player'),
        black_player=game_data.get('black_player'),
        result=game_data.get('result'),
        game_date=game_data.get('game_date'),
        analysis_status='queued'
    )

    db.add(game)
    await db.commit()
    await db.refresh(game)
    return game


async def create_game_if_not_exists(db: AsyncSession, game_data: Dict[str, Any]) -> tuple[Game, bool]:
    """
    Create a game only if it doesn't already exist.

    Args:
        db: Database session
        game_data: Dictionary containing game data

    Returns:
        Tuple of (Game object, created: bool)
        created is True if a new game was created, False if it already existed
    """
    # Check if game already exists
    existing_game = await get_game_by_chess_com_id(db, game_data['chess_com_id'])

    if existing_game:
        return existing_game, False

    # Create new game
    new_game = await create_game(db, game_data)
    return new_game, True


async def bulk_create_games(db: AsyncSession, games_data: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Bulk create games, skipping duplicates.

    Args:
        db: Database session
        games_data: List of game data dictionaries

    Returns:
        Dictionary with stats: {'created': int, 'skipped': int, 'total': int}
    """
    created_count = 0
    skipped_count = 0

    for game_data in games_data:
        _, created = await create_game_if_not_exists(db, game_data)
        if created:
            created_count += 1
        else:
            skipped_count += 1

    return {
        'created': created_count,
        'skipped': skipped_count,
        'total': len(games_data)
    }


async def get_all_games(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Game]:
    """
    Get all games with pagination.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of Game objects
    """
    result = await db.execute(
        select(Game).offset(skip).limit(limit).order_by(Game.import_date.desc())
    )
    return result.scalars().all()


async def get_games_count(db: AsyncSession) -> int:
    """
    Get total count of games in the database.

    Args:
        db: Database session

    Returns:
        Total number of games
    """
    result = await db.execute(
        select(func.count(Game.id))
    )
    return result.scalar()


async def get_games_by_analysis_status(db: AsyncSession, status: str) -> List[Game]:
    """
    Get all games with a specific analysis status.

    Args:
        db: Database session
        status: Analysis status to filter by (e.g., 'queued', 'analyzing', 'completed')

    Returns:
        List of Game objects
    """
    result = await db.execute(
        select(Game).where(Game.analysis_status == status)
    )
    return result.scalars().all()
