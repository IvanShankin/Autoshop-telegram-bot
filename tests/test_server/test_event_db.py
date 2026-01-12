import asyncio
from datetime import datetime
from typing import AsyncGenerator

import orjson
import pytest

from sqlalchemy import select, update
from sqlalchemy import MetaData, Table

from src.broker.producer import publish_event
from src.config import get_config
from src.services.database.discounts.models import Vouchers
from src.services.database.product_categories.events.schemas import NewPurchaseAccount, AccountsData
from src.services.database.system.actions import get_settings, update_settings
from src.services.database.users.models import Replenishments, Users, WalletTransaction, UserAuditLogs
from src.services.database.replenishments_event.schemas import ReplenishmentFailed, ReplenishmentCompleted, NewReplenishment
from src.services.database.core.database import get_db
from src.utils.i18n import get_text, n_get_text
from src.services.redis.core_redis import get_redis

from tests.helpers.helper_functions import comparison_models
from tests.helpers.monkeypatch_data import fake_bot
from tests.helpers.monkeypatch_event_db import processed_promo_code, processed_voucher, processed_referrals, processed_replenishment



class TestHandlerNewReplenishment:
    async def create_and_update_replenishment(
            self, user_id: int,
            type_payment_id: int,
            processed_replenishment: AsyncGenerator
    )->Replenishments:
        """
        Запустит событие на обработку нового пополнения и дождётся его выполнения
        :return возвращает созданный Replenishments
        """

        async with get_db() as session_db:
            new_replenishment = Replenishments(
                user_id = user_id,
                type_payment_id = type_payment_id,
                origin_amount = 100,
                amount = 105,
                status = 'processing'
            )
            session_db.add(new_replenishment)
            await session_db.commit()
            await session_db.refresh(new_replenishment)

            event = NewReplenishment(
                replenishment_id=new_replenishment.replenishment_id,
                user_id=new_replenishment.user_id,
                origin_amount=new_replenishment.origin_amount,
                amount=new_replenishment.amount
            )

            await publish_event(event.model_dump(), 'replenishment.new_replenishment')  # публикация события
            await asyncio.wait_for(processed_replenishment.wait(), timeout=5.0)  # ожидание завершения события

        return new_replenishment

    @pytest.mark.asyncio
    async def test_access(
            self,
            processed_replenishment,
            create_new_user,
            create_type_payment,
            clean_rabbit
        ):
        """Интеграционный тест"""
        user = await create_new_user()
        type_payment = await create_type_payment()

        # Исходные данные пользователя
        initial_balance = user.balance
        initial_total_sum = user.total_sum_replenishment
        user_id = user.user_id

        replenishment = await self.create_and_update_replenishment(
            user_id,
            type_payment.type_payment_id,
            processed_replenishment
        )

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

        # сообщение пользователю
        message_for_user = n_get_text(
            user.language,
            "replenishment",
            "Balance successfully replenished by {sum} ruble.\nThank you for choosing us!",
            "Balance successfully replenished by {sum} rubles.\nThank you for choosing us!",
            replenishment.amount
        ).format(sum=replenishment.amount)

        assert fake_bot.get_message(user.user_id, message_for_user)

    @pytest.mark.asyncio
    async def test_fail(
            self,
            processed_replenishment,
            get_engine,
            create_new_user,
            create_type_payment,
            clean_rabbit
    ):
        """
        Интеграционный тест:
        - При ошибке в handler_new_replenishment генерируется событие ReplenishmentFailed
        - Пользователь получает сообщение об ошибке
        - В лог уходит сообщение об ошибке
        """

        user = await create_new_user()
        type_payment = await create_type_payment()

        # Ломаем таблицу WalletTransaction, чтобы handler_new_replenishment упал
        async with get_engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Table(WalletTransaction.__table__, MetaData()).drop(sync_conn)
            )

        # перенастроим канал логов (иначе send_log ничего не отправит)
        await update_settings(channel_for_logging_id = 123456789)

        # создаём пополнение → переводим в processing → триггерим handler_new_replenishment
        new_replenishment = await self.create_and_update_replenishment(
            user.user_id,
            type_payment.type_payment_id,
            processed_replenishment
        )

        # проверяем, что ReplenishmentFailed отработал
        # сообщение пользователю
        message_for_user = n_get_text(
            user.language,
            'replenishment',
            "Balance successfully replenished by {sum} ruble.\nThank you for choosing us!",
            "Balance successfully replenished by {sum} rubles.\nThank you for choosing us!",
            new_replenishment.amount
        ).format(sum=new_replenishment.amount)

        assert fake_bot.get_message(user.user_id, message_for_user)

        # лог
        message_log = get_text(
            get_config().app.default_lang,
            'replenishment',
            "#Replenishment_error \n\nUser {username} Paid money, balance updated, but an error occurred inside the server. \n"
            "Replenishment ID: {replenishment_id}.\nError: {error} \n\nTime: {time}"
        ).format(
            username=f'@{user.username}',
            replenishment_id=new_replenishment.replenishment_id,
            error="",
            time=datetime.now().strftime(get_config().different.dt_format),
        )

        assert fake_bot.check_str_in_messages(message_log[:100])

    @pytest.mark.asyncio
    async def test_on_replenishment_completed(
            self,
            processed_replenishment,
            create_new_user,
            create_type_payment,
            clean_rabbit
    ):
        """
        Проверяет корректную работу on_replenishment_completed:
        - Пользователь получает сообщение об успешном пополнении
        - В лог уходит корректная запись
        """
        type_payment = await create_type_payment()
        user = await create_new_user()
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

        await publish_event(event.model_dump(), 'replenishment.completed')  # публикация события
        await asyncio.wait_for(processed_replenishment.wait(), timeout=5.0)  # ожидание завершения события

        # сообщение пользователю
        message_success = n_get_text(
            user.language,
            "replenishment",
            "Balance successfully replenished by {sum} ruble.\nThank you for choosing us!",
            "Balance successfully replenished by {sum} rubles.\nThank you for choosing us!",
            amount
        ).format(sum=amount)
        assert fake_bot.get_message(user.user_id, message_success)

        # лог
        message_log = n_get_text(
            user.language,
            "replenishment",
            "#Replenishment \n\nUser {username} successfully topped up the balance by {sum} ruble. \n"
            "Replenishment ID: {replenishment_id} \n\n"
            "Time: {time}",
            "#Replenishment \n\nUser {username} successfully topped up the balance by {sum} rubles. \n"
            "Replenishment ID: {replenishment_id} \n\n"
            "Time: {time}",
            amount
        ).format(
            username=user.username,
            sum=amount,
            replenishment_id=replenishment_id,
            time=datetime.now().strftime(get_config().different.dt_format)
        )

        assert fake_bot.check_str_in_messages(message_log[:100])

    @pytest.mark.asyncio
    async def test_on_replenishment_failed(
            self,
            processed_replenishment,
            create_new_user,
            create_type_payment,
            clean_rabbit
    ):
        """
        Проверяет корректную работу on_replenishment_failed:
        - Пользователь получает сообщение об ошибке
        - В лог уходит корректная запись
        """

        type_payment = await create_type_payment()
        user = await create_new_user()
        replenishment_id = 8888
        error_text = "test_error"

        event = ReplenishmentFailed(
            user_id=user.user_id,
            replenishment_id=replenishment_id,
            error_str=error_text,
            language=user.language,
            username=user.username
        )

        await publish_event(event.model_dump(), 'replenishment.failed')  # публикация события
        await asyncio.wait_for(processed_replenishment.wait(), timeout=5.0)  # ожидание завершения события

        # сообщение пользователю
        message_for_user = get_text(
            user.language,
            "replenishment",
            "An error occurred while replenishing!\nReplenishment ID: {replenishment_id} "
            "\n\nWe apologize for the inconvenience. \nPlease contact support."
        ).format(replenishment_id=replenishment_id)
        assert fake_bot.get_message(user.user_id, message_for_user)

        # лог
        message_log = get_text(
            user.language,
            "replenishment",
            "#Replenishment_error \n\nUser {username} Paid money, but the balance was not updated. \n"
            "Replenishment ID: {replenishment_id}. \nError: {error} \n\nTime: {time}"
        ).format(
            username=user.username,
            replenishment_id=replenishment_id,
            error=error_text,
            time=datetime.now().strftime(get_config().different.dt_format)
        )

        assert fake_bot.check_str_in_messages(message_log[:100])

