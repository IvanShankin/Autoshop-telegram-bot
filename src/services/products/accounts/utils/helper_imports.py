from typing import List, Tuple

from src.services.database.categories.actions.products.accounts.actions_get import get_all_tg_id_in_account_storage
from src.services.database.categories.actions import get_all_phone_in_account_storage
from src.services.database.categories.models import AccountServiceType
from src.services.products.accounts.tg.shemas import BaseAccountProcessingResult
from src.utils.core_logger import get_logger
from src.utils.pars_number import phone_in_e164


async def get_unique_tg_acc_among_db(
    account_data: List[BaseAccountProcessingResult],
    type_account_service: AccountServiceType
) -> Tuple[List[BaseAccountProcessingResult], List[BaseAccountProcessingResult]]:
    """
    Отберёт уникальные аккаунты среди БД.
    :param type_account_service: Тип сервиса ("telegram" и т.д.)
    :return: Tuple[Уникальные, Дубликаты]
    """
    unique_items = []
    duplicate_items = []
    logger = get_logger(__name__)

    numbers_in_db = await get_all_phone_in_account_storage(type_account_service)
    tg_id_in_db = await get_all_tg_id_in_account_storage()

    for acc_data in account_data:
        # преобразовываем номер т.к. такой формат хранится в БД
        if phone_in_e164(acc_data.phone) in numbers_in_db:
            logger.info(f"[get_unique_tg_acc_among_db] - Найден дублик аккаунта по номеру телефона: {acc_data.phone}")
            duplicate_items.append(acc_data)
            continue

        if acc_data.user.id in tg_id_in_db:
            logger.info(f"[get_unique_tg_acc_among_db] - Найден дублик аккаунта по tg_id: {acc_data.user.id}")
            duplicate_items.append(acc_data)
            continue

        unique_items.append(acc_data)

    return unique_items, duplicate_items
