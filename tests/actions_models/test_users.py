import pytest
from orjson import orjson
from sqlalchemy import delete, select

from src.exceptions.service_exceptions import UserNotFound
from src.services.admins.models import AdminActions
from src.services.users.actions.action_user import get_user_by_ref_code
from tests.fixtures.helper_functions import parse_redis_user
from src.services.users.models import Users, NotificationSettings, BannedAccounts
from src.services.database.database import get_db
from src.redis_dependencies.core_redis import get_redis
from tests.fixtures.helper_fixture import create_new_user


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'use_redis',
    [
        True,
        False
    ]
)
async def test_get_user(use_redis, create_new_user):
    from src.services.users.actions import get_user
    user = await create_new_user()
    if use_redis:
        async with get_redis() as session_redis:
            await session_redis.set(
                f'user:{user.user_id}',
                orjson.dumps(user.to_dict())
            )
        async with get_db() as session_db:
            await session_db.execute(delete(NotificationSettings).where(NotificationSettings.user_id == user.user_id))
            await session_db.execute(delete(Users).where(Users.user_id == user.user_id))
    else:
        async with get_redis() as session_redis:
            await session_redis.flushdb()


    selected_user = await get_user(user.user_id)

    assert isinstance(selected_user, Users)
    assert selected_user.user_id == user.user_id
    assert selected_user.username == user.username
    assert selected_user.unique_referral_code == user.unique_referral_code
    assert selected_user.balance == user.balance
    assert selected_user.total_sum_replenishment == user.total_sum_replenishment
    assert selected_user.total_profit_from_referrals == user.total_profit_from_referrals
    # created_at проверяем с допуском
    assert abs((selected_user.created_at - user.created_at).total_seconds()) < 2

async def test_get_user_by_ref_code(create_new_user):
    new_user = await create_new_user()
    returned_user = await get_user_by_ref_code(new_user.unique_referral_code)
    assert new_user.to_dict() == returned_user.to_dict()

@pytest.mark.asyncio
async def test_update_user(create_new_user):
    """Проверяем, что update_user меняет данные в БД и Redis"""
    from src.services.users.actions import update_user
    # изменяем данные пользователя
    user = await create_new_user()
    user.username = "updated_username"
    user.balance = 500
    user.total_profit_from_referrals = 50

    updated_user = await update_user(user)

    async with get_db() as session_db:
        db_user = await session_db.get(Users, user.user_id)

    # проверка БД
    assert db_user.username == "updated_username"
    assert db_user.balance == 500
    assert db_user.total_profit_from_referrals == 50

    # проверка возвращаемого объекта
    assert isinstance(updated_user, Users)
    assert updated_user.username == db_user.username
    assert updated_user.balance == db_user.balance
    assert updated_user.total_profit_from_referrals == db_user.total_profit_from_referrals

    # проверка Redis
    async with get_redis() as session_redis:
        redis_data = await session_redis.get(f"user:{user.user_id}")
        assert redis_data is not None
        redis_user = Users(**parse_redis_user(redis_data))
        assert redis_user.username == "updated_username"
        assert redis_user.balance == 500
        assert redis_user.total_profit_from_referrals == 50


@pytest.mark.asyncio
async def test_add_new_user_creates_records_and_logs(
        replacement_fake_bot,
        clean_db
):
    """Проверяет создание пользователя, уведомлений, логов и запись в Redis"""
    from src.services.users.actions.action_other_with_user import add_new_user

    fake_bot = replacement_fake_bot
    user_id = 101
    username = "test_user"

    await add_new_user(user_id, username, language="en")

    # Проверяем БД
    async with get_db() as session:
        result_user = await session.execute(select(Users).where(Users.user_id == user_id))
        user = result_user.scalar_one()
        assert user.username == username
        assert user.language == "en"

        result_notif = await session.execute(select(NotificationSettings).where(NotificationSettings.user_id == user_id))
        notif = result_notif.scalar_one()
        assert notif.user_id == user_id

    # Проверяем Redis
    async with get_redis() as r:
        data = await r.get(f"user:{user_id}")
        assert data is not None
        user_dict = orjson.loads(data)
        assert user_dict["username"] == username

    # Проверяем FakeBot (лог)
    assert fake_bot.check_str_in_messages("#Новый_пользователь")
    assert fake_bot.check_str_in_messages(username)