class TestHandlerNewIncomeRef:
    @pytest.mark.asyncio
    async def test_handler_new_income_referral(
            self,
            processed_referrals,
            create_referral,
            create_replenishment,
            clean_rabbit
        ):
        """Проверяем корректную работу handler_new_income_referral"""
        from src.services.database.referrals.actions import get_referral_lvl
        from src.services.database.referrals.models import IncomeFromReferrals, Referrals

        _, owner, referral = await create_referral()
        replenishment = await create_replenishment(amount = 999999)

        initial_balance = owner.balance
        initial_total_profit = owner.total_profit_from_referrals

        # --- создаём событие ---
        event = ReplenishmentCompleted(
            user_id = referral.user_id,
            replenishment_id = replenishment.replenishment_id,
            amount = replenishment.amount,
            total_sum_replenishment = referral.total_sum_replenishment + replenishment.amount,
            error = False,
            error_str = '',
            language = 'ru',
            username = referral.username
        )

        await publish_event(event.model_dump(), 'referral.new_referral')  # публикация события
        await asyncio.wait_for(processed_referrals.wait(), timeout=5.0)  # ожидание завершения события

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

        # --- проверяем, что пользователю ушло сообщение ---
        percent = None
        ref_lvl = await get_referral_lvl()
        for lvl in ref_lvl:
            if updated_ref.level == lvl.level:
                percent = lvl.percent

        expected_message = get_text(
            owner.language,
            "referral_messages",
            "Your referral has replenished their balance and increased the level of the referral system.\n"
            "Referral level: {last_lvl} {current_lvl}\n"
            "You have earned: {amount}₽ ({percent}%)\n\n"
            "Funds have been credited to your balance in your personal account."
        ).format(last_lvl=1, current_lvl=updated_ref.level,  amount=replenishment.amount, percent=percent)

        assert fake_bot.get_message(owner.user_id, expected_message), "Сообщение о доходе от реферала не отправлено"

    @pytest.mark.asyncio
    async def test_on_referral_income_completed_no_level_up(self,):
        """Проверяет сообщение без повышения уровня (last_lvl == current_lvl)"""
        from src.services.database.referrals.events import on_referral_income_completed
        user_id = 101
        language = "ru"
        amount = 50
        last_lvl = 2
        current_lvl = 2
        percent = 10

        await on_referral_income_completed(user_id, language, amount, last_lvl, current_lvl, percent)

        message = get_text(
            language,
            "referral_messages",
            "Your referral has replenished the balance. \nReferral level: {level} \nYou have earned {amount}₽ ({percent}%)\n\n"
            "Funds have been credited to your balance in your personal account."
        ).format(level=current_lvl, amount=amount, percent=percent)

        assert fake_bot.check_str_in_messages(message[:100]), "Сообщение о пополнении без повышения уровня не отправлено"


    @pytest.mark.asyncio
    async def test_on_referral_income_completed_with_level_up(self,):
        """Проверяет сообщение с повышением уровня (last_lvl != current_lvl)"""
        from src.services.database.referrals.events import on_referral_income_completed
        user_id = 202
        language = "ru"
        amount = 100
        last_lvl = 1
        current_lvl = 2
        percent = 15

        await on_referral_income_completed(user_id, language, amount, last_lvl, current_lvl, percent)

        message = get_text(
            language,
            "referral_messages",
            "Your referral has replenished their balance and increased the level of the referral system.\n"
            "Referral level: {last_lvl} {current_lvl}\n"
            "You have earned: {amount}₽ ({percent}%)\n\n"
            "Funds have been credited to your balance in your personal account."
        ).format(last_lvl=last_lvl, current_lvl=current_lvl, amount=amount, percent=percent)

        assert fake_bot.check_str_in_messages(message[:100]), "Сообщение о пополнении с повышением уровня не отправлено"


    @pytest.mark.asyncio
    async def test_on_referral_income_failed(self,):
        """Проверяет, что on_referral_income_failed пишет лог об ошибке"""
        from src.services.database.referrals.events import on_referral_income_failed
        error_text = "Some referral error"
        await on_referral_income_failed(error_text)

        message_log = get_text(
            'ru',
            "referral_messages",
            "#Replenishment_error \n\n"
            "An error occurred while sending a message about replenishing funds to the referral owner. \n"
            "Error: {error}. \n\n"
            "Time: {time}"
        ).format(error=error_text, time=datetime.now().strftime(get_config().different.dt_format))

        assert fake_bot.check_str_in_messages(message_log[:100]), "Лог об ошибке рефералки не был отправлен"


