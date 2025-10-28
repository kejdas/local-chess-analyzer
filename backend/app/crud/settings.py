from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from ..db.models import Setting
from typing import Dict, Any, List

async def get_all_settings(db: AsyncSession) -> Dict[str, Any]:
    result = await db.execute(select(Setting))
    settings_list = result.scalars().all()
    
    settings_dict = {}
    for setting in settings_list:
        settings_dict[setting.key] = setting.value
    return settings_dict

async def update_settings(db: AsyncSession, settings_data: Dict[str, Any]) -> List[str]:
    updated_keys = []
    for key, value in settings_data.items():
        setting_obj = Setting(key=key, value=str(value))
        await db.merge(setting_obj)
        updated_keys.append(key)
    
    await db.commit()
    return updated_keys
