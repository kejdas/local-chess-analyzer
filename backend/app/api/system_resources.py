from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from ..db.database import get_db_session
from ..crud import settings as crud_settings
from ..services.system_resources import get_system_resources


router = APIRouter()


@router.get("/api/system-resources")
async def get_system_resources_endpoint(
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Get system resource information including CPU, memory, and Stockfish status.

    Returns:
        Dictionary with system resource information:
        - cpu: CPU information (cores, recommended threads)
        - memory: Memory information (total, available, recommended hash)
        - stockfish: Stockfish binary information (path, validity)
    """
    # Get current Stockfish path from settings
    settings = await crud_settings.get_all_settings(db)
    stockfish_path = settings.get('stockfish_path')

    # Get system resources with Stockfish validation
    resources = get_system_resources(stockfish_path)

    return resources
