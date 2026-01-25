import shutil
from pathlib import Path
from typing import List, Tuple

from sqlalchemy import update, delete

from src.bot_actions.messages import send_log
from src.broker.producer import publish_event
from src.config import get_config
from src.services.database.categories.actions.products.accounts.actions_get import get_product_account_by_category_id
from src.services.database.categories.actions.purchases.accounts.cancel import cancel_purchase_request_accounts
from src.services.database.categories.events.schemas import NewPurchaseAccount, AccountsData
from src.services.database.categories.models import ProductAccounts, SoldAccounts, Purchases, \
    SoldAccountsTranslation, AccountStorage
from src.services.database.categories.models import PurchaseRequests
from src.services.database.categories.models import StartPurchaseAccount
from src.services.database.categories.models.main_category_and_product import ProductType
from src.services.database.core.database import get_db
from src.services.database.discounts.events import NewActivatePromoCode
from src.services.database.users.models.models_users import BalanceHolder
from src.services.filesystem.account_actions import create_path_account, rename_file
from src.services.filesystem.actions import move_file
from src.services.redis.filling import filling_product_account_by_account_id, filling_sold_accounts_by_owner_id, \
    filling_sold_account_by_account_id, filling_all_keys_category
from src.utils.core_logger import get_logger


async def finalize_purchase_accounts(user_id: int, data: StartPurchaseAccount):
    """
    Безопасно переносит файлы (в temp), создаёт DB записи в транзакции,
    затем финализирует перемещение temp->final. При ошибке — вызывает cancel_purchase_request_accounts.
    :return: Успех покупки
    """
    mapping: List[Tuple[str, str, str]] = []  #  (orig, temp, final)
    sold_account_ids: List[int] = []
    purchase_ids: List[int] = []
    account_movement: list[AccountsData] = []

    logger = get_logger(__name__)

    try:
        # Подготовим перемещения в temp (вне транзакции) — НЕ изменяем DB
        for account in data.product_accounts:
            orig = str(Path(get_config().paths.accounts_dir) / account.account_storage.file_path) # полный путь
            final = create_path_account(
                status="bought",
                type_account_service=data.type_service_account,
                uuid=account.account_storage.storage_uuid
            )
            temp = final + ".part"  # временный файл рядом с финальным

            moved = await move_file(orig, temp)
            if not moved:
                # если не удалось найти/переместить — удаляем account из БД (или помечаем), лог и cancel
                text = f"#Внимание \n\nАккаунт не найден/не удалось переместить: {orig}"
                await send_log(text)
                logger.exception(text)
                # сразу откатываем — возвращаем то что успели переместить
                await cancel_purchase_request_accounts(
                    user_id=user_id,
                    mapping=mapping,
                    sold_account_ids=sold_account_ids,
                    purchase_ids=purchase_ids,
                    total_amount=data.total_amount,
                    purchase_request_id=data.purchase_request_id,
                    product_accounts=data.product_accounts,
                    type_service_account=data.type_service_account
                )
                return False

            # Удаление директории где хранится аккаунт (uui). Директория уже будет пустой
            shutil.rmtree(str(Path(orig).parent))

            mapping.append((orig, temp, final))

        # Создаём DB-записи в одной транзакции
        async with get_db() as session:
            async with session.begin():
                # Перед созданием SoldAccounts — удаляем ProductAccounts записей в DB
                for account in data.product_accounts:
                    # удалим ProductAccounts
                    await session.execute(
                        delete(ProductAccounts).where(ProductAccounts.account_id == account.account_id)
                    )

                    new_sold = SoldAccounts(
                        owner_id=user_id,
                        account_storage_id=account.account_storage.account_storage_id,
                        type_account_service=data.type_service_account
                    )
                    session.add(new_sold)
                    await session.flush()
                    sold_account_ids.append(new_sold.sold_account_id)

                    # translations
                    for translate in data.translations_category:
                        session.add(SoldAccountsTranslation(
                            sold_account_id=new_sold.sold_account_id,
                            lang=translate.lang,
                            name=translate.name,
                            description=translate.description
                        ))

                    # purchases row
                    new_purchase = Purchases(
                        user_id=user_id,
                        account_storage_id=account.account_storage.account_storage_id,
                        product_type=ProductType.ACCOUNT,
                        original_price=data.original_price_one,
                        purchase_price=data.purchase_price_one,
                        cost_price=data.cost_price_one,
                        net_profit=data.purchase_price_one - data.cost_price_one
                    )
                    session.add(new_purchase)
                    await session.flush()
                    purchase_ids.append(new_purchase.purchase_id)

                    # Обновляем AccountStorage.status = 'bought' через update (на всякий случай)
                    await session.execute(
                        update(AccountStorage)
                        .where(AccountStorage.account_storage_id == account.account_storage.account_storage_id)
                        .values(
                            status='bought',
                            file_path=create_path_account(
                                status="bought",
                                type_account_service=data.type_service_account,
                                uuid=account.account_storage.storage_uuid
                            )
                        )
                    )
                    account_movement.append(AccountsData(
                        account_storage_id = account.account_storage.account_storage_id,
                        new_sold_account_id = new_sold.sold_account_id,
                        purchase_id = new_purchase.purchase_id,
                        cost_price = new_purchase.cost_price,
                        purchase_price = new_purchase.purchase_price,
                        net_profit = new_purchase.net_profit
                    ))

                # помечаем PurchaseRequests и BalanceHolder
                await session.execute(
                    update(PurchaseRequests)
                    .where(PurchaseRequests.purchase_request_id == data.purchase_request_id)
                    .values(status='completed')
                )
                await session.execute(
                    update(BalanceHolder)
                    .where(BalanceHolder.purchase_request_id == data.purchase_request_id)
                    .values(status='used')
                )
            # конец транзакции — commit произойдёт здесь

        #  После успешного commit — переименовываем temp -> final
        rename_fail = False
        for orig, temp, final in mapping:
            ok = await rename_file(temp, final)
            if not ok:
                logger.exception("Failed to rename temp %s -> %s", temp, final)
                rename_fail = True
                break

        if rename_fail:
            # Если переименование файлов не удалось — сильно редкий случай.
            # Попробуем откатить DB изменения и вернуть файлы обратно
            await cancel_purchase_request_accounts(
                user_id=user_id,
                mapping=mapping,
                sold_account_ids=sold_account_ids,
                purchase_ids=purchase_ids,
                total_amount=data.total_amount,
                purchase_request_id=data.purchase_request_id,
                product_accounts=data.product_accounts,
                type_service_account=data.type_service_account
            )
            return False

        # обновление redis
        await filling_sold_accounts_by_owner_id(user_id)
        for sid in sold_account_ids:
            await filling_sold_account_by_account_id(sid)
        for pid in data.product_accounts:
            await filling_product_account_by_account_id(pid.account_id)

        await filling_all_keys_category(data.category_id)

        # Публикуем событие об активации промокода (если был)
        if data.promo_code_id:
            event = NewActivatePromoCode(
                promo_code_id=data.promo_code_id,
                user_id=user_id
            )
            await publish_event(event.model_dump(), 'promo_code.activated')

        product_accounts = await get_product_account_by_category_id(data.category_id)
        new_purchase = NewPurchaseAccount(
            user_id=user_id,
            category_id=data.category_id,
            amount_purchase=data.total_amount,
            account_movement=account_movement,
            user_balance_before=data.user_balance_before,
            user_balance_after=data.user_balance_after,
            product_left=len(product_accounts)
        )
        await publish_event(new_purchase.model_dump(), 'purchase.account')

        return True

    except Exception as e:
        logger.exception("Error in finalize_purchase: %s", e)
        await send_log(f"#Ошибка finalise_purchase: {e}")

        await cancel_purchase_request_accounts(
            user_id=user_id,
            mapping=mapping,
            sold_account_ids=sold_account_ids,
            purchase_ids=purchase_ids,
            total_amount=data.total_amount,
            purchase_request_id=data.purchase_request_id,
            product_accounts=data.product_accounts,
            type_service_account=data.type_service_account
        )
        return False

