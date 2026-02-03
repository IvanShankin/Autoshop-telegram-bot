from typing import List

from sqlalchemy import select
from sqlalchemy.sql.expression import distinct

from src.services.database.categories.models import ProductAccounts, SoldAccounts
from src.services.database.core.database import get_db
from src.services.database.system.models import TypePayments
from src.services.database.system.models import UiImages
from src.services.database.users.models import Users
from src.services.redis.filling.filling_categories import filling_all_keys_category
from src.services.redis.filling.filling_other import filling_types_payments_by_id, filling_ui_image, \
    filling_voucher_by_user_id, filling_settings, filling_referral_levels, filling_all_types_payments, filling_users, \
    filling_admins, filling_banned_accounts, filling_promo_code, filling_vouchers
from src.services.redis.filling.filling_accounts import filling_product_account_by_account_id, \
    filling_sold_accounts_by_owner_id, filling_sold_account_by_account_id, filling_product_accounts_by_category_id
from src.services.redis.filling.helpers_func import _delete_keys_by_pattern
from src.utils.core_logger import get_logger


async def filling_all_redis():
    """Заполняет redis необходимыми данными. Использовать только после заполнения БД"""
    async with get_db() as session_db:
        result_db = await session_db.execute(select(TypePayments.type_payment_id))
        types_payments_ids: List[int] = result_db.scalars().all()
        for type_id in types_payments_ids:
            await filling_types_payments_by_id(type_id)

        result_db = await session_db.execute(select(UiImages))
        ui_images: List[UiImages] = result_db.scalars().all()
        for ui_image in ui_images:
            await filling_ui_image(ui_image.key)

        result_db = await session_db.execute(select(Users.user_id))
        users_ids: List[int] = result_db.scalars().all()
        for user_id in users_ids:
            await filling_voucher_by_user_id(user_id)

        result_db = await session_db.execute(select(ProductAccounts.account_id))
        product_accounts_ids: List[int] = result_db.scalars().all()
        for product_account_id in product_accounts_ids:
            await filling_product_account_by_account_id(product_account_id)

        result_db = await session_db.execute(select(distinct(SoldAccounts.owner_id)))
        union_sold_accounts_owner_ids: List[int] = result_db.scalars().all()
        for owner_id in union_sold_accounts_owner_ids:
            await filling_sold_accounts_by_owner_id(owner_id)

        result_db = await session_db.execute(select(SoldAccounts.sold_account_id))
        sold_accounts_ids: List[int] = result_db.scalars().all()
        for account_id in sold_accounts_ids:
            await filling_sold_account_by_account_id(account_id)

    await _delete_keys_by_pattern(f"category:*")  # обязательно т.к. могут хранится категории которых уже нет

    await filling_settings()
    await filling_referral_levels()
    await filling_all_types_payments()
    await filling_users()
    await filling_admins()
    await filling_banned_accounts()
    await filling_all_keys_category()
    await filling_product_accounts_by_category_id()
    await filling_promo_code()
    await filling_vouchers()

    logger = get_logger(__name__)
    logger.info("Redis filling successfully")