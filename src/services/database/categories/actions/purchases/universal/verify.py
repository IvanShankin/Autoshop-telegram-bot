import asyncio
from collections import deque
from typing import List, Tuple

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from src.bot_actions.messages import send_log
from src.config import get_config
from src.services.database.categories.actions.actions_get import get_category_by_category_id
from src.services.database.categories.actions.products.universal.action_delete import delete_prod_universal
from src.services.database.categories.actions.products.universal.action_update import update_universal_storage
from src.services.database.categories.actions.products.universal.actions_add import add_deleted_universal
from src.services.database.categories.models import PurchaseRequests
from src.services.database.categories.models.product_universal import UniversalStorageStatus, \
    ProductUniversal, UniversalStorage, PurchaseRequestUniversal
from src.services.database.categories.models.shemas.product_universal_schem import ProductUniversalFull
from src.services.database.core.database import get_db
from src.services.products.universals.actions import check_valid_universal_product, move_universal_storage
from src.services.secrets import get_crypto_context
from src.utils.core_logger import get_logger

SEMAPHORE_LIMIT_ACCOUNT = 12
SEMAPHORE_LIMIT_UNIVERSAL = 50
MAX_REPLACEMENT_ATTEMPTS = 3
REPLACEMENT_QUERY_LIMIT = 5  # сколько кандидатов брать за раз (можно увеличить)


async def _delete_universal(universal_product: List[ProductUniversalFull]):
    if universal_product:
        category = await get_category_by_category_id(
            category_id=universal_product[0].category_id,
            return_not_show=True
        )

        for bad_prod in universal_product:
            result_path = await move_universal_storage(
                storage=bad_prod.universal_storage,
                new_status=UniversalStorageStatus.DELETED
            )

            # помечаем первоначальный плохо прошедший продукт как deleted сразу
            try:
                await update_universal_storage(
                    universal_storage_id=bad_prod.universal_storage.universal_storage_id,
                    status=UniversalStorageStatus.DELETED,
                    is_active=False
                )
                await delete_prod_universal(bad_prod.product_universal_id)
            except Exception:
                logger = get_logger(__name__)
                logger.exception("Error marking bad account deleted %s", bad_prod.universal_storage.universal_storage_id)

            try:
                await add_deleted_universal(
                    universal_storage_id=bad_prod.universal_storage.universal_storage_id,
                )
                text = (
                    "\n#Невалидный_продукт \n"
                    "При покупке был найден невалидный универсальный продукт, он удалён с продажи \n"
                    "Данные об продукте: \n"
                    f"universal_storage_id: {bad_prod.universal_storage.universal_storage_id}\n"
                    f"Себестоимость: {category.cost_price}\n"
                )
                await send_log(text)

                logger = get_logger(__name__)
                logger.info(text)
            except Exception:
                logger = get_logger(__name__)
                logger.exception(
                    "Failed to log deleted product %s",
                    bad_prod.universal_storage.universal_storage_id
                )


async def verify_reserved_universal_one(
    product_universal: ProductUniversalFull,
) -> bool:
    """Для покупки товара когда у категории стоит флаг allow_multiple_purchase"""

    crypto = get_crypto_context()

    result_check = await check_valid_universal_product(
        product=product_universal,
        status=UniversalStorageStatus.FOR_SALE,
        crypto=crypto
    )

    if not result_check:
        await _delete_universal([product_universal])
        category = await get_category_by_category_id(product_universal.category_id, return_not_show=True)
        text = (
            "\n#Невалидный_продукт \n"
            "При покупке был найден невалидный универсальный продукт, он удалён с продажи \n"
            "Категория теперь не отображается! \n"
            f"ID категории: {category.category_id}\n"
            f"Имя категории: {category.name}\n"
            f"Описание внутри категории: {category.description}\n"
        )
        await send_log(text)

    return result_check


