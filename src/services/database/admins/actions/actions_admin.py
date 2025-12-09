from sqlalchemy import select

from src.services.database.admins.models import MessageForSending, Admins, AdminActions
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
        return None


async def update_message_for_sending(
    user_id: int,
    content: str = None,
    photo_path: str = False,
    button_url: str = False,
) -> MessageForSending | None:
    """
    Обновит данные для массовой рассылки.
    Если нет такого админа, то ничего не произойдёт
    :param user_id: ID админа
    :param content: текс у будущего сообщения
    :param photo_path: можно передать None
    :param button_url: можно передать None
    """
    is_admin = await check_admin(user_id)
    if not is_admin:
        return

    update_data = {}
    if content is not None:
        update_data["content"] = content
    if photo_path is not False: # именно такое условие
        update_data["photo_path"] = photo_path
    if button_url is not False: # именно такое условие
        update_data["button_url"] = button_url

    if update_data:
        update_data["user_id"] = user_id
        new_message_for_sending = MessageForSending(**update_data)

        async with get_db() as session_db:
            session_db.add(new_message_for_sending)
            await session_db.commit()
            await session_db.refresh(new_message_for_sending)

        return new_message_for_sending
    return None


async def add_admin_action(user_id: int, action_type: str, message: str, details: dict) -> AdminActions:
    new_action = AdminActions(user_id=user_id, action_type=action_type, message=message, details=details)

    async with get_db() as session_db:
        session_db.add(new_action)
        await session_db.commit()

    return new_action

