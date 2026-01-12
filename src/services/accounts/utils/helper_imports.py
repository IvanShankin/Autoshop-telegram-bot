from typing import List, Tuple, TypeVar

from src.exceptions import TypeAccountServiceNotFound
from src.services.accounts.shemas import HasPhone
from src.services.database.categories.actions import get_all_types_account_service, \
    get_all_phone_in_account_storage
from src.utils.core_logger import get_logger
from src.utils.pars_number import phone_in_e164


T = TypeVar("T", bound=HasPhone)


async def get_unique_among_db(
    account_data: List[T],
    type_account_service: str
) -> Tuple[List[T], List[T]]:
    """
    Отберёт уникальные аккаунты среди БД.
    Возвращает Tuple[List[T], List[T]] где T = тип элементов account_data
    :param account_data: Принимает AccountImportData, BaseAccountProcessingResult, ключевое требование, что бы было поле "phone"
    :param type_account_service: Тип сервиса ("telegram" и т.д.)
    :return: Tuple[Уникальные, Дубликаты]
    """
    unique_items = []
    duplicate_items = []

    numbers_in_db = await get_all_phone_in_account_storage(type_account_service)

    for acc_data in account_data:
        # преобразовываем номер т.к. такой формат хранится в БД
        if phone_in_e164(acc_data.phone) in numbers_in_db:
            logger = get_logger(__name__)
            logger.info(f"[get_unique_among_db] - Найден дублик аккаунта: {acc_data.phone}")
            duplicate_items.append(acc_data)
        else:
            unique_items.append(acc_data)

    return unique_items, duplicate_items
