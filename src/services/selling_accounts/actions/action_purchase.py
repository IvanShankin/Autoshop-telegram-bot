import asyncio
from typing import Optional

import orjson
from sqlalchemy import select, update
from sqlalchemy.exc import InvalidRequestError, OperationalError, IntegrityError

from src.broker.producer import publish_event
from src.exceptions.service_exceptions import CategoryNotFound, NotEnoughAccounts, InvalidPromoCode
from src.exceptions.service_exceptions import NotEnoughMoney
from src.redis_dependencies.core_redis import get_redis
from src.redis_dependencies.filling_redis import filling_product_accounts_by_category_id, \
    filling_product_accounts_by_account_id
from src.services.database.database import get_db
from src.services.discounts.actions import get_valid_promo_code
from src.services.discounts.events import NewActivatePromoCode
from src.services.selling_accounts.actions import get_account_categories_by_category_id
from src.services.selling_accounts.events.schemas import NewPurchaseAccount, AccountsData
from src.services.selling_accounts.models import ProductAccounts, SoldAccounts, PurchasesAccounts, \
    SoldAccountsTranslation, AccountCategoryTranslation
from src.services.selling_accounts.models.schemas import PurchaseAccountSchem
from src.services.users.actions import get_user
from src.services.users.models import Users
from src.utils.core_logger import logger
from src.bot_actions.send_messages import send_log


# Настройки retry
_MAX_DB_RETRIES = 1  # кол-во повторов при грубой конкурентной ошибке (можно увеличить)
_RETRY_BACKOFF = 0.08  # секунды