@pytest.mark.asyncio
@pytest.mark.parametrize('should_become_inactive',[True, False])
async def test_handler_new_activate_promo_code(
    should_become_inactive,
    replacement_needed_modules,
    processed_promo_code,
    clean_db,
    create_promo_code,
    create_new_user,
    create_settings,
    clean_rabbit
):
    from src.services.database.discounts.events.schemas import NewActivatePromoCode
    from src.services.database.discounts.models import PromoCodes, ActivatedPromoCodes
    promo_code = await create_promo_code()
    old_promo = promo_code
    if should_become_inactive: # сделаем поромокод на одну активацию
        async with get_db() as session_db:
            await session_db.execute(
                update(PromoCodes)
                .where(PromoCodes.promo_code_id == promo_code.promo_code_id)
                .values(number_of_activations=1)
            )
            await session_db.commit()
            promo_code.number_of_activations = 1

    user = await create_new_user()
    settings = create_settings

    event = NewActivatePromoCode(
        promo_code_id = old_promo.promo_code_id,
        user_id = user.user_id
    )

    await publish_event(event.model_dump(), 'promo_code.activated') # публикация события
    await asyncio.wait_for(processed_promo_code.wait(), timeout=5.0) # ожидание завершения события

    async with get_db() as session_db:
        result = await session_db.execute(
            select(ActivatedPromoCodes)
            .where(
                (ActivatedPromoCodes.promo_code_id == old_promo.promo_code_id) &
                (ActivatedPromoCodes.user_id == user.user_id)
            )
        )
        activate = result.scalar_one_or_none()
        assert activate

        result = await session_db.execute(select(PromoCodes).where(PromoCodes.promo_code_id == promo_code.promo_code_id))
        promo = result.scalar_one_or_none()

        assert promo.activated_counter == old_promo.activated_counter + 1
        if should_become_inactive: # если промокод был на одну активацию, то должен стать невалидным
            assert promo.is_valid == False
        else:
            assert promo.is_valid == True

        async with get_redis() as session_redis:
            redis_result = await session_redis.get(f"promo_code:{old_promo.activation_code}")

            if should_become_inactive: # если промокод был на одну активацию, то должен удалиться с redis
                assert not redis_result
            else:
                assert redis_result

        message = get_text(
            'ru',
            "discount",
            "#Promocode_activation \nID promo_code '{promo_code_id}' \nCode '{code}' \nID user '{user_id}'"
            "\n\nSuccessfully activated. \nActivations remaining: {number_of_activations}"
        ).format(
            promo_code_id=old_promo.promo_code_id,
            code=old_promo.activation_code,
            user_id=user.user_id,
            number_of_activations=old_promo.number_of_activations - 1 # т.к. активировли один раз
        )
        assert fake_bot.get_message(settings.channel_for_logging_id, message)

        if should_become_inactive:
            message = get_text(
                'ru',
                "discount",
                "#Promo_code_expired \nID '{id}' \nCode '{code}'"
                "\n\nThe promo code has expired due to reaching the number of activations or time limit. It is no longer possible to activate it"
            ).format(id=old_promo.promo_code_id,code=old_promo.activation_code,)
            assert fake_bot.get_message(settings.channel_for_logging_id, message)


