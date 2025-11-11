from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from ..db.models import Game
from typing import List, Dict, Any, Optional


async def get_game_by_id(db: AsyncSession, game_id: int) -> Optional[Game]:
    """
    Get a game by its database ID.

    Args:
        db: Database session
        game_id: Database ID of the game

    Returns:
        Game object if found, None otherwise
    """
    result = await db.execute(
        select(Game).where(Game.id == game_id)
    )
    return result.scalars().first()


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
        white_rating=game_data.get('white_rating'),
        black_rating=game_data.get('black_rating'),
        time_class=game_data.get('time_class'),
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


async def get_all_games(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    time_class: Optional[str] = None,
    sort_by: str = 'date',
    sort_order: str = 'desc',
    search: Optional[str] = None
) -> List[Game]:
    """
    Get all games with pagination, filters, and sorting.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        date_from: Filter games from this date (format: YYYY.MM.DD)
        date_to: Filter games to this date (format: YYYY.MM.DD)
        status: Filter by analysis status
        sort_by: Field to sort by (date/result/status)
        sort_order: Sort order (asc/desc)

    Returns:
        List of Game objects
    """
    query = select(Game)

    # Apply filters
    if date_from:
        query = query.where(Game.game_date >= date_from)
    if date_to:
        query = query.where(Game.game_date <= date_to)
    if status:
        query = query.where(Game.analysis_status == status)
    if time_class:
        query = query.where(Game.time_class == time_class)
    if search:
        term = f"%{search.lower()}%"
        query = query.where(
            (func.lower(Game.white_player).ilike(term)) |
            (func.lower(Game.black_player).ilike(term)) |
            (func.lower(Game.result).ilike(term)) |
            (func.lower(Game.game_date).ilike(term))
        )

    # Apply sorting
    sort_column = Game.game_date  # Default
    if sort_by == 'result':
        sort_column = Game.result
    elif sort_by == 'status':
        sort_column = Game.analysis_status
    elif sort_by == 'date':
        sort_column = Game.game_date
    elif sort_by == 'white':
        sort_column = Game.white_player
    elif sort_by == 'black':
        sort_column = Game.black_player
    elif sort_by == 'time_class':
        sort_column = Game.time_class

    if sort_order == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # Apply pagination
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def get_games_count(
    db: AsyncSession,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    time_class: Optional[str] = None,
    search: Optional[str] = None
) -> int:
    """
    Get total count of games in the database with optional filters.

    Args:
        db: Database session
        date_from: Filter games from this date (format: YYYY.MM.DD)
        date_to: Filter games to this date (format: YYYY.MM.DD)
        status: Filter by analysis status

    Returns:
        Total number of games matching filters
    """
    query = select(func.count(Game.id))

    # Apply filters
    if date_from:
        query = query.where(Game.game_date >= date_from)
    if date_to:
        query = query.where(Game.game_date <= date_to)
    if status:
        query = query.where(Game.analysis_status == status)
    if time_class:
        query = query.where(Game.time_class == time_class)

    if search:
        term = f"%{search.lower()}%"
        query = query.where(
            (func.lower(Game.white_player).ilike(term)) |
            (func.lower(Game.black_player).ilike(term)) |
            (func.lower(Game.result).ilike(term)) |
            (func.lower(Game.game_date).ilike(term))
        )
    result = await db.execute(query)
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


async def update_game_analysis_status(
    db: AsyncSession,
    game_id: int,
    status: str,
    analysis_data: Optional[str] = None
) -> Optional[Game]:
    """
    Update the analysis status and data for a game.

    Args:
        db: Database session
        game_id: Database ID of the game
        status: New analysis status ('queued', 'analyzing', 'completed')
        analysis_data: Optional analysis data (JSON string)

    Returns:
        Updated Game object if found, None otherwise
    """
    game = await get_game_by_id(db, game_id)

    if not game:
        return None

    game.analysis_status = status
    if analysis_data is not None:
        game.analysis_data = analysis_data

    await db.commit()
    await db.refresh(game)
    return game
