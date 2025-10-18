import pytest
from orjson import orjson
from sqlalchemy import delete, select

from src.exceptions.service_exceptions import UserNotFound, NotEnoughMoney
from src.services.admins.models import AdminActions
from src.services.users.actions.action_user import get_user_by_ref_code
from tests.helpers.helper_functions import parse_redis_user, comparison_models
from src.services.users.models import Users, NotificationSettings, BannedAccounts, WalletTransaction, TransferMoneys, \
    UserAuditLogs
from src.services.database.database import get_db
from src.redis_dependencies.core_redis import get_redis
from tests.helpers.helper_fixture import create_new_user, create_wallet_transaction


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
        referral_replenishment=False
    )

    assert updated.referral_invitation is False
    assert updated.referral_replenishment is False

    async with get_db() as session:
        result = await session.execute(select(NotificationSettings).where(NotificationSettings.user_id == user.user_id))
        notif = result.scalar_one()
        assert notif.referral_invitation is False
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


@pytest.mark.asyncio
async def test_get_wallet_transaction(replacement_fake_bot, create_new_user):
    from src.services.users.actions.action_other_with_user import get_wallet_transaction
    user = await create_new_user()
    record = WalletTransaction(
        user_id=user.user_id,
        type='replenish',
        amount=100,
        balance_before=0,
        balance_after=100
    )

    async with get_db() as session_db:
        session_db.add(record)
        await session_db.commit()

    wallet_transaction = await get_wallet_transaction(record.wallet_transaction_id)
    assert wallet_transaction.to_dict() == record.to_dict()


@pytest.mark.asyncio
async def test_get_wallet_transaction_page(replacement_fake_bot, create_new_user, create_wallet_transaction):
    from src.services.users.actions.action_other_with_user import get_wallet_transaction_page

    user = await create_new_user()
    transaction_1 = await create_wallet_transaction(user.user_id, amount=100)
    transaction_2 = await create_wallet_transaction(user.user_id, amount=200)
    transaction_3 = await create_wallet_transaction(user.user_id, amount=300)

    transaction = await get_wallet_transaction_page(user_id = user.user_id, page=1)

    assert transaction[0].to_dict() == transaction_3.to_dict()
    assert transaction[1].to_dict() == transaction_2.to_dict()
    assert transaction[2].to_dict() == transaction_1.to_dict()


@pytest.mark.asyncio
async def test_get_income_from_referral(replacement_fake_bot, create_new_user, create_wallet_transaction):
    from src.services.users.actions.action_other_with_user import get_count_wallet_transaction

    user = await create_new_user()
    transaction_1 = await create_wallet_transaction(user.user_id, amount=100)
    transaction_2 = await create_wallet_transaction(user.user_id, amount=200)

    counter = await get_count_wallet_transaction(user.user_id)

    assert counter == 2


@pytest.mark.asyncio
async def test_money_transfer(replacement_fake_bot, create_new_user):
    from src.services.users.actions.action_other_with_user import money_transfer
    sender = await create_new_user(balance=100)
    recipient = await create_new_user()

    await money_transfer(sender_id=sender.user_id, recipient_id=recipient.user_id, amount=100)

    async with get_db() as session_db:
        result_sender = await session_db.execute(select(Users).where(Users.user_id == sender.user_id))
        result_recipient = await session_db.execute(select(Users).where(Users.user_id == recipient.user_id))
        sender = result_sender.scalar()
        recipient = result_recipient.scalar()

        # проверка логов
        result_db = await session_db.execute(select(TransferMoneys).where(TransferMoneys.user_from_id == sender.user_id))
        assert result_db.scalar_one_or_none()

        result_db = await session_db.execute(select(WalletTransaction).where(WalletTransaction.user_id == sender.user_id))
        assert result_db.scalar_one_or_none()
        result_db = await session_db.execute(select(WalletTransaction).where(WalletTransaction.user_id == recipient.user_id))
        assert result_db.scalar_one_or_none()

        result_db = await session_db.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == sender.user_id))
        assert result_db.scalar_one_or_none()
        result_db = await session_db.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == recipient.user_id))
        assert result_db.scalar_one_or_none()

    # проверка БД
    assert sender.balance == 0
    assert recipient.balance == 100

    # проверка redis
    async with get_redis() as session_redis:
        sender_redis = await session_redis.get(f"user:{sender.user_id}")
        recipient_redis = await session_redis.get(f"user:{recipient.user_id}")

    await comparison_models(sender, orjson.loads(sender_redis))
    await comparison_models(recipient, orjson.loads(recipient_redis))


