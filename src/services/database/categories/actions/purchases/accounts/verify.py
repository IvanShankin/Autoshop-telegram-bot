import asyncio
from collections import deque
from typing import List, Tuple

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from src.bot_actions.messages import send_log
from src.services.database.categories.actions.actions_get import get_category_by_category_id
from src.services.database.categories.actions.products.accounts.actions_add import add_deleted_accounts
from src.services.database.categories.actions.products.accounts.actions_delete import delete_product_account
from src.services.database.categories.actions.products.accounts.actions_update import update_account_storage
from src.services.database.categories.models import ProductAccounts, AccountStorage, PurchaseRequests, \
    PurchaseRequestAccount, AccountServiceType, StorageStatus
from src.services.database.core.database import get_db
from src.services.filesystem.account_actions import move_in_account
from src.services.products.accounts.tg.actions import check_account_validity
from src.utils.core_logger import get_logger

SEMAPHORE_LIMIT_ACCOUNT = 12
SEMAPHORE_LIMIT_UNIVERSAL = 50
MAX_REPLACEMENT_ATTEMPTS = 3
REPLACEMENT_QUERY_LIMIT = 5  # сколько кандидатов брать за раз (можно увеличить)


async def _delete_account(account_storage: List[ProductAccounts], type_service_account: AccountServiceType):
    """Проведёт всю необходимую работу с БД и переместит аккаунты с for_sale в deleted"""

    if account_storage:
        category = await get_category_by_category_id(
            category_id=account_storage[0].category_id,
            return_not_show=True
        )

        for bad_account in account_storage:
            bad_account.account_storage.status = StorageStatus.FOR_SALE # аккаунт хранится на данном этапе здесь
            await move_in_account(
                account=bad_account.account_storage,
                type_service_name=type_service_account,
                status=StorageStatus.DELETED
            )

            # помечаем первоначальный плохо прошедший аккаунт как deleted сразу
            try:
                await update_account_storage(
                    bad_account.account_storage.account_storage_id,
                    status=StorageStatus.DELETED,
                    is_valid=False,
                    is_active=False
                )
                await delete_product_account(bad_account.account_id)
            except Exception:
                logger = get_logger(__name__)
                logger.exception("Error marking bad account deleted %s", bad_account.account_storage.account_storage_id)

            # логируем в deleted_accounts
            try:

                await add_deleted_accounts(
                    account_storage_id=bad_account.account_storage.account_storage_id,
                    category_name=category.name,
                    description=category.description
                )
                text = (
                    "\n#Невалидный_аккаунт \n"
                    "При покупке был найден невалидный аккаунт, он удалён с продажи \n"
                    "Данные об аккаунте: \n"
                    f"storage_account_id: {bad_account.account_storage.account_storage_id}\n"
                    f"Себестоимость: {category.cost_price}\n"
                )
                await send_log(text)

                logger = get_logger(__name__)
                logger.info(text)
            except Exception:
                logger = get_logger(__name__)
                logger.exception("Failed to log deleted account %s", bad_account.account_storage.account_storage_id)