async def purchase_accounts(
        user_id: int,
        category_id: int,
        quantity_accounts: int,
        code_promo_code: Optional[str]
) -> PurchaseAccountSchem:
    """
    Покупка N аккаунтов: атомарно удаляем ProductAccounts, создаём SoldAccounts и записи PurchasesAccounts.
    Применяем промокод к общей сумме покупки, распределяем итоговую сумму по аккаунтам.
    Публикуем события после успешного commit'а
    """
    # получаем категорию
    category = await get_account_categories_by_category_id(category_id)

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(AccountCategoryTranslation)
            .where(AccountCategoryTranslation.account_category_id == category_id)
        )
        translations_category: list[AccountCategoryTranslation] = result_db.scalars().all()

    if not category or not translations_category:
        raise CategoryNotFound("Данной категории больше не существует")

    # получаем промокод (если задан)
    promo_code = None
    if code_promo_code:
        promo_code = await get_valid_promo_code(code_promo_code)
        if not promo_code:
            raise InvalidPromoCode("Промокод невалидный")

    original_price_per = category.price_one_account
    original_total = original_price_per * quantity_accounts # оригинальная сумма которую должен заплатить пользователь

    # рассчитываем скидку
    discount_amount = 0
    if promo_code:
        if promo_code.amount is not None:
            discount_amount = min(promo_code.amount, original_total)
        elif promo_code.discount_percentage is not None:
            # явный int (рубли/копейки) — округляем вниз
            discount_amount = (original_total * promo_code.discount_percentage) // 100
        else:
            discount_amount = 0

    final_total = max(0, original_total - discount_amount) # конечная сумма которую должен заплатить пользователь

    # проверяем баланс пользователя (и снимаем)
    user = await get_user(user_id)
    if user.balance < final_total:
        raise NotEnoughMoney("Недостаточно средств для покупки аккаунтов", final_total - user.balance)

    # Попытка транзакции (с небольшим retry при конкурентных ошибках)
    attempt = 0
    while True:
        try:
            async with get_db() as session_db:
                async with session_db.begin():
                    # Захватываем нужные строки (row-level lock). ждём освобождения при необходимости
                    q = (
                        select(ProductAccounts)
                        .where(ProductAccounts.account_category_id == category_id)
                        .order_by(ProductAccounts.created_at.desc())
                        .with_for_update()
                        .limit(quantity_accounts)
                    )

                    result_db = await session_db.execute(q)
                    product_accounts: list[ProductAccounts] = result_db.scalars().all()

                    if len(product_accounts) < quantity_accounts:
                        raise NotEnoughAccounts("У данной категории недостаточно аккаунтов")

                    balance_before = user.balance
                    balance_after = user.balance - final_total

                    # отнимаем у пользователя деньги
                    result_db = await session_db.execute(
                        update(Users)
                        .where(Users.user_id == user_id)
                        .values(balance=user.balance - final_total)
                        .returning(Users)
                    )
                    user = result_db.scalar_one_or_none()

                    # Удаляем product_accounts (они будут удалены в рамках транзакции)
                    for acc in product_accounts:
                        await session_db.delete(acc)


                    account_movement: list[AccountsData] = [] # для отправки в событие
                    sold_accounts: list[SoldAccounts] = []

                    # Создаём sold_accounts (правильно указываем type_account_service_id)
                    for acc in product_accounts:
                        sold_account = SoldAccounts(
                            owner_id=user_id,
                            type_account_service_id=acc.type_account_service_id,  # исправлено
                            hash_login=acc.hash_login,
                            hash_password=acc.hash_password
                        )
                        session_db.add(sold_account)
                        sold_accounts.append(sold_account)

                    # Flush чтобы получить sold_account_id
                    await session_db.flush()

                    # добавляем перевод
                    for account in sold_accounts:
                        for translation in translations_category:
                            new_translation = SoldAccountsTranslation(
                                sold_account_id=account.sold_account_id,
                                lang = translation.lang,
                                name = translation.name,
                                description = translation.description
                            )
                            session_db.add(new_translation)

                    # Распределяем итоговую сумму (final_total) по аккаунтам равномерно,
                    # чтобы сумма purchase_price_i = final_total (целые значения)
                    base_price = final_total // quantity_accounts
                    remainder = final_total % quantity_accounts

                    cost_price_per = category.cost_price_one_account or 0
                    original_price_per_unit = original_price_per

                    purchases_rows: list[PurchasesAccounts] = []
                    for idx, sold in enumerate(sold_accounts):
                        purchase_price = base_price + (1 if idx < remainder else 0)
                        net_profit = purchase_price - cost_price_per

                        purchase_row = PurchasesAccounts(
                            user_id=user_id,
                            sold_account_id=sold.sold_account_id,
                            promo_code_id=promo_code.promo_code_id if promo_code else None,
                            original_price=original_price_per_unit,
                            purchase_price=purchase_price,
                            cost_price=cost_price_per,
                            net_profit=net_profit,
                        )
                        session_db.add(purchase_row)
                        purchases_rows.append(purchase_row)

                    await session_db.flush()

                    # формируем account_movement
                    account_movement = [
                        AccountsData(
                            id_old_product_account=acc.account_id,
                            id_new_sold_account=sold.sold_account_id,
                            id_purchase_account=purchase.purchase_id,
                            cost_price=purchase.cost_price,
                            purchase_price=purchase.purchase_price,
                            net_profit=purchase.net_profit
                        )
                        for acc, sold, purchase in zip(product_accounts, sold_accounts, purchases_rows)
                    ]

                    # Все изменения будут закоммичены по выходу из session_db.begin()

            # если дошли сюда — транзакция успешно закоммичена
            break

        except (OperationalError, InvalidRequestError, IntegrityError) as e:
            # Конкурентные / операционные ошибки — можно повторить один раз
            attempt += 1
            logger.warning("DB concurrency/operational error during purchase_accounts: %s (attempt %d)", str(e), attempt)
            if attempt > _MAX_DB_RETRIES:
                # откатываемся и пробрасываем
                logger.error("Exceeded retries for purchase_accounts, error: %s", str(e))
                await send_log(f"#Ошибка_при_покупке_аккунтов 1. \n\nОшибка: {str(e)}")
                raise
            # короткая пауза перед повтором
            await asyncio.sleep(_RETRY_BACKOFF)
            # повторяем цикл
            continue

        except Exception as e:
            # Логируем, пробрасываем
            logger.exception("Ошибка в БД при приобретении аккаунтов: %s", str(e))
            # неявный rollback произойдёт при выходе из контекста сессии
            await send_log(f"#Ошибка_при_покупке_аккунтов 2. \n\nОшибка: {str(e)}")
            raise

    # обновление redis
    async with get_redis() as session_redis:
        await session_redis.set(f'user:{user_id}', orjson.dumps(user.to_dict()))

    # обновление аккаунтов на продаже
    await filling_product_accounts_by_category_id()
    await filling_product_accounts_by_account_id()

    # После успешного commit: сформируем возвращаемую структуру и опубликуем события
    ids_deleted_product_account = [account.account_id for account in product_accounts]
    ids_new_sold_account = [account.sold_account_id for account in sold_accounts]

    data_returning = PurchaseAccountSchem(
        ids_deleted_product_account=ids_deleted_product_account,
        ids_new_sold_account=ids_new_sold_account
    )

    # Публикуем событие об активации промокода (если был)
    if promo_code:
        event = NewActivatePromoCode(
            promo_code_id=promo_code.promo_code_id,
            user_id=user_id
        )
        await publish_event(event.model_dump(), 'promo_code.activated')

    # Публикуем событие о покупке
    new_purchase = NewPurchaseAccount(
        user_id = user_id,
        category_id = category_id,
        quantity = quantity_accounts,
        amount_purchase = final_total,
        account_movement = account_movement,
        languages = [translation.lang for translation in translations_category],
        promo_code_id = promo_code.promo_code_id if promo_code else None,
        user_balance_before = balance_before,
        user_balance_after = balance_after,
    )
    await publish_event(new_purchase.model_dump(), 'account.purchase')

    return data_returning