@pytest.mark.asyncio
async def test_money_transfer_not_enough_money(replacement_fake_bot, create_new_user):
    """Тест на исключение нет денег"""
    from src.services.users.actions.action_other_with_user import money_transfer

    sender = await create_new_user(balance=50)
    recipient = await create_new_user(balance=0)

    with pytest.raises(NotEnoughMoney):
        await money_transfer(sender_id=sender.user_id, recipient_id=recipient.user_id, amount=100)

    # проверки: балансы и записи не изменились
    async with get_db() as session_db:
        result_sender = await session_db.execute(select(Users).where(Users.user_id == sender.user_id))
        result_recipient = await session_db.execute(select(Users).where(Users.user_id == recipient.user_id))
        db_sender = result_sender.scalar_one()
        db_recipient = result_recipient.scalar_one()

        assert db_sender.balance == 50
        assert db_recipient.balance == 0

        # нет записей о переводах / транзакциях / аудит-логах
        assert not (await session_db.execute(select(TransferMoneys).where(TransferMoneys.user_from_id == sender.user_id))).scalar_one_or_none()
        assert not (await session_db.execute(select(WalletTransaction).where(WalletTransaction.user_id == sender.user_id))).scalar_one_or_none()
        assert not (await session_db.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == sender.user_id))).scalar_one_or_none()

@pytest.mark.asyncio
async def test_money_transfer_user_not_found(replacement_fake_bot, create_new_user):
    """Тест на исключение не найдено пользователя"""
    from src.services.users.actions.action_other_with_user import money_transfer
    # создаём только получателя
    recipient = await create_new_user(balance=0)

    with pytest.raises(UserNotFound):
        await money_transfer(sender_id=99999999, recipient_id=recipient.user_id, amount=10)

    # убедимся, что у реального получателя ничего не изменилось
    async with get_db() as session_db:
        result_recipient = await session_db.execute(select(Users).where(Users.user_id == recipient.user_id))
        db_recipient = result_recipient.scalar_one()
        assert db_recipient.balance == 0

@pytest.mark.asyncio
async def test_money_transfer_integrity_error_rollback(monkeypatch, replacement_fake_bot, create_new_user):
    """
    Симулируем ошибку при создании TransferMoneys (бросаем Exception),
    ожидаем откат (балансы не меняются), и что send_log был вызван.
    """
    from src.services.users.actions.action_other_with_user import money_transfer
    from src.services.users.actions import action_other_with_user as money_module

    sender = await create_new_user(balance=100)
    recipient = await create_new_user(balance=0)
    fake_bot = replacement_fake_bot

    # симулируем ошибку в момент создания TransferMoneys
    original_init = TransferMoneys.__init__

    def failing_init(self, *args, **kwargs):
        # можно бросать конкретную DB-ошибку, но Exception достаточно для отката
        raise Exception("simulated failure during TransferMoneys construction")

    monkeypatch.setattr(money_module.TransferMoneys, "__init__", failing_init)

    await money_transfer(sender_id=sender.user_id, recipient_id=recipient.user_id, amount=100)

    # восстановим (monkeypatch сам откатит к original при тесте завершении,
    # но явно оставить оригинал не обязательно; для читаемости сохраняем)
    monkeypatch.setattr(money_module.TransferMoneys, "__init__", original_init)

    # Проверяем — откат: балансы не изменились, нет записей о переводах/транзакциях/аудите
    async with get_db() as session_db:
        result_sender = await session_db.execute(select(Users).where(Users.user_id == sender.user_id))
        result_recipient = await session_db.execute(select(Users).where(Users.user_id == recipient.user_id))
        db_sender = result_sender.scalar_one()
        db_recipient = result_recipient.scalar_one()

        assert db_sender.balance == 100
        assert db_recipient.balance == 0

        assert not (await session_db.execute(select(TransferMoneys).where(TransferMoneys.user_from_id == sender.user_id))).scalar_one_or_none()
        assert not (await session_db.execute(select(WalletTransaction).where(WalletTransaction.user_id == sender.user_id))).scalar_one_or_none()
        assert not (await session_db.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == sender.user_id))).scalar_one_or_none()

    assert fake_bot.sent, "send_log должен был вызваться при обработке исключения"

