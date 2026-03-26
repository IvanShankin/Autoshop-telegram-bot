from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.models.read_models.other import SettingsDTO
from src.models.update_models.system import UpdateSettingsDTO
from src.repository.database.systems import SettingsRepository
from src.repository.redis import SettingsCacheRepository


class SettingsService:

    def __init__(
        self,
        settings_repo: SettingsRepository,
        cache_repo: SettingsCacheRepository,
        conf: Config,
        session_db: AsyncSession,
    ):
        self.settings_repo = settings_repo
        self.cache_repo = cache_repo
        self.conf = conf
        self.session_db = session_db

    async def get_settings(self) -> Optional[SettingsDTO]:
        cached = await self.cache_repo.get()
        if cached:
            return cached

        settings = await self.settings_repo.get()
        if settings:
            await self.cache_repo.set(settings)
        return settings

    async def update_settings(
        self,
        data: UpdateSettingsDTO,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ) -> Optional[SettingsDTO]:
        values = data.model_dump(exclude_unset=True)
        settings = await self.settings_repo.update(**values)

        if make_commit:
            await self.session_db.commit()

        if settings and filling_redis:
            await self.cache_repo.set(settings)

        return settings
