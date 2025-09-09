import asyncio
from datetime import datetime

import orjson
import pytest
import pytest_asyncio
from sqlalchemy import select

from src.config import DT_FORMAT_FOR_LOGS
from src.database.action_main_models import get_user
from src.database.models_main import Replenishments, Users, WalletTransaction, UserAuditLogs
from src.database.database import get_db
from src.database.events.core_event import event_queue
from src.i18n import get_i18n
from src.modules.referrals.database.models_ref import IncomeFromReferrals, Referrals
from src.redis_dependencies.core_redis import get_redis
from src.services.replenishments.schemas import ReplenishmentFailed, ReplenishmentCompleted
from tests.fixtures.helper_fixture import create_new_user, create_type_payment, create_referral, create_replenishment
from tests.fixtures.monkeypatch_data import replacement_fake_bot, replacement_fake_keyboard, fake_bot, replacement_exception_aiogram
from tests.fixtures.helper_functions import comparison_models


@pytest_asyncio.fixture()
async def start_event_handler():
    # данный импорт обязательно тут, ибо aiogram запустит свой even_loop который не даст работать тесту в режиме отладки
    from src.database.events.triggers_processing import run_triggers_processing

    task = asyncio.create_task(run_triggers_processing())
    try:
        yield
    finally:
        await event_queue.join()  # дождались всех событий
        event_queue.put_nowait(None)  # закрываем dispatcher
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
            replacement_exception_aiogram,
            create_new_user,
            create_type_payment,
            start_event_handler
        ):
        """Интеграционный тест"""
        # Исходные данные пользователя
        initial_balance = create_new_user.balance
        initial_total_sum = create_new_user.total_sum_replenishment
        user_id = create_new_user.user_id

        replenishment =  await self.create_and_update_replenishment(user_id, create_type_payment['type_payment_id'])

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

        # проверяем, что ReplenishmentFailed отработал
        i18n = get_i18n(create_new_user.language, "replenishment_dom")

        # сообщение пользователю
        message_for_user = i18n.ngettext(
            "Balance successfully replenished by {sum} ruble.\nThank you for choosing us!",
            "Balance successfully replenished by {sum} rubles.\nThank you for choosing us!",
            replenishment.amount
        ).format(sum=replenishment.amount)

        assert fake_bot.get_message(create_new_user.user_id, message_for_user)

    @pytest.mark.asyncio
    async def test_fail(
            self,
            replacement_fake_bot,
            replacement_fake_keyboard,
            replacement_exception_aiogram,
            create_new_user,
            create_type_payment,
            start_event_handler,
    ):
        """
        Интеграционный тест:
        - При ошибке в handler_new_replenishment генерируется событие ReplenishmentFailed
        - Пользователь получает сообщение об ошибке
        - В лог уходит сообщение об ошибке
        """

        from src.database.action_main_models import get_settings, update_settings
        from src.database.database import engine
        from src.database.models_main import WalletTransaction
        from sqlalchemy import MetaData, Table

        user = create_new_user

        # Ломаем таблицу WalletTransaction, чтобы handler_new_replenishment упал
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Table(WalletTransaction.__table__, MetaData()).drop(sync_conn)
            )

        # создаём пополнение → переводим в processing → триггерим handler_new_replenishment
        new_replenishment = await self.create_and_update_replenishment(
            user.user_id, create_type_payment["type_payment_id"]
        )

        # перенастроим канал логов (иначе send_log ничего не отправит)
        settings = await get_settings()
        settings.channel_for_logging_id = 123456789
        await update_settings(settings)

        # ждём обработки события
        q = event_queue
        await asyncio.sleep(0)  # передать управление
        await q.join()

        # проверяем, что ReplenishmentFailed отработал
        i18n = get_i18n(user.language, "replenishment_dom")

        # сообщение пользователю
        message_for_user = i18n.ngettext(
            "Balance successfully replenished by {sum} ruble.\nThank you for choosing us!",
            "Balance successfully replenished by {sum} rubles.\nThank you for choosing us!",
            new_replenishment.amount
        ).format(sum=new_replenishment.amount)

        assert fake_bot.get_message(user.user_id, message_for_user)

        # лог
        message_log = i18n.gettext(
            "#Replenishment_error \n\nUser @{username} Paid money, balance updated, but an error occurred inside the server. \n"
            "Replenishment ID: {replenishment_id}.\nError: {error} \n\nTime: {time}"
        ).format(
            username=user.username,
            replenishment_id=new_replenishment.replenishment_id,
            error="",
            time=datetime.now().strftime(DT_FORMAT_FOR_LOGS),
        )

        assert fake_bot.check_str_in_messages(message_log[:100])

    @pytest.mark.asyncio
    async def test_on_replenishment_completed(
            self,
            replacement_fake_bot,
            replacement_fake_keyboard,
            replacement_exception_aiogram,
            create_new_user,
            create_type_payment,
            start_event_handler
    ):
        """
        Проверяет корректную работу on_replenishment_completed:
        - Пользователь получает сообщение об успешном пополнении
        - В лог уходит корректная запись
        """

        user = create_new_user
        amount = 150
        replenishment_id = 9999

        event = ReplenishmentCompleted(
            user_id=user.user_id,
            replenishment_id=replenishment_id,
            amount=amount,
            total_sum_replenishment=user.total_sum_replenishment + amount,
            error=False,
            error_str=None,
            language=user.language,
            username=user.username
        )

        from src.services.replenishments.event_handlers_replenishments  import on_replenishment_completed
        await on_replenishment_completed(event)

        i18n = get_i18n(user.language, "replenishment_dom")

        # сообщение пользователю
        message_success = i18n.ngettext(
            "Balance successfully replenished by {sum} ruble.\nThank you for choosing us!",
            "Balance successfully replenished by {sum} rubles.\nThank you for choosing us!",
            amount
        ).format(sum=amount)
        assert fake_bot.get_message(user.user_id, message_success)

        # лог
        message_log = i18n.ngettext(
            "#Replenishment \n\nUser @{username} successfully topped up the balance by {sum} ruble. \n"
            "Replenishment ID: {replenishment_id} \n\n"
            "Time: {time}",
            "#Replenishment \n\nUser @{username} successfully topped up the balance by {sum} rubles. \n"
            "Replenishment ID: {replenishment_id}  \n\n"
            "Time: {time}",
            amount
        ).format(
            username=user.username,
            sum=amount,
            replenishment_id=replenishment_id,
            time=datetime.now().strftime(DT_FORMAT_FOR_LOGS)
        )

        assert fake_bot.check_str_in_messages(message_log[:100])

    @pytest.mark.asyncio
    async def test_on_replenishment_failed(
            self,
            replacement_fake_bot,
            replacement_fake_keyboard,
            replacement_exception_aiogram,
            create_new_user,
            create_type_payment,
            start_event_handler
    ):
        """
        Проверяет корректную работу on_replenishment_failed:
        - Пользователь получает сообщение об ошибке
        - В лог уходит корректная запись
        """

        user = create_new_user
        replenishment_id = 8888
        error_text = "test_error"

        event = ReplenishmentFailed(
            user_id=user.user_id,
            replenishment_id=replenishment_id,
            error_str=error_text,
            language=user.language,
            username=user.username
        )

        from src.services.replenishments.event_handlers_replenishments import on_replenishment_failed
        await on_replenishment_failed(event)

        i18n = get_i18n(user.language, "replenishment_dom")

        # сообщение пользователю
        message_for_user = i18n.gettext(
            "An error occurred while replenishing!\nReplenishment ID: {replenishment_id} "
            "\n\nWe apologize for the inconvenience. \nPlease contact support."
        ).format(replenishment_id=replenishment_id)
        assert fake_bot.get_message(user.user_id, message_for_user)

        # лог
        message_log = i18n.gettext(
            "#Replenishment_error \n\nUser @{username} Paid money, but the balance was not updated. \n"
            "Replenishment ID: {replenishment_id}. \nError: {error} \n\nTime: {time}"
        ).format(
            username=user.username,
            replenishment_id=replenishment_id,
            error=error_text,
            time=datetime.now().strftime(DT_FORMAT_FOR_LOGS)
        )

        assert fake_bot.check_str_in_messages(message_log[:100])

@pytest.mark.asyncio
async def test_handler_new_income_referral(
        replacement_fake_bot,
        replacement_fake_keyboard,
        replacement_exception_aiogram,
        create_new_user,
        create_referral,
        create_replenishment,
        start_event_handler,
        clean_db
    ):
    """Проверяем корректную работу handler_new_income_referral"""
    owner, referral = create_referral

    initial_balance = owner.balance
    initial_total_profit = owner.total_profit_from_referrals

    # --- создаём событие ---
    event = ReplenishmentCompleted(
        user_id = referral.user_id,
        replenishment_id = create_replenishment.replenishment_id,
        amount = create_replenishment.amount,
        total_sum_replenishment = referral.total_sum_replenishment,
        error = False,
        error_str = '',
        language = 'ru',
        username = referral.username
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
            select(Referrals).where(Referrals.referral_id == referral.user_id)
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

