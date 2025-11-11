from sqlalchemy import select

from src.services.database.admins.models import MessageForSending, Admins
from src.services.database.core.database import get_db
from src.services.redis.core_redis import get_redis

async def check_admin(user_id) -> bool:
    """Проверит наличие админа по данному ID"""
    async with get_redis() as session_redis:
        admin = await session_redis.get(f'admin:{user_id}')

    return True if admin else False

async def create_admin(user_id: int) -> Admins:
    async with get_db() as session_db:
        # проверка на наличие такого админа
        result_db = await session_db.execute(select(Admins).where(Admins.user_id == user_id))
        admin = result_db.scalar_one_or_none()
        if admin:
            return admin

        # создание
        new_admin = Admins(user_id=user_id)
        new_message_for_sending = MessageForSending(user_id=user_id)
        session_db.add(new_admin)
        session_db.add(new_message_for_sending)
        await session_db.commit()
        await session_db.refresh(new_admin)

        async with get_redis() as session_redis:
            await session_redis.set(f"admin:{user_id}", '_')

        return new_admin


async def get_message_for_sending(admin_id: int) -> MessageForSending | None:
    """
    Вёрнёт MessageForSending, для данного админа.
    Если админа нет по такому id, то ничего не вернёт.
    Если у админа нет записи в БД, создаст её
    """
    async with get_db() as session_db:
        result_db = await session_db.execute(select(MessageForSending).where(MessageForSending.user_id == admin_id))
        message_for_sending = result_db.scalar_one_or_none()
        if message_for_sending:
            return message_for_sending
        else:
            if await check_admin(admin_id): # если пользователь с данным id реально админ
                new_message_for_sending = MessageForSending(user_id=admin_id)
                session_db.add(new_message_for_sending)
                await session_db.commit()
                await session_db.refresh(new_message_for_sending)
                return new_message_for_sending

async def update_message_for_sending(
    user_id: int,
    content: str = None,
    photo_path: str = None,
    button_url: str = None,
) -> MessageForSending | None:
    """
    Обновит данные для массовой рассылки.
    Если нет такого админа, то ничего не произойдёт
    """
    is_admin = await check_admin(user_id)
    if not is_admin:
        return

    new_message_for_sending = MessageForSending(
        user_id=user_id,
        content=content,
        photo_path=photo_path,
        button_url=button_url,
    )

    async with get_db() as session_db:
        session_db.add(new_message_for_sending)
        await session_db.commit()
        await session_db.refresh(new_message_for_sending)

    return new_message_for_sending
