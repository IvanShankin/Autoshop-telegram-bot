import pytest
from orjson import orjson
from sqlalchemy import delete, select

from tests.helpers.helper_functions import parse_redis_user, comparison_models
from src.exceptions import UserNotFound, NotEnoughMoney
from src.database.models.admins import AdminActions
from src.application._database.users.actions.action_user import get_user_by_ref_code
from src.database.models.users import Users, NotificationSettings, BannedAccounts, WalletTransaction, \
    TransferMoneys, \
    UserAuditLogs, Replenishments
from src.database import get_db
from src.infrastructure.redis import get_redis



@pytest.mark.asyncio
async def test_add_banned_account_creates_ban_and_log(replacement_fake_bot_fix, create_new_user):
    """Проверяем, что при добавлении бана создаётся запись в БД, Redis и лог"""
    from src.application._database.users.actions import add_banned_account

    fake_bot = replacement_fake_bot_fix
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


@pytest.mark.asyncio
async def test_add_banned_account_user_not_found(replacement_fake_bot_fix):
    """Если пользователя нет — должно выбрасываться исключение UserNotFound"""
    from src.application._database.users.actions import add_banned_account
    with pytest.raises(UserNotFound):
        await add_banned_account(1, 999999, "reason")


@pytest.mark.asyncio
async def test_delete_banned_account_removes_data(replacement_fake_bot_fix, create_new_user):
    """Проверяет, что при удалении бана — Redis очищается, запись удаляется, лог пишется"""
    from src.application._database.users.actions import add_banned_account
    from src.application._database.users.actions import delete_banned_account

    fake_bot = replacement_fake_bot_fix
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


@pytest.mark.asyncio
async def test_delete_banned_account_not_found(replacement_fake_bot_fix):
    """Если в Redis нет ключа — должно выбрасываться UserNotFound"""
    from src.application._database.users.actions import delete_banned_account
    with pytest.raises(UserNotFound):
        await delete_banned_account(1, 999999)



@pytest.mark.asyncio
async def test_get_income_from_referral(replacement_fake_bot_fix, create_new_user, create_wallet_transaction):
    from src.application._database.users.actions import get_count_wallet_transaction

    user = await create_new_user()
    transaction_1 = await create_wallet_transaction(user.user_id, amount=100)
    transaction_2 = await create_wallet_transaction(user.user_id, amount=200)

    counter = await get_count_wallet_transaction(user.user_id)

    assert counter == 2


@pytest.mark.asyncio
async def test_admin_update_user_balance(replacement_fake_bot_fix, create_new_user, create_admin_fix):
    from src.application._database.users.actions import admin_update_user_balance
    user = await create_new_user()
    admin = await create_admin_fix()

    await admin_update_user_balance(
        admin_id=admin.user_id,
        target_user_id=user.user_id,
        new_balance=100
    )

    async with get_db() as session_db:
        user_db = await session_db.execute(select(Users).where(Users.user_id == user.user_id))
        user = user_db.scalar()
        assert user.balance == 100

        trans_db = await session_db.execute(select(WalletTransaction).where(WalletTransaction.user_id == user.user_id))
        trans = trans_db.scalar()
        assert trans

        log_db = await session_db.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == user.user_id))
        log = log_db.scalar()
        assert log