class TestHandlerNewActivatedVoucher:

    async def create_voucher_activation_event(
        self,
        user: Users,
        voucher: Vouchers,
        balance_before: int,
        balance_after: int
    ):
        """Создает событие активации ваучера"""
        from src.services.database.discounts.events import NewActivationVoucher

        return NewActivationVoucher(
            voucher_id=voucher.voucher_id,
            user_id=user.user_id,
            language=user.language,
            amount=voucher.amount,
            balance_before=balance_before,
            balance_after=balance_after
        )

    @pytest.mark.asyncio
    async def test_successful_voucher_activation(
        self,
        replacement_needed_modules,
        processed_voucher,
        create_new_user,
        create_voucher,
        clean_rabbit
    ):

        from src.services.database.users.actions import get_user
        """Тест успешной активации ваучера"""
        user = await create_new_user()
        voucher = await create_voucher()
        initial_balance = user.balance
        expected_balance = initial_balance + voucher.amount

        # Создаем событие активации
        event = await self.create_voucher_activation_event(
            user, voucher, initial_balance, expected_balance
        )

        await publish_event(event.model_dump(), 'voucher.activated')  # публикация события
        await asyncio.wait_for(processed_voucher.wait(), timeout=5.0)  # ожидание завершения события

        async with get_db() as session_db:
            # Проверяем обновление ваучера
            voucher_result = await session_db.execute(
                select(Vouchers).where(Vouchers.voucher_id == voucher.voucher_id)
            )
            updated_voucher = voucher_result.scalar_one()
            assert updated_voucher.activated_counter == voucher.activated_counter + 1

            # Проверяем транзакцию кошелька
            transaction_result = await session_db.execute(
                select(WalletTransaction)
                .where(WalletTransaction.user_id == user.user_id)
            )
            wallet_transaction = transaction_result.scalar_one()
            assert wallet_transaction.type == 'voucher'
            assert wallet_transaction.amount == voucher.amount
            assert wallet_transaction.balance_before == initial_balance
            assert wallet_transaction.balance_after == expected_balance

            # Проверяем лог аудита
            log_result = await session_db.execute(
                select(UserAuditLogs)
                .where(UserAuditLogs.user_id == user.user_id)
            )
            assert log_result.scalar_one()


        owner = await get_user(voucher.creator_id)
        message_for_user = get_text(
            owner.language,
            "discount",
            "Voucher with code '{code}' has been activated! \n\nRemaining number of voucher activations: {number_activations}"
        ).format(code=updated_voucher.activation_code, number_activations=updated_voucher.number_of_activations - updated_voucher.activated_counter)

        assert fake_bot.get_message(owner.user_id, message_for_user)

    @pytest.mark.asyncio
    async def test_voucher_activation_with_activation_limit(
            self,
            processed_voucher,
            create_new_user,
            create_voucher,
            clean_rabbit,
            replacement_fake_bot_fix
    ):
        """Тест активации ваучера с достижением лимита активаций"""
        user = await create_new_user()
        voucher = await create_voucher()

        # Устанавливаем лимит активаций в 1
        async with get_db() as session_db:
            db_voucher = await session_db.execute(
                update(Vouchers)
                .where(Vouchers.voucher_id == voucher.voucher_id)
                .values(number_of_activations=1)
                .returning(Vouchers)
            )
            voucher: Vouchers = db_voucher.scalar_one()
            await session_db.commit()

        activation_amount = voucher.amount
        initial_balance = user.balance
        expected_balance = initial_balance + activation_amount

        event = await self.create_voucher_activation_event(user, voucher, initial_balance, expected_balance)

        await publish_event(event.model_dump(), 'voucher.activated')  # публикация события
        await asyncio.wait_for(processed_voucher.wait(), timeout=10.0)  # ожидание завершения события

        async with get_db() as session_db:
            # Проверяем, что ваучер стал невалидным
            voucher_result = await session_db.execute(
                select(Vouchers).where(Vouchers.voucher_id == voucher.voucher_id)
            )
            updated_voucher = voucher_result.scalar_one()
            assert not updated_voucher.is_valid
            assert updated_voucher.activated_counter == 1

            # Проверяем удаление ваучера из Redis
            async with get_redis() as session_redis:
                redis_result = await session_redis.get(f"voucher:{voucher.activation_code}")
                assert not redis_result

        # Проверяем отправку сообщения об истечении ваучера
        expected_user_message = get_text(
            'ru',
            "discount",
            "Voucher has reached its activation limit \n\nID: {id} \nCode: {code} \n\n"
                "The voucher has expired due to the activation limit. It can no longer be activated"
        ).format(id=voucher.voucher_id, code=voucher.activation_code)

        assert fake_bot.get_message(voucher.creator_id, expected_user_message)

    @pytest.mark.asyncio
    async def test_voucher_activation_failure(
            self,
            processed_voucher,
            create_new_user,
            create_voucher,
            get_engine,
            clean_rabbit
    ):
        """Тест обработки ошибки при активации ваучера"""
        user = await create_new_user()
        voucher = await create_voucher()

        # Ломаем таблицу VoucherActivations чтобы вызвать ошибку
        async with get_engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Table(WalletTransaction.__table__, MetaData()).drop(sync_conn)
            )

        activation_amount = voucher.amount
        initial_balance = user.balance
        expected_balance = initial_balance + activation_amount

        event = await self.create_voucher_activation_event(
            user, voucher, initial_balance, expected_balance
        )

        # Настраиваем канал для логов
        await update_settings(channel_for_logging_id = 123456789)

        await publish_event(event.model_dump(), 'voucher.activated')  # публикация события
        await asyncio.wait_for(processed_voucher.wait(), timeout=5.0)  # ожидание завершения события

        # Проверяем отправку лога об ошибке
        expected_error_message = get_text(
            'ru',
            "discount",
            "Error_while_activating_voucher. \n\nVoucher ID '{id}' \nError: {error}"
        ).format(id=voucher.voucher_id, error="")

        assert fake_bot.check_str_in_messages(expected_error_message[:60])

    @pytest.mark.asyncio
    @pytest.mark.parametrize('is_created_admin', [True, False])
    async def test_send_set_not_valid_voucher(
            self,
            is_created_admin,
            create_new_user,
            create_voucher,
    ):
        """Тест отправки сообщений при истечении ваучера"""
        from src.services.database.discounts.utils.set_not_valid import send_set_not_valid_voucher

        user = await create_new_user()
        voucher = await create_voucher()

        # Устанавливаем флаг is_created_admin
        async with get_db() as session_db:
            voucher_db = await session_db.execute(
                update(Vouchers)
                .where(Vouchers.voucher_id == voucher.voucher_id)
                .values(is_created_admin=is_created_admin)
                .returning(Vouchers)
            )
            voucher: Vouchers = voucher_db.scalar_one()
            await session_db.commit()

        # Настраиваем канал для логов если ваучер создан админом
        if is_created_admin:
            settings = await get_settings()
            await update_settings(channel_for_logging_id=123456789)

        await send_set_not_valid_voucher(user.user_id, voucher, True, user.language)

        if is_created_admin:
            # Проверяем лог в канале
            expected_log_message = get_text(
            user.language,
            "discount",
                "#Voucher_expired \nID '{id}' \nCode '{code}'"
                "\n\nThe voucher has expired due to reaching the number of activations or time limit. It is no longer possible to activate it"
            ).format(id=voucher.voucher_id, code=voucher.activation_code)
            assert fake_bot.get_message(settings.channel_for_logging_id, expected_log_message)
        else:
            # Проверяем сообщение пользователю
            expected_user_message = get_text(
                user.language,
                "discount",
                "Voucher has reached its activation limit \n\nID: {id} \nCode: {code} \n\n"
                "The voucher has expired due to the activation limit. It can no longer be activated"
            ).format(id=voucher.voucher_id, code=voucher.activation_code)
            assert fake_bot.get_message(user.user_id, expected_user_message)

    @pytest.mark.asyncio
    async def test_send_failed(self,):
        """Тест отправки сообщения об ошибке"""
        from src.services.database.discounts.events import send_failed

        voucher_id = 999
        error_text = "Test error message"

        # Настраиваем канал для логов
        await update_settings(channel_for_logging_id=123456789)

        await send_failed(voucher_id, error_text)

        expected_error_message = get_text(
            'ru',
            "discount",
            "Error_while_activating_voucher. \n\nVoucher ID '{id}' \nError: {error}"
        ).format(id=voucher_id, error=error_text)

        assert fake_bot.check_str_in_messages(expected_error_message[:60])