@pytest.mark.asyncio
async def test_update_notification_updates_correctly(replacement_fake_bot, create_new_user):
    """Проверяем, что update_notification обновляет флаги корректно"""
    from src.services.users.actions.action_other_with_user import update_notification
    user = await create_new_user()

    updated = await update_notification(
        user.user_id,
        referral_invitation=False,
        referral_level_up=True,
        referral_replenishment=False
    )

    assert updated.referral_invitation is False
    assert updated.referral_level_up is True
    assert updated.referral_replenishment is False

    async with get_db() as session:
        result = await session.execute(select(NotificationSettings).where(NotificationSettings.user_id == user.user_id))
        notif = result.scalar_one()
        assert notif.referral_invitation is False
        assert notif.referral_level_up is True
        assert notif.referral_replenishment is False


@pytest.mark.asyncio
async def test_add_banned_account_creates_ban_and_log(replacement_fake_bot, create_new_user):
    """Проверяем, что при добавлении бана создаётся запись в БД, Redis и лог"""
    from src.services.users.actions.action_other_with_user import add_banned_account

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    admin = await create_new_user()
    admin_id = admin.user_id
    reason = "cheating"

    await add_banned_account(admin_id, user.user_id, reason)

    async with get_db() as session:
        ban_res = await session.execute(select(BannedAccounts).where(BannedAccounts.user_id == user.user_id))
        ban = ban_res.scalar_one()
        assert ban.reason == reason

        admin_log_res = await session.execute(select(AdminActions))
        admin_log = admin_log_res.scalar_one()
        assert admin_log.user_id == admin_id
        assert admin_log.details["user_id"] == user.user_id

    # Redis
    async with get_redis() as r:
        redis_val = await r.get(f"banned_account:{user.user_id}")
        assert redis_val.decode() == reason

    # Лог в FakeBot
    assert fake_bot.check_str_in_messages("#Аккаунт_забанен")
    assert fake_bot.check_str_in_messages(reason)


@pytest.mark.asyncio
async def test_add_banned_account_user_not_found(replacement_fake_bot):
    """Если пользователя нет — должно выбрасываться исключение UserNotFound"""
    from src.services.users.actions.action_other_with_user import add_banned_account
    with pytest.raises(UserNotFound):
        await add_banned_account(1, 999999, "reason")


@pytest.mark.asyncio
async def test_delete_banned_account_removes_data(replacement_fake_bot, create_new_user):
    """Проверяет, что при удалении бана — Redis очищается, запись удаляется, лог пишется"""
    from src.services.users.actions.action_other_with_user import add_banned_account
    from src.services.users.actions.action_other_with_user import delete_banned_account

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    admin = await create_new_user()
    admin_id = admin.user_id
    reason = "spam"

    # Добавим бан вручную
    await add_banned_account(admin_id, user.user_id, reason)

    # Проверим, что есть в Redis
    async with get_redis() as r:
        assert await r.get(f"banned_account:{user.user_id}") is not None

    # Удаляем
    await delete_banned_account(admin_id, user.user_id)

    # Проверяем Redis — должен быть очищен
    async with get_redis() as r:
        assert await r.get(f"banned_account:{user.user_id}") is None

    # Проверяем лог
    assert fake_bot.check_str_in_messages("#Аккаунт_разбанен")
    assert fake_bot.check_str_in_messages(str(user.user_id))


@pytest.mark.asyncio
async def test_delete_banned_account_not_found(replacement_fake_bot):
    """Если в Redis нет ключа — должно выбрасываться UserNotFound"""
    from src.services.users.actions.action_other_with_user import delete_banned_account
    with pytest.raises(UserNotFound):
        await delete_banned_account(1, 999999)