import asyncio
import os
import shutil
from collections import deque

from typing import Optional, List, Tuple
from pathlib import Path

from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from src.broker.producer import publish_event
from src.config import ACCOUNTS_DIR
from src.exceptions.service_exceptions import CategoryNotFound, NotEnoughAccounts, NotEnoughMoney
from src.services.database.discounts.events import NewActivatePromoCode
from src.services.database.discounts.utils.calculation import discount_calculation
from src.services.database.selling_accounts.events.schemas import NewPurchaseAccount, AccountsData
from src.services.database.selling_accounts.models.models import PurchaseRequests, PurchaseRequestAccount
from src.services.database.users.models.models_users import BalanceHolder
from src.services.filesystem.account_actions import create_path_account, move_file, rename_file, move_in_account
from src.services.tg_accounts.actions import check_account_validity
from src.services.redis.filling_redis import filling_product_accounts_by_category_id, \
    filling_product_account_by_account_id, filling_sold_accounts_by_owner_id, filling_sold_account_by_account_id, \
    filling_user, filling_account_categories_by_service_id, filling_account_categories_by_category_id
from src.services.database.core.database import get_db
from src.services.database.selling_accounts.actions import get_account_categories_by_category_id, \
    update_account_storage, delete_product_account, add_deleted_accounts, get_account_service, get_type_account_service, \
    get_product_account_by_category_id
from src.services.database.selling_accounts.models import ProductAccounts, SoldAccounts, PurchasesAccounts, \
    SoldAccountsTranslation, AccountCategoryTranslation, AccountStorage
from src.services.database.selling_accounts.models.schemas import StartPurchaseAccount
from src.services.database.users.actions import get_user
from src.services.database.users.models import Users
from src.utils.core_logger import logger
from src.bot_actions.actions import send_log


SEMAPHORE_LIMIT = 12
MAX_REPLACEMENT_ATTEMPTS = 3
REPLACEMENT_QUERY_LIMIT = 5  # сколько кандидатов брать за раз (можно увеличить)