@pytest.mark.asyncio
async def test_handler_new_purchase_creates_wallet_and_logs(
    replacement_needed_modules,
    create_new_user,
    create_sold_account,
    clean_db
):
    """
    Прямой вызов handler_new_purchase:
    - создаётся WalletTransaction
    - создаются UserAuditLogs (по каждому account_movement)
    - обновляется redis (sold_account и sold_accounts_by_owner_id)
    - отправляются логи (проверяется fake_bot)
    """

    from src.services.database.product_categories.events.even_handlers_acc import handler_new_purchase
    # подготовка данных
    user = await create_new_user()
    # создаём sold_account в БД и перевод для языка 'ru'
    _, sold_full = await create_sold_account(filling_redis=False, owner_id=user.user_id, language='ru')

    # параметры покупки (имитация того, что уже произошла основная транзакция и purchase_id = 777)
    account_movement = [
        AccountsData(
            id_account_storage=sold_full.account_storage.account_storage_id,
            id_new_sold_account=sold_full.sold_account_id,
            id_purchase_account=777,
            cost_price=10,
            purchase_price=100,
            net_profit=90
        )
    ]

    new_purchase = NewPurchaseAccount(
        user_id=user.user_id,
        category_id=1,
        amount_purchase=100,
        account_movement=account_movement,
        user_balance_before=1000,
        user_balance_after=900,
        accounts_left=3,
    )

    # вызов тестируемой функции
    await handler_new_purchase(new_purchase)

    # ---- проверки в БД ----
    async with get_db() as session_db:
        # WalletTransaction
        result = await session_db.execute(
            select(WalletTransaction).where(WalletTransaction.user_id == user.user_id)
        )
        wt = result.scalar_one_or_none()
        assert wt is not None, "WalletTransaction не создан"
        assert wt.type == 'purchase'
        assert wt.amount == new_purchase.amount_purchase * -1
        assert wt.balance_before == new_purchase.user_balance_before
        assert wt.balance_after == new_purchase.user_balance_after

        # UserAuditLogs (должна появиться запись для account_movement)
        result = await session_db.execute(
            select(UserAuditLogs).where(UserAuditLogs.user_id == user.user_id)
        )
        logs = result.scalars().all()
        assert len(logs) >= 1, "UserAuditLogs не созданы"
        # проверим одну запись на соответствие деталям
        found = False
        for l in logs:
            if l.action_type == "purchase_account" and l.details.get("id_new_sold_account") == sold_full.sold_account_id:
                found = True
                assert l.details["id_account_storage"] == sold_full.account_storage.account_storage_id
                assert l.details["id_purchase_account"] == 777
                assert l.details["profit"] == 90
                break
        assert found, "Лог покупки с нужными деталями не найден"

    # ---- проверка отправленных логов (send_log должен был использовать fake bot) ----
    # формируется текст в handler_new_purchase, проверим что хотя бы кусок текста попал в сообщения
    expected_substring = f"Аккаунт на продаже с id (StorageAccount) = {sold_full.account_storage.account_storage_id} продан!"
    assert fake_bot.check_str_in_messages(expected_substring) or fake_bot.check_str_in_messages(expected_substring[:30])


