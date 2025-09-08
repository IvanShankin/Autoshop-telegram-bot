import asyncio
import contextlib
from datetime import datetime

import orjson
import pytest
import pytest_asyncio
from sqlalchemy import select, Table, MetaData

from src.config import DT_FORMAT_FOR_LOGS
from src.database.models_main import Replenishments, Users, WalletTransaction, UserAuditLogs
from src.database.database import get_db
from src.database.events.core_event import event_queue
from src.i18n import get_i18n
from src.modules.referrals.database.events.schemas_ref import NewIncomeFromRef
from src.modules.referrals.database.models_ref import IncomeFromReferrals, Referrals
from src.redis_dependencies.core_redis import get_redis
from tests.fixtures.helper_fixture import create_new_user, create_type_payment, create_referral, create_replenishment
from tests.fixtures.monkeypatch_data import replacement_fake_bot, replacement_fake_keyboard, fake_bot
from tests.fixtures.helper_functions import comparison_models


@pytest_asyncio.fixture()
async def start_event_handler():
    # данный импорт обязательно тут, ибо aiogram запустит свой even_loop который не даст работать тесту в режиме отладки
    from src.database.events.triggers_processing import run_triggers_processing

    task = asyncio.create_task(run_triggers_processing())
    try:
        yield
    finally:
        await event_queue.join() # ждём пока все тестовые события обработаны
        event_queue.put_nowait(None) # закрываем dispatcher через sentinel
        with contextlib.suppress(asyncio.CancelledError):
            await task

class TestHandlerNewReplenishment:
    async def create_and_update_replenishment(self, user_id: int, type_payment_id: int)->Replenishments:
        """
        Создаст новый replenishment с переданными параметрами и обновит его статус на 'pending'.
        :return возвращает созданный Replenishments
        """

        async with get_db() as session_db:
            new_replenishment = Replenishments(
                user_id = user_id,
                type_payment_id = type_payment_id,
                origin_amount = 100,
                amount = 105,
                status = 'pending'
            )
            session_db.add(new_replenishment)
            await session_db.commit()
            await session_db.refresh(new_replenishment)

            # Меняем статус на processing (это должно запустить обработчик)
            result_db = await session_db.execute(select(Replenishments).where(Replenishments.replenishment_id == new_replenishment.replenishment_id))
            replenishment = result_db.scalar_one_or_none()
            replenishment.status='processing'

            await session_db.commit()
        return new_replenishment

    @pytest.mark.asyncio
    async def test_access(
            self,
            replacement_fake_bot,
            replacement_fake_keyboard,
            create_new_user,
            create_type_payment,
            start_event_handler
        ):
        # Исходные данные пользователя
        initial_balance = create_new_user.balance
        initial_total_sum = create_new_user.total_sum_replenishment
        user_id = create_new_user.user_id

        await self.create_and_update_replenishment(user_id, create_type_payment['type_payment_id'])

        q = event_queue
        await asyncio.sleep(0) # для передачи управления
        await q.join() # дождёмся пока очередь событий выполнится

        async with get_db() as session_db:
            # Проверяем, что баланс пользователя обновился
            user_result = await session_db.execute(select(Users).where(Users.user_id == user_id))
            updated_user = user_result.scalar_one()

            assert updated_user.balance == initial_balance + 105, "Баланс пользователя не обновился"
            assert updated_user.total_sum_replenishment == initial_total_sum + 105, "Общая сумма пополнений не обновилась"

            # Проверяем создание записи в WalletTransaction
            transaction_result = await session_db.execute(
                select(WalletTransaction)
                .where(WalletTransaction.user_id == user_id)
            )
            wallet_transaction = transaction_result.scalar_one()

            assert wallet_transaction is not None, "Запись в WalletTransaction не создана"
            assert wallet_transaction.type == 'replenish', "Неверный тип транзакции"
            assert wallet_transaction.amount == 105, "Неверная сумма транзакции"
            assert wallet_transaction.balance_before == initial_balance, "Неверный баланс до операции"
            assert wallet_transaction.balance_after == initial_balance + 105, "Неверный баланс после операции"

            # Проверяем создание записи в UserAuditLogs
            log_result = await session_db.execute(
                select(UserAuditLogs)
                .where(UserAuditLogs.user_id == user_id)
            )
            user_log = log_result.scalar_one()

            assert user_log is not None, "Запись в UserAuditLogs не создана"
            assert user_log.action_type == 'replenish', "Неверный тип действия в логах"
            assert user_log.details['amount'] == 105, "Неверная сумма в деталях лога"
            assert user_log.details['new_balance'] == initial_balance + 105, "Неверный новый баланс в деталях лога"

        async with get_redis() as session_redis:
            result_redis = orjson.loads(await session_redis.get(f'user:{updated_user.user_id}'))

        await comparison_models(updated_user, result_redis)

    @pytest.mark.asyncio
    async def test_fail(
            self,
            replacement_fake_bot,
            replacement_fake_keyboard,
            create_new_user,
            create_type_payment,
            start_event_handler,
        ):
        """
        Обработает ошибку пополнения, путём удаления записи в БД об этом пополнении.
        Пользователю в итоге должны начислиться деньги, но в должны отправить лог админу и саппорту о том что произошла ошибка
        """

        print("\n\nНачали проверять test_fail\n\n")

        # необходимо тут иначе в режиме отладки не будет работать
        from src.database.action_core_models import get_settings, update_settings
        from src.database.database import engine
        user = create_new_user

        async with engine.begin() as conn:
            # Удаляем таблицу для получения ошибки
            await conn.run_sync(lambda sync_conn: Table(WalletTransaction.__table__, MetaData()).drop(sync_conn))

        new_replenishment = await self.create_and_update_replenishment(user.user_id, create_type_payment['type_payment_id'])

        settings = await get_settings()
        settings.channel_for_logging_id = 123456789
        await update_settings(settings)

        q = event_queue
        await asyncio.sleep(0)  # для передачи управления
        await q.join()  # дождёмся пока очередь событий выполнится

        i18n = get_i18n(user.language, 'replenishment_dom')
        message_for_user = i18n.ngettext(
            "Balance successfully replenished by {sum} ruble.\nThank you for choosing us!",
            "Balance successfully replenished by {sum} rubles.\nThank you for choosing us!",
            new_replenishment.amount
        ).format(
            sum=new_replenishment.amount
        )
        message_log = i18n.gettext(
            "#Replenishment_error \n\nUser @{username} Paid money, balance updated, but an error occurred inside the server. \n"
            "Replenishment ID: {replenishment_id}.\nError: {error} \n\nTime: {time}"
        ).format(
            username=user.username,
            replenishment_id=new_replenishment.replenishment_id,
            error='ошибка',
            time=datetime.now().strftime(DT_FORMAT_FOR_LOGS)
        )

        assert fake_bot.get_message(user.user_id, message_for_user)
        assert fake_bot.check_str_in_messages(message_log[:100])