async def purchase_accounts(
    user_id: int,
    category_id: int,
    quantity_accounts: int,
    promo_code_id: Optional[int],
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
    data = await start_purchase_request(user_id, category_id, quantity_accounts, promo_code_id)
    valid_list = await verify_reserved_accounts(data.product_accounts, data.type_service_name, data.purchase_request_id)
    if valid_list is False:
        await cancel_purchase_request(
            user_id = user_id,
            mapping = [],
            sold_account_ids = [],
            purchase_ids = [],
            total_amount = data.total_amount,
            purchase_request_id = data.purchase_request_id,
            product_accounts = [],
            type_service_name=data.type_service_name
        )
        text = (
            "#Недостаточно_аккаунтов \n"
            "Пользователь пытался купить аккаунты, но ему не нашлось необходимое количество аккаунтов"
        )
        await send_log(text)
        logger.warning(text)
        result = False
    else:
        data.product_accounts = valid_list # обновляем data.product_accounts на валидные
        await finalize_purchase(user_id, data)
        result = True

    # обновляем redis
    await filling_account_categories_by_service_id()
    await filling_account_categories_by_category_id()
    return result


async def start_purchase_request(
        user_id: int,
        category_id: int,
        quantity_accounts: int,
    promo_code_id: Optional[int]
) -> StartPurchaseAccount:
    """
Зафиксирует намерение покупки и заморозит деньги

Проверяет баланс пользователя и наличие аккаунтов

Создаёт:
запись в PurchaseRequests (status=processing)
запись в BalanceHolder (status=held)

Резервирует нужные аккаунты.
Списывает деньги — удерживая (через BalanceHolder).

:return: StartPurchaseAccount
"""

    # получаем категорию
    category = await get_account_categories_by_category_id(category_id)
    account_service = await get_account_service(category.account_service_id, return_not_show=True)
    type_service = await get_type_account_service(account_service.type_account_service_id)

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(AccountCategoryTranslation)
            .where(AccountCategoryTranslation.account_category_id == category_id)
        )
        translations_category: list[AccountCategoryTranslation] = result_db.scalars().all()

    if not category or not translations_category:
        raise CategoryNotFound("Данной категории больше не существует")

    original_price_per = category.price_one_account
    original_total = original_price_per * quantity_accounts  # оригинальная сумма которую должен заплатить пользователь

    # рассчитываем скидку
    if promo_code_id:
        discount_amount, _ = await discount_calculation(original_total, promo_code_id=promo_code_id)
    else:
        discount_amount = 0
    final_total = max(0, original_total - discount_amount)  # конечная сумма которую должен заплатить пользователь

    # проверяем баланс пользователя
    user = await get_user(user_id)
    user_balance_before = user.balance
    if user.balance < final_total:
        raise NotEnoughMoney("Недостаточно средств для покупки аккаунтов", final_total - user.balance)

    async with get_db() as session_db:
        async with session_db.begin():
            q = (
                select(ProductAccounts)
                .options(selectinload(ProductAccounts.account_storage))
                .join(ProductAccounts.account_storage)
                .where(
                    (ProductAccounts.account_category_id == category_id) &
                    (AccountStorage.status == "for_sale")
                )
                .order_by(ProductAccounts.created_at.desc())
                .with_for_update()
                .limit(quantity_accounts)
            )
            result_db = await session_db.execute(q)
            product_accounts: list[ProductAccounts] = result_db.scalars().all()
            account_storages_ids: list[int] = [account.account_storage.account_storage_id for account in product_accounts]

            if len(product_accounts) < quantity_accounts:
                raise NotEnoughAccounts("У данной категории недостаточно аккаунтов")

            await session_db.execute(
                update(AccountStorage)
                .where(AccountStorage.account_storage_id.in_(account_storages_ids))
                .values(status='reserved')
            )

            new_purchase_requests = PurchaseRequests(
                user_id=user_id,
                promo_code_id=promo_code_id,
                quantity=quantity_accounts,
                total_amount=final_total,
                status='processing'
            )
            session_db.add(new_purchase_requests)
            await session_db.flush()

            for id in account_storages_ids:
                new_purchase_request_account = PurchaseRequestAccount(
                    purchase_request_id = new_purchase_requests.purchase_request_id,
                    account_storage_id = id,
                )
                session_db.add(new_purchase_request_account)

            # Действие с балансом
            new_balance_holder = BalanceHolder(
                purchase_request_id=new_purchase_requests.purchase_request_id,
                user_id = user_id,
                amount = final_total
            )
            session_db.add(new_balance_holder)
            result_db = await session_db.execute(
                update(Users)
                .where(Users.user_id == user_id)
                .values(balance=Users.balance - final_total)
                .returning(Users)
            )
            user = result_db.scalar_one_or_none()

            # после выхода из транзакции произойдёт commit()
        await filling_user(user)

        for ac_id in [account.account_id for account in product_accounts]:
            await filling_product_account_by_account_id(ac_id)

    return StartPurchaseAccount(
        purchase_request_id = new_purchase_requests.purchase_request_id,
        category_id = category_id,
        type_account_service_id = type_service.type_account_service_id,
        promo_code_id = promo_code_id,
        product_accounts = product_accounts,
        type_service_name = type_service.name,
        translations_category = translations_category,
        original_price_one_acc = category.price_one_account,
        purchase_price_one_acc = final_total // quantity_accounts if final_total > 0 else final_total ,
        cost_price_one_acc = category.cost_price_one_account,
        total_amount = final_total,
        user_balance_before = user_balance_before,
        user_balance_after = user.balance
    )


async def _delete_account(account_storage: List[ProductAccounts], type_service_name: str):
    """Проведёт всю необходимую работу с БД и переместит аккаунты с for_sale в deleted"""

    if account_storage:
        category = await get_account_categories_by_category_id(
            account_category_id=account_storage[0].account_category_id,
            return_not_show=True
        )

        for bad_account in account_storage:
            await move_in_account(account=bad_account.account_storage, type_service_name=type_service_name, status="deleted")

            # помечаем первоначальный плохо прошедший аккаунт как deleted сразу
            try:
                await update_account_storage(
                    bad_account.account_storage.account_storage_id,
                    status='deleted',
                    is_valid=False,
                    is_active=False
                )
                await delete_product_account(bad_account.account_id)
            except Exception:
                logger.exception("Error marking bad account deleted %s", bad_account.account_storage.account_storage_id)

            # логируем в deleted_accounts
            try:

                await add_deleted_accounts(
                    type_account_service_id=bad_account.type_account_service_id,
                    account_storage_id=bad_account.account_storage.account_storage_id,
                    category_name=category.name,
                    description=category.description
                )
                text = (
                    "\n#Невалидный_аккаунт \n"
                    "При покупке был найден невалидный аккаунт, он удалён с продажи \n"
                    "Данные об аккаунте: \n"
                    f"storage_account_id: {bad_account.account_storage.account_storage_id}\n"
                    f"Себестоимость: {category.cost_price_one_account}\n"
                )
                await send_log(text)
                logger.info(text)
            except Exception:
                logger.exception("Failed to log deleted account %s", bad_account.account_storage.account_storage_id)