async def verify_reserved_universal_different(
    reserved_products: List[ProductUniversalFull],
    purchase_request_id: int
) -> List[ProductUniversalFull] | bool:
    """
        Для покупки товара когда у категории НЕ стоит флаг allow_multiple_purchase
        Проверяет валидность аккаунтов, если невалидный — заменит и логирует.
        Возвращает False, если не удалось собрать нужное количество валидных аккаунтов.
        :return: List[ProductAccounts] если нашли необходимое количество валидных аккаунтов. False если нет нужного количества аккаунтов
    """
    if not reserved_products:
        return False

    logger = get_logger(__name__)
    conf = get_config()
    crypto = get_crypto_context()

    slots = reserved_products.copy()
    sem = asyncio.Semaphore(SEMAPHORE_LIMIT_UNIVERSAL)  # семафор для ограничения параллелизма проверок

    async def validate_slot(product: ProductUniversalFull) -> Tuple[ProductUniversalFull, bool]:
        """Проверка одного ProductAccounts -> возвращает (pa, is_valid)"""
        async with sem:
            return product, await check_valid_universal_product(product, UniversalStorageStatus.FOR_SALE, crypto)

    # Получим purchase_request (чтобы иметь доступ к balance_holder)
    async with get_db() as session_db:
        purchase_req = await session_db.scalar(
            select(PurchaseRequests)
            .options(selectinload(PurchaseRequests.balance_holder))
            .where(PurchaseRequests.purchase_request_id == purchase_request_id)
        )
        if not purchase_req:
            logger.warning("Purchase request %s not found", purchase_request_id)
            return False

    # Параллельно проверяем все текущие слоты
    # (замены будем обрабатывать отдельно для каждого невалидного слота)
    initial_checks = await asyncio.gather(*[validate_slot(pa) for pa in slots], return_exceptions=True)

    # Собираем результат и формируем список невалидных слотов
    invalid_products: list[ProductUniversalFull] = []
    valid_products: list[ProductUniversalFull] = []
    for res in initial_checks:
        if isinstance(res, Exception):
            # на проверке упало исключение — считаем невалидным
            logger.exception("Validation task exception: %s", res)
            # не имеем прямой ProductUniversal здесь — пропускаем (безопаснее: fail later)
            # безопаснее получить index, для простоты — вернуть False
            return False
        prod, ok = res
        if ok:
            valid_products.append(prod)
        else:
            invalid_products.append(prod)

    # если нет дыр — просто возвращаем валидные (их количество == исходному)
    if not invalid_products:
        return valid_products

    # нам нужно заменить эти invalid_products — считаем сколько нужно
    bad_queue = deque(invalid_products)

    # Начинаем итеративный поиск замен пакетами
    async with get_db() as session_db:
        attempts = 0

        if invalid_products:
            # переносим аккаунты к невалидным
            await _delete_universal(invalid_products)

        while bad_queue and attempts < MAX_REPLACEMENT_ATTEMPTS:
            attempts += 1
            # необходимое количество товаров с БД
            to_fetch = min(max(REPLACEMENT_QUERY_LIMIT, len(bad_queue)), len(bad_queue) * 2)
            # выбираем пачку кандидатов (atomic select)
            try:
                async with session_db.begin():
                    q = (
                        select(ProductUniversal)
                        .options(selectinload(ProductUniversal.storage).selectinload(UniversalStorage.translations))
                        .join(ProductUniversal.storage)
                        .where(
                            (ProductUniversal.category_id == bad_queue[0].category_id) &  # выбираем по категории текущей «дыры»
                            (UniversalStorage.is_active == True) &
                            (UniversalStorage.status == UniversalStorageStatus.FOR_SALE)
                        )
                        .with_for_update()
                        .limit(to_fetch)
                    )
                    result = await session_db.execute(q)
                    candidates: List[ProductUniversal] = result.scalars().all()

                    if not candidates:
                        # нет кандидатов
                        logger.debug(
                            "No replacement candidates on attempt %s for request %s",
                            attempts,
                            purchase_request_id
                        )
                        return False
                    else:
                        # резервируем всех выбранных кандидатов
                        storage_ids = [c.storage.universal_storage_id for c in candidates]
                        await session_db.execute(
                            update(UniversalStorage)
                            .where(UniversalStorage.universal_storage_id.in_(storage_ids))
                            .values(status=UniversalStorageStatus.RESERVED)
                        )
                        # commit произойдёт по выходу из session_db.begin()
            except Exception as e:
                logger.exception("DB error while selecting/reserving replacement batch: %s", e)
                await asyncio.sleep(0.2)
                continue

            if not candidates:
                return False

            candidates_full = [ProductUniversalFull.from_orm_model(can, conf.app.default_lang) for can in candidates]

            # Проверяем пачку кандидатов параллельно (семафор ограничивает нагрузку)
            async def validate_candidate(candidates_full: ProductUniversalFull) -> Tuple[ProductUniversalFull, bool]:
                async with sem:
                    try:
                        ok = await check_valid_universal_product(candidates_full, UniversalStorageStatus.FOR_SALE, crypto)
                        return candidates_full, ok
                    except Exception as e:
                        logger.exception(
                            "Candidate validation exception for %s: %s",
                            getattr(candidates_full.account_storage, "account_storage_id", None), e
                        )
                        return candidates_full, False

            checks = await asyncio.gather(*[validate_candidate(c) for c in candidates_full], return_exceptions=False)

            # Разделяем валидные и невалидные кандидаты
            valid_candidates: List[ProductUniversalFull] = [c for c, ok in checks if ok]
            invalid_candidates: List[ProductUniversalFull] = [c for c, ok in checks if not ok]

            # Теперь применяем изменения в БД: удаляем невалидных, возвращаем неиспользованных валидных в for_sale,
            # и привязываем нужное количество валидных к заявке (заменяем позиции из bad_queue).
            try:
                # удаление невалидных аккаунтов
                await _delete_universal(invalid_candidates)

                async with session_db.begin():
                    # Используем столько валидных кандидатов, сколько нужно (по очереди из bad_queue)
                    used = 0
                    while valid_candidates and bad_queue:
                        chosen = valid_candidates.pop(0)
                        bad = bad_queue.popleft()

                        # обновляем связующую таблицу заявки: заменяем bad -> chosen
                        await session_db.execute(
                            update(PurchaseRequestUniversal)
                            .where(
                                (PurchaseRequestUniversal.purchase_request_id == purchase_request_id) &
                                (PurchaseRequestUniversal.universal_storage_id == bad.universal_storage.universal_storage_id)
                            )
                            .values(universal_storage_id=chosen.universal_storage.universal_storage_id)
                        )

                        valid_products.append(chosen)
                        used += 1

                    # 3) Для оставшихся (валидных, но не использованных) — вернуть статус в for_sale
                    if valid_candidates:
                        keep_ids = [c.universal_storage.universal_storage_id for c in valid_candidates]
                        await session_db.execute(
                            update(UniversalStorage)
                            .where(UniversalStorage.universal_storage_id.in_(keep_ids))
                            .values(status=UniversalStorageStatus.FOR_SALE)
                        )
                # конец session_db.begin() — commit
            except Exception as e:
                logger.exception("DB error while applying candidate results: %s", e)
                # best-effort: попытаться вернуть reserved -> for_sale
                try:
                    ids = [c.storage.universal_storage_id for c in candidates]
                    await session_db.execute(
                        update(UniversalStorage)
                        .where(UniversalStorage.universal_storage_id.in_(ids))
                        .values(status=UniversalStorageStatus.FOR_SALE)
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

    # Всё ок — для всех невалидных нашли замену (valid_products + originally valid) -> должны иметь нужное количество
    return valid_products
