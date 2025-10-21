from sqlalchemy import select

from src.services.database.core.database import get_db
from src.services.database.users.models import Users
from src.utils.codes import generate_code


async def create_unique_referral_code():
    """Создаст уникальный реферальный код"""
    while True:
        code = generate_code()
        async with get_db() as session_db:
            result = await session_db.execute(select(Users).where(Users.unique_referral_code == code))
            referral = result.scalars().first()
            if referral: # если данный код уже занят пользователем
                continue
            else:
                return code