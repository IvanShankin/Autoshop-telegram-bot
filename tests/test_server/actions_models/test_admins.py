import pytest
from sqlalchemy import select

from src.services.redis.core_redis import get_redis
from src.services.database.admins.actions import check_admin, create_admin as create_admin_fun, get_message_for_sending, \
    update_message_for_sending
from src.services.database.admins.models import MessageForSending, Admins
from src.services.database.core.database import get_db

@pytest.mark.asyncio
async def test_check_admin(create_admin_fix):
    admin = await create_admin_fix()
    assert await check_admin(admin.user_id)


@pytest.mark.asyncio
async def test_create_admin_creates_new_admin_and_message(create_new_user):
    user = await create_new_user()
    # вызываем тестируемую функцию
    admin = await create_admin_fun(user.user_id)

    # проверяем что admin создан
    assert isinstance(admin, Admins)
    assert admin.user_id == user.user_id

    # проверяем что MessageForSending тоже создалась
    async with get_db() as session_db:
        result = await session_db.execute(
            select(MessageForSending).where(MessageForSending.user_id == user.user_id)
        )
        message = result.scalar_one_or_none()
        assert message is not None

    # проверяем, что в redis появился ключ
    async with get_redis() as session_redis:
        redis_value = await session_redis.get(f"admin:{user.user_id}")
        assert redis_value == b'_'

@pytest.mark.asyncio
async def test_create_admin_returns_existing_admin(create_admin_fix):
    # вызываем повторно для уже существующего админа
    admin_1 = await create_admin_fix()
    admin_2 = await create_admin_fun(admin_1.user_id)

    assert admin_1.user_id == admin_2.user_id

@pytest.mark.asyncio
async def test_get_message_for_sending_returns_existing(create_admin_fix):
    # сначала создадим запись
    admin = await create_admin_fix()
    message = await get_message_for_sending(admin.user_id)
    assert isinstance(message, MessageForSending)

    # второй вызов должен вернуть ту же запись
    message_2 = await get_message_for_sending(admin.user_id)
    assert message_2.user_id == message.user_id


@pytest.mark.asyncio
async def test_get_message_for_sending_creates_if_missing(create_admin_fix):
    # удаляем все записи MessageForSending из БД
    from src.services.database.core.database import get_db

    admin = await create_admin_fix()
    async with get_db() as session_db:
        await session_db.execute(
            MessageForSending.__table__.delete().where(MessageForSending.user_id == admin.user_id)
        )
        await session_db.commit()

    message = await get_message_for_sending(admin.user_id)
    assert message is not None
    assert message.user_id == admin.user_id

@pytest.mark.asyncio
async def test_update_message_for_sending_updates_data(create_admin_fix):
    admin = await create_admin_fix()
    updated = await update_message_for_sending(
        user_id=admin.user_id,
        content="Hello World",
        photo_path="photo.png",
        button_url="https://example.com"
    )

    assert isinstance(updated, MessageForSending)
    assert updated.content == "Hello World"
    assert updated.photo_path == "photo.png"
    assert updated.button_url == "https://example.com"