@pytest.mark.asyncio
async def test_account_purchase_event_handler_parses_and_calls_handler(
    replacement_needed_modules,
    create_new_user,
    create_sold_account,
    clean_db
):
    """
    Проверяем, что account_purchase_event_handler корректно парсит dict-ивент
    и вызывает handler_new_purchase (через этот wrapper вставится Pydantic->handler).
    """
    from src.services.database.product_categories.events.even_handlers_acc import account_purchase_event_handler
    user = await create_new_user()
    _, sold_full = await create_sold_account(filling_redis=False, owner_id=user.user_id, language='ru')

    account_movement = [
        AccountsData(
            id_account_storage=sold_full.account_storage.account_storage_id,
            id_new_sold_account=sold_full.sold_account_id,
            id_purchase_account=777,
            cost_price=10,
            purchase_price=100,
            net_profit=90
        ).model_dump()
    ]

    payload = NewPurchaseAccount(
        user_id=user.user_id,
        category_id=1,
        amount_purchase=100,
        account_movement=account_movement,
        user_balance_before=1000,
        user_balance_after=900,
        accounts_left=3,
    ).model_dump()

    event = {"event": "account.purchase", "payload": payload}

    # вызываем через event handler (имитируем приход события из брокера)
    await account_purchase_event_handler(event)

    # даём немного времени на асинхронные операции (send_log / redis)
    await asyncio.sleep(0.05)

    # проверим, что появились WalletTransaction и UserAuditLogs
    async with get_db() as session_db:
        result = await session_db.execute(select(WalletTransaction).where(WalletTransaction.user_id == user.user_id))
        wt = result.scalar_one_or_none()
        assert wt is not None and wt.type == 'purchase'

        result = await session_db.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == user.user_id))
        logs = result.scalars().all()
        assert len(logs) >= 1

    # проверка на отправленные логи
    expected_substring = f"Аккаунт на продаже с id (StorageAccount) = {sold_full.account_storage.account_storage_id} продан!"
    assert fake_bot.check_str_in_messages(expected_substring) or fake_bot.check_str_in_messages(expected_substring[:30])
