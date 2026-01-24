from typing import Optional

from src.bot_actions.messages import send_log
from src.services.database.categories.actions.purchases.accounts.cancel import cancel_purchase_request_accounts
from src.services.database.categories.actions.purchases.accounts.finalize import finalize_purchase_accounts
from src.services.database.categories.actions.purchases.accounts.start import start_purchase_account
from src.services.database.categories.actions.purchases.accounts.verify import verify_reserved_accounts
from src.services.database.categories.actions.purchases.universal.cancel import cancel_purchase_universal_different, \
    cancel_purchase_universal_one
from src.services.database.categories.actions.purchases.universal.finalize import finalize_purchase_universal_different, \
    finalize_purchase_universal_one
from src.services.database.categories.actions.purchases.universal.start import start_purchase_universal
from src.services.database.categories.actions.purchases.universal.verify import verify_reserved_universal_different, \
    verify_reserved_universal_one
from src.services.database.categories.models.main_category_and_product import ProductType
from src.services.database.categories.models.shemas.purshanse_schem import StartPurchaseUniversal, \
    StartPurchaseUniversalOne
from src.services.redis.filling import filling_all_keys_category
from src.utils.core_logger import get_logger


async def purchase(
    user_id: int,
    category_id: int,
    quantity_products: int,
    promo_code_id: Optional[int],
    product_type: ProductType,
    language: str,
) -> bool:
    if product_type == ProductType.ACCOUNT:
        return await purchase_accounts(user_id, category_id, quantity_products, promo_code_id)
    elif product_type == ProductType.UNIVERSAL:
        return await purchase_universal(user_id, category_id, quantity_products, language, promo_code_id)

    return False


async def purchase_accounts(
    user_id: int,
    category_id: int,
    quantity_accounts: int,
    promo_code_id: Optional[int] = None,
) -> bool:
    """
    Произведёт покупку необходимых аккаунтов, переместив файлы для входа в аккаунт в необходимую директорию.
    Произведёт все необходимые действия с БД.

    Пользователю ничего не отошлёт!

    :return: Успешность процесса
    :except CategoryNotFound: Если категория не найдена
    :except NotEnoughMoney: Если у пользователя недостаточно средств
    :except NotEnoughAccounts: Если у категории недостаточно аккаунтов
    """
    result = False
    data = await start_purchase_account(user_id, category_id, quantity_accounts, promo_code_id)
    valid_list = await verify_reserved_accounts(data.product_accounts, data.type_service_account, data.purchase_request_id)
    if valid_list is False:
        await cancel_purchase_request_accounts(
            user_id = user_id,
            mapping = [],
            sold_account_ids = [],
            purchase_ids = [],
            total_amount = data.total_amount,
            purchase_request_id = data.purchase_request_id,
            product_accounts = [],
            type_service_account=data.type_service_account
        )
        text = (
            "#Недостаточно_аккаунтов \n"
            "Пользователь пытался купить аккаунты, но ему не нашлось необходимое количество аккаунтов"
        )
        await send_log(text)

        logger = get_logger(__name__)
        logger.warning(text)

        result = False
    else:
        data.product_accounts = valid_list      # обновляем data.product_accounts на валидные
        result = await finalize_purchase_accounts(user_id, data)

    # обновляем redis
    await filling_all_keys_category(category_id=category_id)
    return result


async def purchase_universal(
    user_id: int,
    category_id: int,
    quantity_products: int,
    language: str,
    promo_code_id: Optional[int] = None,
) -> bool:
    result = False
    data = await start_purchase_universal(user_id, category_id, quantity_products, promo_code_id, language)

    if isinstance(data, StartPurchaseUniversal):
        full_products = await verify_reserved_universal_different(data.full_reserved_products, data.purchase_request_id)
        if full_products is False:
            await cancel_purchase_universal_different(
                user_id=user_id,
                mapping=[],
                sold_universal_ids=[],
                purchase_ids=[],
                total_amount=data.total_amount,
                purchase_request_id=data.purchase_request_id,
                product_universal=data.full_reserved_products
            )
            result = False
        else:
            result = await finalize_purchase_universal_different(
                user_id=user_id,
                data=data
            )
    elif isinstance(data, StartPurchaseUniversalOne):
        valid = await verify_reserved_universal_one(data.full_product)
        if valid is False:
            await cancel_purchase_universal_one(
                user_id=user_id,
                paths_created_storage=[],
                sold_universal_ids=[],
                storage_universal_ids=[],
                purchase_ids=[],
                total_amount=data.total_amount,
                purchase_request_id=data.purchase_request_id,
                product_universal=data.full_product
            )
            result = False
        else:
            result = await finalize_purchase_universal_one(
                user_id=user_id,
                data=data
            )

    await filling_all_keys_category(category_id=category_id)
    return result