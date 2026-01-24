from typing import List, Tuple

from sqlalchemy import select, update, delete

from src.services.database.categories.actions.purchases.general.cancel import \
    update_purchaseRequests_and_balance_holder, return_files
from src.services.database.categories.models import ProductAccounts, SoldAccounts, Purchases, \
    AccountStorage
from src.services.database.categories.models.product_account import AccountServiceType
from src.services.database.core.database import get_db
from src.services.database.users.models import Users
from src.services.filesystem.account_actions import create_path_account
from src.services.redis.filling import filling_product_account_by_account_id, filling_sold_accounts_by_owner_id, \
    filling_sold_account_by_account_id, filling_user, filling_product_accounts_by_category_id
from src.utils.core_logger import get_logger


async def cancel_purchase_request_accounts(
    user_id: int,
    mapping: List[Tuple[str, str, str]],
    sold_account_ids: List[int],
    purchase_ids: List[int],
    total_amount: int,
    purchase_request_id: int,
    product_accounts: List[ProductAccounts],
    type_service_account: AccountServiceType,
):
    """
    получает mapping и пытается вернуть файлы и БД в исходное состояние

    :param mapping: список кортежей (orig_path, temp_path, final_path)
     - orig_path: изначальный путь (старое место)
     - temp_path: временный путь куда мы переместили файл до коммита
     - final_path: финальный путь (куда будет переименован после commit)
    :param sold_account_ids: список уже созданных sold_account (если есть) — удалим их и вернём product-строки
    :param purchase_ids: список purchases_accounts — удалим Purchases
    :param product_accounts: Список orm объектов с обязательно подгруженными account_storage
    """
    user = None
    logger = get_logger(__name__)

    await return_files(mapping, logger)

    # Удалить sold_accounts & purchases и вернуть AccountStorage.status = 'for_sale'
    async with get_db() as session:
        async with session.begin():
            # возвращаем баланс
            result_db = await session.execute(select(Users).where(Users.user_id == user_id))
            user: Users | None = result_db.scalars().one_or_none()
            if user is not None:
                new_balance = user.balance + total_amount
                await session.execute(
                    update(Users).where(Users.user_id == user_id).values(balance=new_balance)
                )

            # Удалим Purchases и SoldAccounts
            if purchase_ids:
                await session.execute(delete(Purchases).where(Purchases.purchase_id.in_(purchase_ids)))
            if sold_account_ids:
                await session.execute(delete(SoldAccounts).where(SoldAccounts.sold_account_id.in_(sold_account_ids)))

            try:
                account_storages_ids = [account.account_storage.account_storage_id for account in product_accounts]
                await session.execute(
                    update(AccountStorage)
                    .where(AccountStorage.account_storage_id.in_(account_storages_ids))
                    .values(
                        status="for_sale",
                        file_path=create_path_account(
                            status="for_sale",
                            type_account_service=type_service_account,
                            uuid=AccountStorage.storage_uuid
                        )
                    )
                )

                existing = await session.execute(
                    select(ProductAccounts.account_storage_id).where(
                        ProductAccounts.account_storage_id.in_(account_storages_ids))
                )
                existing_ids = set(existing.scalars().all())

                for account in product_accounts:
                    aid = account.account_storage.account_storage_id
                    if aid not in existing_ids:
                        session.add(ProductAccounts(
                            type_account_service=account.type_account_service,
                            category_id=account.category_id,
                            account_storage_id=aid
                        ))

            except Exception:
                logger.exception("Failed to restore account storage status")

            # Обновляем PurchaseRequests и BalanceHolder
            await update_purchaseRequests_and_balance_holder(
                session=session,
                logger=logger,
                purchase_request_id=purchase_request_id
            )

    if user:
        await filling_user(user)
    await filling_sold_accounts_by_owner_id(user_id)
    await filling_product_accounts_by_category_id()
    for sid in sold_account_ids:
        await filling_sold_account_by_account_id(sid)
    for pid in product_accounts:
        await filling_product_account_by_account_id(pid.account_id)

    logger.info("cancel_purchase_request_accounts finished for purchase %s", purchase_request_id)