async def verify_reserved_accounts(
    product_accounts: List[ProductAccounts],
    type_service_account: AccountServiceType,
    purchase_request_id: int
) -> List[ProductAccounts] | False:
    """
    Проверяет валидность аккаунтов, если невалидный — заменит и логирует.
    Возвращает False, если не удалось собрать нужное количество валидных аккаунтов.
    :param product_accounts: Обязательно ProductAccounts с подгруженными account_storage
    :param type_service_account: тип сервиса у аккаунтов
    :param purchase_request_id: id заказа
    :return: List[ProductAccounts] если нашли необходимое количество валидных аккаунтов. False если нет нужного количества аккаунтов
    """
    if not product_accounts:
        return False

    logger = get_logger(__name__)

    # 1) Подготовим list AccountStorage объектов из переданных ProductAccounts
    #    product_accounts гарантированно имеют подгруженный account_storage
    slots = [pa for pa in product_accounts] # работаем с ProductAccounts
    sem = asyncio.Semaphore(SEMAPHORE_LIMIT_ACCOUNT) # семафор для ограничения параллелизма проверок

    async def validate_slot(pa: ProductAccounts) -> Tuple[ProductAccounts, bool]:
        """Проверка одного ProductAccounts -> возвращает (pa, is_valid)"""
        async with sem:
            return pa, await check_account_validity(pa.account_storage, type_service_account, StorageStatus.FOR_SALE)

    # 2) Получим purchase_request (чтобы иметь доступ к balance_holder)
    async with get_db() as session_db:
        purchase_req = await session_db.scalar(
            select(PurchaseRequests)
            .options(selectinload(PurchaseRequests.balance_holder))
            .where(PurchaseRequests.purchase_request_id == purchase_request_id)
        )
        if not purchase_req:
            logger.warning("Purchase request %s not found", purchase_request_id)
            return False

    # 3) Параллельно проверяем все текущие слоты
    #    (замены будем обрабатывать отдельно для каждого невалидного слота)
    initial_checks = await asyncio.gather(*[validate_slot(pa) for pa in slots], return_exceptions=True)

    # 4) Собираем результат и формируем список невалидных слотов
    invalid_accounts: List[ProductAccounts] = []
    valid_accounts: List[ProductAccounts] = []
    for res in initial_checks:
        if isinstance(res, Exception):
            # на проверке упало исключение — считаем невалидным
            logger.exception("Validation task exception: %s", res)
            # не имеем прямой ProductAccounts здесь — пропускаем (безопаснее: fail later)
            # безопаснее получить index, для простоты — вернуть False
            return False
        pa, ok = res
        if ok:
            valid_accounts.append(pa)
        else:
            invalid_accounts.append(pa)

    # если нет дыр — просто возвращаем валидные (их количество == исходному)
    if not invalid_accounts:
        return valid_accounts

    # нам нужно заменить эти invalid_accounts — считаем сколько нужно
    bad_queue = deque(invalid_accounts)

    # Начинаем итеративный поиск замен пакетами
    attempts = 0

    if invalid_accounts:
        # переносим аккаунты к невалидным
        await _delete_account(invalid_accounts, type_service_account=type_service_account)

    while bad_queue and attempts < MAX_REPLACEMENT_ATTEMPTS:
        attempts += 1
        # необходимое количество аккаунтов с БД
        to_fetch = min(max(REPLACEMENT_QUERY_LIMIT, len(bad_queue)), len(bad_queue) * 2)
        # выбираем пачку кандидатов (atomic select)

        async with get_db() as session_db:
            try:
                async with session_db.begin():
                    q = (
                        select(ProductAccounts)
                        .options(selectinload(ProductAccounts.account_storage))
                        .join(ProductAccounts.account_storage)
                        .where(
                            (ProductAccounts.category_id == bad_queue[0].category_id) &  # выбираем по категории текущей «дыры»
                            (AccountStorage.type_account_service == type_service_account) &
                            (AccountStorage.is_active == True) &
                            (AccountStorage.is_valid == True) &
                            (AccountStorage.status == StorageStatus.FOR_SALE)
                        )
                        .with_for_update()
                        .limit(to_fetch)
                    )
                    result = await session_db.execute(q)
                    candidates: List[ProductAccounts] = result.scalars().all()

                    if not candidates:
                        # нет кандидатов
                        logger.debug("No replacement candidates on attempt %s for request %s", attempts,
                                     purchase_request_id)
                        return False
                    else:
                        # резервируем всех выбранных кандидатов
                        storage_ids = [c.account_storage.account_storage_id for c in candidates]
                        await session_db.execute(
                            update(AccountStorage)
                            .where(AccountStorage.account_storage_id.in_(storage_ids))
                            .values(status=StorageStatus.RESERVED)
                        )
                        # commit произойдёт по выходу из session_db.begin()
            except Exception as e:
                logger.exception("DB error while selecting/reserving replacement batch: %s", e)
                await asyncio.sleep(0.2)
                continue

        if not candidates:
            return False

        # Проверяем пачку кандидатов параллельно (семафор ограничивает нагрузку)
        async def validate_candidate(candidate: ProductAccounts):
            async with sem:
                try:
                    ok = await check_account_validity(candidate.account_storage, type_service_account, StorageStatus.FOR_SALE)
                    return candidate, ok
                except Exception as e:
                    logger.exception("Candidate validation exception for %s: %s",
                                     getattr(candidate.account_storage, "account_storage_id", None), e)
                    return candidate, False

        checks = await asyncio.gather(*[validate_candidate(c) for c in candidates], return_exceptions=False)

        # Разделяем валидные и невалидные кандидаты
        valid_candidates: list[ProductAccounts] = [c for c, ok in checks if ok]
        invalid_candidates: list[ProductAccounts] = [c for c, ok in checks if not ok]

        # Теперь применяем изменения в БД: удаляем невалидных, возвращаем неиспользованных валидных в for_sale,
        # и привязываем нужное количество валидных к заявке (заменяем позиции из bad_queue).
        try:
            # удаление невалидных аккаунтов
            await _delete_account(invalid_candidates, type_service_account=type_service_account)

            async with get_db() as session_db:
                async with session_db.begin():
                    # Используем столько валидных кандидатов, сколько нужно (по очереди из bad_queue)
                    used = 0
                    while valid_candidates and bad_queue:
                        chosen = valid_candidates.pop(0)
                        bad = bad_queue.popleft()

                        # обновляем связующую таблицу заявки: заменяем bad -> chosen
                        await session_db.execute(
                            update(PurchaseRequestAccount)
                            .where(
                                (PurchaseRequestAccount.purchase_request_id == purchase_request_id) &
                                (PurchaseRequestAccount.account_storage_id == bad.account_storage.account_storage_id)
                            )
                            .values(account_storage_id=chosen.account_storage.account_storage_id)
                        )

                        valid_accounts.append(chosen)
                        used += 1

                    # 3) Для оставшихся (валидных, но не использованных) — вернуть статус в for_sale
                    if valid_candidates:
                        keep_ids = [c.account_storage.account_storage_id for c in valid_candidates]
                        await session_db.execute(
                            update(AccountStorage)
                            .where(AccountStorage.account_storage_id.in_(keep_ids))
                            .values(status=StorageStatus.FOR_SALE)
                        )
                # конец session_db.begin() — commit
        except Exception as e:
            logger.exception("DB error while applying candidate results: %s", e)
            # best-effort: попытаться вернуть reserved -> for_sale
            try:
                async with get_db() as session_db:
                    ids = [c.account_storage.account_storage_id for c in candidates]
                    await session_db.execute(
                        update(AccountStorage)
                        .where(AccountStorage.account_storage_id.in_(ids))
                        .values(status=StorageStatus.FOR_SALE)
                    )
            except Exception:
                logger.exception("Failed to revert candidate statuses after error")
            # подождём и попробуем снова
            await asyncio.sleep(0.2)
            continue

        # если у нас всё ещё есть bad_queue — цикл продолжится и попробует новую пачку
        # иначе — мы успешно заменили все дыры
    # end attempts loop

    if bad_queue:
        # не смогли заменить все необходимые аккаунты
        logger.error("Could not find replacements for %d accounts after %d attempts (request %s)",
                     len(bad_queue), attempts, purchase_request_id)
        return False

    # Всё ок — для всех невалидных нашли замену (valid_accounts + originally valid) -> должны иметь нужное количество
    return valid_accounts