@pytest.mark.asyncio
async def test_handler_new_income_referral(
        replacement_fake_bot,
        replacement_fake_keyboard,
        create_new_user,
        create_referral,
        create_replenishment,
        start_event_handler,
        clean_db
    ):
    """Проверяем корректную работу handler_new_income_referral"""

    print("\n\nНачали проверять test_handler_new_income_referral\n\n")
    owner = create_new_user
    referral = create_referral
    replenishment = create_replenishment

    initial_balance = owner.balance
    initial_total_profit = owner.total_profit_from_referrals

    # --- создаём событие ---
    event = NewIncomeFromRef(
        replenishment_id=replenishment.replenishment_id,
        owner_id=owner.user_id,
        referral_id=referral.referral_id,
        amount=replenishment.origin_amount,
        total_sum_replenishment=replenishment.origin_amount,
    )

    q = event_queue  # зафиксировали ссылку один раз
    q.put_nowait(event)

    # ждём пока событие обработается
    await asyncio.sleep(0)
    await q.join()

    async with get_db() as session_db:
        # проверка пользователя (владельца реферала)
        user_result = await session_db.execute(
            select(Users).where(Users.user_id == owner.user_id)
        )
        updated_user = user_result.scalar_one()

        assert updated_user.balance > initial_balance, "Баланс не увеличился"
        assert updated_user.total_profit_from_referrals > initial_total_profit, "Суммарная прибыль от рефералов не обновилась"

        # проверка уровня в Referrals
        referral_result = await session_db.execute(
            select(Referrals).where(Referrals.referral_id == referral.referral_id)
        )
        updated_ref = referral_result.scalar_one()
        assert updated_ref.level >= 0, "Уровень реферала не обновился"

        # проверка IncomeFromReferrals
        income_result = await session_db.execute(
            select(IncomeFromReferrals)
            .where(IncomeFromReferrals.owner_user_id == owner.user_id)
        )
        income = income_result.scalars().first()
        assert income.amount > 0, "Запись о доходе от рефералов не создана"
        assert income.percentage_of_replenishment > 0, "Процент не сохранился"

        # проверка WalletTransaction
        wallet_result = await session_db.execute(
            select(WalletTransaction).where(WalletTransaction.user_id == owner.user_id)
        )
        wallet_trans = wallet_result.scalars().first()
        assert wallet_trans.type == "referral", "Неверный тип транзакции"
        assert wallet_trans.amount == income.amount, "Сумма транзакции не совпадает"
        assert wallet_trans.balance_after == updated_user.balance, "Баланс после транзакции некорректен"

        # проверка UserAuditLogs
        log_result = await session_db.execute(
            select(UserAuditLogs).where(UserAuditLogs.user_id == owner.user_id)
        )
        log = log_result.scalars().first()
        assert log.action_type == "profit from referral", "Неверный action_type в логах"

    # проверка Redis
    async with get_redis() as session_redis:
        redis_data = orjson.loads(await session_redis.get(f"user:{owner.user_id}"))

    await comparison_models(updated_user, redis_data)

