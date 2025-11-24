from typing import List, Tuple, TypeVar

from src.exceptions.service_exceptions import TypeAccountServiceNotFound
from src.services.accounts.shemas import HasPhone
from src.services.database.selling_accounts.actions import get_all_types_account_service, \
    get_all_phone_in_account_storage
from src.utils.core_logger import logger
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

    types_account_service = await get_all_types_account_service()
    type_account_service_id = None
    for type_service in types_account_service:
        if type_account_service == type_service.name:
            type_account_service_id = type_service.type_account_service_id

    # если не нашли полученный сервис
    if type_account_service_id is None:
        raise TypeAccountServiceNotFound()

    numbers_in_db = await get_all_phone_in_account_storage(type_account_service_id)

    for acc_data in account_data:
        # преобразовываем номер т.к. такой формат хранится в БД
        if phone_in_e164(acc_data.phone) in numbers_in_db:
            logger.info(f"[get_unique_among_db] - Найден дублик аккаунта: {acc_data.phone}")
            duplicate_items.append(acc_data)
        else:
            unique_items.append(acc_data)

    return unique_items, duplicate_items
