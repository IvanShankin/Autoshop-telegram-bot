import uuid
from typing import List, Optional

from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload

from src.config import PAGE_SIZE
from src.services.database.admins.models import MessageForSending, Admins, AdminActions, SentMasMessages
from src.services.database.core.database import get_db
from src.services.database.system.actions import get_ui_image, create_ui_image, delete_ui_image, update_ui_image
from src.services.redis.core_redis import get_redis
from src.utils.ui_images_data import get_default_image_bytes


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
        session_db.add(new_admin)

        ui_image = await create_ui_image(str(uuid.uuid4()), get_default_image_bytes(), show=False)

        if not await get_message_for_sending(user_id):
            new_message_for_sending = MessageForSending(user_id=user_id,  ui_image_key=ui_image.key)
            session_db.add(new_message_for_sending)

        await session_db.commit()
        await session_db.refresh(new_admin)

        async with get_redis() as session_redis:
            await session_redis.set(f"admin:{user_id}", '_')

        return new_admin


async def get_message_for_sending(admin_id: int) -> MessageForSending | None:
    """
    Вёрнёт MessageForSending, для данного админа с подгруженным ui_image.

    Если админа нет по такому id, то ничего не вернёт.
    Если у админа нет записи в БД, создаст её
    """
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(MessageForSending)
            .options(selectinload(MessageForSending.ui_image))
            .where(MessageForSending.user_id == admin_id)
        )
        message_for_sending = result_db.scalar_one_or_none()
        if message_for_sending:
            return message_for_sending
        return None


async def update_message_for_sending(
    user_id: int,
    content: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    show_image: Optional[bool] = None,
    button_url: Optional[str] = False,
) -> MessageForSending | None:
    """
    Обновит данные для массовой рассылки.
    Если нет такого админа, то ничего не произойдёт
    :param user_id: ID админа
    :param content: текс у будущего сообщения
    :param file_bytes: Поток байт для создания фото
    :param button_url: можно передать None
    """
    is_admin = await check_admin(user_id)
    if not is_admin:
        return

    message_data = None
    old_ui_image_key = None
    update_data = {}
    if content is not None:
        update_data["content"] = content
    if file_bytes is not None:
        message_data = await get_message_for_sending(user_id)
        new_ui_image = await create_ui_image(str(uuid.uuid4()), file_data=file_bytes, show=True)
        old_ui_image_key = message_data.ui_image_key
        update_data["ui_image_key"] = new_ui_image.key

    if show_image is not None:
        if not message_data:
            message_data =  await get_message_for_sending(user_id)

        await update_ui_image(key=message_data.ui_image_key, show=show_image)
    if button_url is not False: # именно такое условие
        update_data["button_url"] = button_url

    if update_data:
        async with get_db() as session_db:
            result_db = await session_db.execute(
                update(MessageForSending)
                .where(MessageForSending.user_id == user_id)
                .values(**update_data)
                .returning(MessageForSending)
            )
            msg = result_db.scalar_one_or_none()
            await session_db.commit()

        if file_bytes is not None:
            await delete_ui_image(old_ui_image_key)

        return msg
    return None


async def add_admin_action(user_id: int, action_type: str, message: str, details: dict) -> AdminActions:
    new_action = AdminActions(user_id=user_id, action_type=action_type, message=message, details=details)

    async with get_db() as session_db:
        session_db.add(new_action)
        await session_db.commit()

    return new_action


async def get_sent_mass_messages_by_page(
    page: int = None,
    page_size: int = PAGE_SIZE,
) -> List[SentMasMessages]:
    async with get_db() as session_db:
        query = select(SentMasMessages)
        if page:
            offset = (page - 1) * page_size
            query = query.limit(page_size).offset(offset)

        result_db = await session_db.execute(query.order_by(SentMasMessages.created_at.desc()))
        return result_db.scalars().all()


async def get_count_sent_messages() -> int:
    async with get_db() as session_db:
        result_db = await session_db.execute(select(func.count()).select_from(SentMasMessages))
        return result_db.scalar()