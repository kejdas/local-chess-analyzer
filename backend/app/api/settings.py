from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List

from ..db.database import get_db_session
from ..crud import settings as crud_settings # 'as' dla czytelności

router = APIRouter()

@router.get("/api/settings", response_model=Dict[str, Any])
async def read_settings(db: AsyncSession = Depends(get_db_session)):
    settings = await crud_settings.get_all_settings(db)
    return settings

@router.put("/api/settings")
async def write_settings(
    settings_data: Dict[str, Any], # Przyjmuje dowolny słownik JSON
    db: AsyncSession = Depends(get_db_session)
):
    try:
        updated_keys = await crud_settings.update_settings(db, settings_data)
        return {"status": "success", "updated_settings": updated_keys}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd zapisu ustawień: {str(e)}")