async def verify_reserved_accounts(
    product_accounts: List[ProductAccounts],
    type_service_name: str,
    purchase_request_id: int
) -> List[ProductAccounts] | False:
    """
    Проверяет валидность аккаунтов, если невалидный — заменит и логирует.
    Возвращает False, если не удалось собрать нужное количество валидных аккаунтов.
    :param product_accounts: Обязательно ProductAccounts с подгруженными account_storage
    :param type_service_name: имя типа сервиса
    :param purchase_request_id: id заказа
    :return: List[ProductAccounts] если нашли необходимое количество валидных аккаунтов. False если нет нужного количества аккаунтов
    """
    if not product_accounts:
        return False

    # 1) Подготовим list AccountStorage объектов из переданных ProductAccounts
    #    product_accounts гарантированно имеют подгруженный account_storage
    slots = [pa for pa in product_accounts] # работаем с ProductAccounts
    sem = asyncio.Semaphore(SEMAPHORE_LIMIT) # семафор для ограничения параллелизма проверок

    async def validate_slot(pa: ProductAccounts):
        """Проверка одного ProductAccounts -> возвращает (pa, is_valid)"""
        async with sem:
            return pa, await check_account_validity(pa.account_storage, type_service_name)

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
    invalid_accounts: list[ProductAccounts] = []
    valid_accounts: list[ProductAccounts] = []
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
    async with get_db() as session_db:
        attempts = 0

        if invalid_accounts:
            # переносим аккаунты к невалидным
            await _delete_account(invalid_accounts, type_service_name=type_service_name)

        while bad_queue and attempts < MAX_REPLACEMENT_ATTEMPTS:
            attempts += 1
            # необходимое количество аккаунтов с БД
            to_fetch = min(max(REPLACEMENT_QUERY_LIMIT, len(bad_queue)), len(bad_queue) * 2)
            # выбираем пачку кандидатов (atomic select)
            try:
                async with session_db.begin():
                    q = (
                        select(ProductAccounts)
                        .options(selectinload(ProductAccounts.account_storage))
                        .join(ProductAccounts.account_storage)
                        .where(
                            (ProductAccounts.account_category_id == bad_queue[0].account_category_id) &  # выбираем по категории текущей «дыры»
                            (ProductAccounts.type_account_service_id == bad_queue[0].type_account_service_id) &
                            (AccountStorage.is_active == True) &
                            (AccountStorage.is_valid == True) &
                            (AccountStorage.status == "for_sale")
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
                            .values(status='reserved')
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
                        ok = await check_account_validity(candidate.account_storage, type_service_name)
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
                await _delete_account(invalid_candidates, type_service_name=type_service_name)

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
                            .values(status='for_sale')
                        )
                # конец session_db.begin() — commit
            except Exception as e:
                logger.exception("DB error while applying candidate results: %s", e)
                # best-effort: попытаться вернуть reserved -> for_sale
                try:
                    ids = [c.account_storage.account_storage_id for c in candidates]
                    await session_db.execute(
                        update(AccountStorage)
                        .where(AccountStorage.account_storage_id.in_(ids))
                        .values(status='for_sale')
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



async def cancel_purchase_request(
    user_id: int,
    mapping: List[Tuple[str, str, str]],  # list of (orig_path, temp_path, final_path)
    sold_account_ids: List[int],
    purchase_ids: List[int],
    total_amount: int,
    purchase_request_id: int,
    product_accounts: List[ProductAccounts],
    type_service_name: str,
):
    """
    получает mapping и пытается вернуть файлы и БД в исходное состояние

    :param mapping: список кортежей (orig_path, temp_path, final_path)
     - orig_path: изначальный путь (старое место)
     - temp_path: временный путь куда мы переместили файл до коммита
     - final_path: финальный путь (куда будет переименован после commit)
    :param sold_account_ids: список уже созданных sold_account (если есть) — удалим их и вернём product-строки
    :param purchase_ids: список purchases_accounts — удалим PurchasesAccounts
    :param product_accounts: Список orm объектов с обязательно подгруженными account_storage
    """
    user = None
    # Попытаться вернуть временные файлы обратно (temp -> orig) если они существуют
    for orig, temp, final in mapping:
        for src in (temp, final):
            if src and os.path.exists(src):
                try:
                    os.makedirs(os.path.dirname(orig), exist_ok=True)
                    await asyncio.to_thread(shutil.move, src, orig)
                    break
                except Exception:
                    logger.exception("Failed to restore file for %s from %s", orig, src)

        # если final уже существует (переименование успело произойти), попытаться вернуть final -> orig
        try:
            if final and os.path.exists(final):
                await asyncio.to_thread(shutil.move, final, orig)
        except Exception:
            logger.exception("Failed to move final back to orig for %s", orig)

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

            # Удалим PurchasesAccounts и SoldAccounts
            if purchase_ids:
                await session.execute(delete(PurchasesAccounts).where(PurchasesAccounts.purchase_id.in_(purchase_ids)))
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
                            status="bought",
                            type_account_service=type_service_name,
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
                            type_account_service_id=account.type_account_service_id,
                            account_category_id=account.account_category_id,
                            account_storage_id=aid
                        ))

            except Exception:
                logger.exception("Failed to restore account storage status")

            # Обновляем PurchaseRequests и BalanceHolder
            try:
                await session.execute(
                    update(PurchaseRequests)
                    .where(PurchaseRequests.purchase_request_id == purchase_request_id)
                    .values(status='failed')
                )
                await session.execute(
                    update(BalanceHolder)
                    .where(BalanceHolder.purchase_request_id == purchase_request_id)
                    .values(status='released')
                )
            except Exception:
                logger.exception("Failed to update purchase request / balance holder status")

    if user:
        await filling_user(user)
    await filling_sold_accounts_by_owner_id(user_id)
    await filling_product_accounts_by_category_id()
    for sid in sold_account_ids:
        await filling_sold_account_by_account_id(sid)
    for pid in product_accounts:
        await filling_product_account_by_account_id(pid.account_id)

    logger.info("cancel_purchase_request finished for purchase %s", purchase_request_id)


