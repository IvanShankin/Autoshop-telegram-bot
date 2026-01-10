from typing import List

from src.exceptions import ProductAccountNotFound
from src.services.database.product_categories.actions import get_product_account_by_category_id
from src.services.database.product_categories.models import ProductAccountFull


async def get_account_storage_by_category_id(category_id: int) -> List[ProductAccountFull]:
    all_accounts = await get_product_account_by_category_id(category_id, get_full=True)

    if not all_accounts:
        raise ProductAccountNotFound()

    return all_accounts