async def finalize_purchase(user_id: int, data: StartPurchaseAccount):
    """
    Безопасно переносит файлы (в temp), создаёт DB записи в транзакции,
    затем финализирует перемещение temp->final. При ошибке — вызывает cancel_purchase_request.
    """
    mapping: List[Tuple[str, str, str]] = []  #  (orig, temp, final)
    sold_account_ids: List[int] = []
    purchase_ids: List[int] = []
    account_movement: list[AccountsData] = []

    try:
        # Подготовим перемещения в temp (вне транзакции) — НЕ изменяем DB
        for account in data.product_accounts:
            orig = str(Path(ACCOUNTS_DIR) / account.account_storage.file_path) # полный путь
            final = create_path_account(
                status="bought",
                type_account_service=data.type_service_name,
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
                await cancel_purchase_request(
                    user_id=user_id,
                    mapping=mapping,
                    sold_account_ids=sold_account_ids,
                    purchase_ids=purchase_ids,
                    total_amount=data.total_amount,
                    purchase_request_id=data.purchase_request_id,
                    product_accounts=data.product_accounts,
                    type_service_name=data.type_service_name
                )
                return

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
                        type_account_service_id=data.type_account_service_id
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
                    new_purchase = PurchasesAccounts(
                        user_id=user_id,
                        account_storage_id=account.account_storage.account_storage_id,
                        original_price=data.original_price_one_acc,
                        purchase_price=data.purchase_price_one_acc,
                        cost_price=data.cost_price_one_acc,
                        net_profit=data.purchase_price_one_acc - data.cost_price_one_acc
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
                                type_account_service=data.type_service_name,
                                uuid=account.account_storage.storage_uuid
                            )
                        )
                    )
                    account_movement.append(AccountsData(
                        id_account_storage = account.account_storage.account_storage_id,
                        id_new_sold_account = new_sold.sold_account_id,
                        id_purchase_account = new_purchase.purchase_id,
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
            await cancel_purchase_request(
                user_id=user_id,
                mapping=mapping,
                sold_account_ids=sold_account_ids,
                purchase_ids=purchase_ids,
                total_amount=data.total_amount,
                purchase_request_id=data.purchase_request_id,
                product_accounts=data.product_accounts,
                type_service_name=data.type_service_name
            )
            return

        # обновление redis
        await filling_sold_accounts_by_owner_id(user_id)
        await filling_product_accounts_by_category_id()
        for sid in sold_account_ids:
            await filling_sold_account_by_account_id(sid)
        for pid in data.product_accounts:
            await filling_product_account_by_account_id(pid.account_id)

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
            accounts_left=len(product_accounts)
        )
        await publish_event(new_purchase.model_dump(), 'account.purchase')

    except Exception as e:
        logger.exception("Error in finalize_purchase: %s", e)
        await send_log(f"#Ошибка finalise_purchase: {e}")
        await cancel_purchase_request(
            user_id=user_id,
            mapping=mapping,
            sold_account_ids=sold_account_ids,
            purchase_ids=purchase_ids,
            total_amount=data.total_amount,
            purchase_request_id=data.purchase_request_id,
            product_accounts=data.product_accounts,
            type_service_name=data.type_service_name
        )

