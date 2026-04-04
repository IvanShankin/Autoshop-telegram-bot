import asyncio
import shutil
from collections import deque
from pathlib import Path
from typing import List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.read_models import EventSentLog, LogLevel
from src.config import Config
from src.database.models.categories import AccountServiceType, StorageStatus, ProductType
from src.exceptions import NotEnoughAccounts
from src.infrastructure.rebbit_mq.producer import publish_event
from src.models.create_models.accounts import CreateDeletedAccountDTO
from src.models.read_models import StartPurchaseAccount
from src.repository.redis import UsersCacheRepository
from src.services._database.categories.events.schemas import NewPurchaseAccount, AccountsData
from src.services._database.discounts.events import NewActivatePromoCode
from src.services.filesystem.account_actions import move_in_account
from src.services.filesystem.actions import move_file
from src.services.filesystem.media_paths import create_path_account
from src.services.filesystem.account_actions import rename_file
from src.services.products.accounts.tg.actions import check_account_validity
from src.services.models.categories.categories_cache_filler_service import CategoriesCacheFillerService
from src.services.models.categories.category_service import CategoryService
from src.services.models.products.accounts.account_deleted_service import AccountDeletedService
from src.services.models.products.accounts.accounts_cache_filler_service import AccountsCacheFillerService
from src.services.models.purchases.general.purchase_cancel_service import PurchaseCancelService
from src.services.models.purchases.general.purchase_request_service import PurchaseRequestService
from src.services.models.purchases.general.purchase_validation_service import PurchaseValidationService
from src.repository.database.categories import (
    ProductAccountsRepository,
    AccountStorageRepository,
    PurchaseRequestAccountsRepository,
    SoldAccountsRepository,
    SoldAccountsTranslationRepository,
    PurchasesRepository,
)
from src.utils.core_logger import get_logger

SEMAPHORE_LIMIT_ACCOUNT = 12
MAX_REPLACEMENT_ATTEMPTS = 3
REPLACEMENT_QUERY_LIMIT = 5


class AccountPurchaseService:

    def __init__(
        self,
        validation_service: PurchaseValidationService,
        purchase_request_service: PurchaseRequestService,
        purchase_cancel_service: PurchaseCancelService,
        product_repo: ProductAccountsRepository,
        storage_repo: AccountStorageRepository,
        purchase_request_account_repo: PurchaseRequestAccountsRepository,
        sold_repo: SoldAccountsRepository,
        sold_trans_repo: SoldAccountsTranslationRepository,
        purchases_repo: PurchasesRepository,
        deleted_service: AccountDeletedService,
        category_service: CategoryService,
        accounts_cache_filler: AccountsCacheFillerService,
        categories_cache_filler: CategoriesCacheFillerService,
        user_cache_repo: UsersCacheRepository,
        conf: Config,
        session_db: AsyncSession,
    ):
        self.validation_service = validation_service
        self.purchase_request_service = purchase_request_service
        self.purchase_cancel_service = purchase_cancel_service
        self.product_repo = product_repo
        self.storage_repo = storage_repo
        self.purchase_request_account_repo = purchase_request_account_repo
        self.sold_repo = sold_repo
        self.sold_trans_repo = sold_trans_repo
        self.purchases_repo = purchases_repo
        self.deleted_service = deleted_service
        self.category_service = category_service
        self.accounts_cache_filler = accounts_cache_filler
        self.categories_cache_filler = categories_cache_filler
        self.user_cache_repo = user_cache_repo
        self.conf = conf
        self.session_db = session_db

    async def start_purchase(
        self,
        user_id: int,
        category_id: int,
        quantity_accounts: int,
        promo_code_id: int | None = None,
    ) -> StartPurchaseAccount:
        """
        Зафиксирует намерение покупки и заморозит деньги.
        Проверяет баланс пользователя и наличие товара.

        Создаёт PurchaseRequest, резервирует аккаунты, переводит средства в BalanceHolder.

        :exception NotEnoughAccounts: Если товаров недостаточно.
        :exception CategoryNotFound: Если категория не найдена.
        :exception UserNotFound: Если пользователь не найден.
        :exception NotEnoughMoney: Если недостаточно средств.
        """
        result_check = await self.validation_service.check_category_and_money(
            user_id,
            category_id,
            quantity_accounts,
            promo_code_id,
        )

        async with self.session_db.begin():
            new_purchase_request = await self.purchase_request_service.create_request(
                user_id=user_id,
                promo_code_id=promo_code_id,
                quantity=quantity_accounts,
                total_amount=result_check.final_total,
            )

            product_accounts = await self.product_repo.get_for_update_by_category(
                category_id=category_id,
                limit=quantity_accounts,
            )
            if len(product_accounts) < quantity_accounts:
                raise NotEnoughAccounts("У данной категории недостаточно аккаунтов")

            storage_ids = [acc.account_storage.account_storage_id for acc in product_accounts]
            await self.storage_repo.update_status_by_ids(
                storage_ids,
                status=StorageStatus.RESERVED,
            )

            await self.purchase_request_account_repo.create_many(
                purchase_request_id=new_purchase_request.purchase_request_id,
                account_storage_ids=storage_ids,
            )

            user = await self.purchase_request_service.hold_funds(
                user_id=user_id,
                purchase_request_id=new_purchase_request.purchase_request_id,
                amount=result_check.final_total,
            )

        await self.user_cache_repo.set(user, int(self.conf.redis_time_storage.user))
        for acc in product_accounts:
            await self.accounts_cache_filler.fill_product_account_by_account_id(acc.account_id)
        await self.categories_cache_filler.fill_need_category(category_id)

        return StartPurchaseAccount(
            purchase_request_id=new_purchase_request.purchase_request_id,
            category_id=category_id,
            type_service_account=result_check.category.type_account_service,
            promo_code_id=promo_code_id,
            product_accounts=product_accounts,
            translations_category=result_check.translations_category,
            original_price_one=result_check.category.price,
            purchase_price_one=(
                result_check.final_total // quantity_accounts
                if result_check.final_total > 0
                else result_check.final_total
            ),
            cost_price_one=result_check.category.cost_price,
            total_amount=result_check.final_total,
            user_balance_before=result_check.user_balance_before,
            user_balance_after=user.balance,
        )

    async def verify_reserved_accounts(
        self,
        product_accounts: List,
        type_service_account: AccountServiceType,
        purchase_request_id: int,
    ) -> List | bool:
        """
        Проверяет валидность аккаунтов и подменяет невалидные. Использует `check_account_validity`, удаляет плохие,
        заменяет в PurchaseRequestAccount и возвращает устранённый список.
        """
        if not product_accounts:
            return False

        logger = get_logger(__name__)
        slots = [pa for pa in product_accounts]
        sem = asyncio.Semaphore(SEMAPHORE_LIMIT_ACCOUNT)

        async def validate_slot(pa):
            async with sem:
                return pa, await check_account_validity(
                    pa.account_storage,
                    type_service_account,
                    StorageStatus.FOR_SALE,
                )

        initial_checks = await asyncio.gather(*[validate_slot(pa) for pa in slots], return_exceptions=True)

        invalid_accounts = []
        valid_accounts = []
        for res in initial_checks:
            if isinstance(res, Exception):
                logger.exception("Validation task exception: %s", res)
                return False
            pa, ok = res
            if ok:
                valid_accounts.append(pa)
            else:
                invalid_accounts.append(pa)

        if not invalid_accounts:
            return valid_accounts

        await self._delete_accounts(invalid_accounts, type_service_account=type_service_account)

        bad_queue = deque(invalid_accounts)
        attempts = 0

        while bad_queue and attempts < MAX_REPLACEMENT_ATTEMPTS:
            attempts += 1
            to_fetch = min(max(REPLACEMENT_QUERY_LIMIT, len(bad_queue)), len(bad_queue) * 2)

            try:
                async with self.session_db.begin():
                    candidates = await self.product_repo.get_for_update_candidates(
                        category_id=bad_queue[0].category_id,
                        type_account_service=type_service_account,
                        limit=to_fetch,
                    )
                    if not candidates:
                        logger.debug(
                            "No replacement candidates on attempt %s for request %s",
                            attempts,
                            purchase_request_id,
                        )
                        return False

                    storage_ids = [c.account_storage.account_storage_id for c in candidates]
                    await self.storage_repo.update_status_by_ids(
                        storage_ids,
                        status=StorageStatus.RESERVED,
                    )
            except Exception as e:
                logger.exception("DB error while selecting/reserving replacement batch: %s", e)
                await asyncio.sleep(0.2)
                continue

            async def validate_candidate(candidate):
                async with sem:
                    try:
                        ok = await check_account_validity(
                            candidate.account_storage,
                            type_service_account,
                            StorageStatus.FOR_SALE,
                        )
                        return candidate, ok
                    except Exception as e:
                        logger.exception(
                            "Candidate validation exception for %s: %s",
                            getattr(candidate.account_storage, "account_storage_id", None),
                            e,
                        )
                        return candidate, False

            checks = await asyncio.gather(*[validate_candidate(c) for c in candidates], return_exceptions=False)

            valid_candidates = [c for c, ok in checks if ok]
            invalid_candidates = [c for c, ok in checks if not ok]

            try:
                if invalid_candidates:
                    await self._delete_accounts(invalid_candidates, type_service_account=type_service_account)

                async with self.session_db.begin():
                    while valid_candidates and bad_queue:
                        chosen = valid_candidates.pop(0)
                        bad = bad_queue.popleft()

                        await self.purchase_request_account_repo.update_account_storage_id(
                            purchase_request_id=purchase_request_id,
                            old_storage_id=bad.account_storage.account_storage_id,
                            new_storage_id=chosen.account_storage.account_storage_id,
                        )
                        valid_accounts.append(chosen)

                    if valid_candidates:
                        keep_ids = [c.account_storage.account_storage_id for c in valid_candidates]
                        await self.storage_repo.update_status_by_ids(
                            keep_ids,
                            status=StorageStatus.FOR_SALE,
                        )
            except Exception as e:
                logger.exception("DB error while applying candidate results: %s", e)
                try:
                    ids = [c.account_storage.account_storage_id for c in candidates]
                    await self.storage_repo.update_status_by_ids(
                        ids,
                        status=StorageStatus.FOR_SALE,
                    )
                    await self.session_db.commit()
                except Exception:
                    logger.exception("Failed to revert candidate statuses after error")
                await asyncio.sleep(0.2)
                continue

        if bad_queue:
            logger.error(
                "Could not find replacements for %d accounts after %d attempts (request %s)",
                len(bad_queue),
                attempts,
                purchase_request_id,
            )
            return False

        return valid_accounts

    async def finalize_purchase(self, user_id: int, data: StartPurchaseAccount) -> bool:
        """
        :exception Exception: При ошибках переносит обработку в cancel_purchase_request.
        :summary: Перемещает файлы в final, удаляет ProductAccounts, создаёт SoldAccounts/Purchases и логирует результат.
        """
        mapping: List[Tuple[str, str, str]] = []
        sold_account_ids: List[int] = []
        purchase_ids: List[int] = []
        account_movement: List[AccountsData] = []

        logger = get_logger(__name__)

        try:
            for account in data.product_accounts:
                orig = create_path_account(
                    status=StorageStatus.FOR_SALE,
                    type_account_service=data.type_service_account,
                    uuid=account.account_storage.storage_uuid,
                )
                final = create_path_account(
                    status=StorageStatus.BOUGHT,
                    type_account_service=data.type_service_account,
                    uuid=account.account_storage.storage_uuid,
                )
                temp = final + ".part"

                moved = await move_file(orig, temp)
                if not moved:
                    text = f"#Внимание \n\nАккаунт не найден/не удалось переместить: {orig}"
                    logger.exception(text)
                    event = EventSentLog(text=text)
                    await publish_event(event.model_dump(), "message.send_log")

                    await self.cancel_purchase_request(
                        user_id=user_id,
                        category_id=data.category_id,
                        mapping=mapping,
                        sold_account_ids=sold_account_ids,
                        purchase_ids=purchase_ids,
                        total_amount=data.total_amount,
                        purchase_request_id=data.purchase_request_id,
                        product_accounts=data.product_accounts,
                    )
                    return False

                shutil.rmtree(str(Path(orig).parent))
                mapping.append((orig, temp, final))

            async with self.session_db.begin():
                for account in data.product_accounts:
                    await self.product_repo.delete_by_account_id(account.account_id)

                    new_sold = await self.sold_repo.create_sold(
                        owner_id=user_id,
                        account_storage_id=account.account_storage.account_storage_id,
                    )
                    sold_account_ids.append(new_sold.sold_account_id)

                    for translate in data.translations_category:
                        await self.sold_trans_repo.create_translate(
                            sold_account_id=new_sold.sold_account_id,
                            lang=translate.lang,
                            name=translate.name,
                            description=translate.description,
                        )

                    new_purchase = await self.purchases_repo.create_purchase(
                        user_id=user_id,
                        account_storage_id=account.account_storage.account_storage_id,
                        product_type=ProductType.ACCOUNT,
                        original_price=data.original_price_one,
                        purchase_price=data.purchase_price_one,
                        cost_price=data.cost_price_one,
                        net_profit=data.purchase_price_one - data.cost_price_one,
                    )
                    purchase_ids.append(new_purchase.purchase_id)

                    await self.storage_repo.update(
                        account.account_storage.account_storage_id,
                        status=StorageStatus.BOUGHT,
                    )
                    account_movement.append(
                        AccountsData(
                            account_storage_id=account.account_storage.account_storage_id,
                            new_sold_account_id=new_sold.sold_account_id,
                            purchase_id=new_purchase.purchase_id,
                            cost_price=new_purchase.cost_price,
                            purchase_price=new_purchase.purchase_price,
                            net_profit=new_purchase.net_profit,
                        )
                    )

                await self.purchase_request_service.mark_request_status(
                    data.purchase_request_id,
                    "completed",
                )
                await self.purchase_request_service.mark_balance_holder_status(
                    data.purchase_request_id,
                    "used",
                )

            rename_fail = False
            for orig, temp, final in mapping:
                ok = await rename_file(temp, final)
                if not ok:
                    logger.exception("Failed to rename temp %s -> %s", temp, final)
                    rename_fail = True
                    break

            if rename_fail:
                await self.cancel_purchase_request(
                    user_id=user_id,
                    category_id=data.category_id,
                    mapping=mapping,
                    sold_account_ids=sold_account_ids,
                    purchase_ids=purchase_ids,
                    total_amount=data.total_amount,
                    purchase_request_id=data.purchase_request_id,
                    product_accounts=data.product_accounts,
                )
                return False

            await self.accounts_cache_filler.fill_sold_accounts_by_owner_id(user_id)
            for sid in sold_account_ids:
                await self.accounts_cache_filler.fill_sold_accounts_by_account_id(sid)
            for pid in data.product_accounts:
                await self.accounts_cache_filler.fill_product_account_by_account_id(pid.account_id)

            await self.categories_cache_filler.fill_need_category(data.category_id)

            if data.promo_code_id:
                event = NewActivatePromoCode(
                    promo_code_id=data.promo_code_id,
                    user_id=user_id,
                )
                await publish_event(event.model_dump(), "promo_code.activated")

            product_left = len(
                await self.product_repo.get_by_category_id(
                    data.category_id,
                    only_for_sale=True,
                )
            )
            new_purchase = NewPurchaseAccount(
                user_id=user_id,
                category_id=data.category_id,
                amount_purchase=data.total_amount,
                account_movement=account_movement,
                user_balance_before=data.user_balance_before,
                user_balance_after=data.user_balance_after,
                product_left=product_left,
            )
            await publish_event(new_purchase.model_dump(), "purchase.account")

            return True

        except Exception as e:
            logger.exception("Error in finalize_purchase: %s", e)
            event = EventSentLog(text=f"#Ошибка finalise_purchase: {e}")
            await publish_event(event.model_dump(), "message.send_log")

            await self.cancel_purchase_request(
                user_id=user_id,
                category_id=data.category_id,
                mapping=mapping,
                sold_account_ids=sold_account_ids,
                purchase_ids=purchase_ids,
                total_amount=data.total_amount,
                purchase_request_id=data.purchase_request_id,
                product_accounts=data.product_accounts,
            )
            return False

    async def cancel_purchase_request(
        self,
        user_id: int,
        category_id: int,
        mapping: List[Tuple[str, str, str]],
        sold_account_ids: List[int],
        purchase_ids: List[int],
        total_amount: int,
        purchase_request_id: int,
        product_accounts: List,
    ) -> None:
        """
        :exception UserNotFound: Если пользователь не найден.
        :summary: Восстанавливает деньги, статусы хранилищ и записи по продаже после отката.
        """
        logger = get_logger(__name__)
        user = None

        await self.purchase_cancel_service.return_files(mapping, logger)

        async with self.session_db.begin():
            user = await self.purchase_request_service.release_funds(user_id, total_amount)

            if purchase_ids:
                await self.purchases_repo.delete_by_ids(purchase_ids)
            if sold_account_ids:
                await self.sold_repo.delete_by_ids(sold_account_ids)

            try:
                account_storage_ids = [acc.account_storage.account_storage_id for acc in product_accounts]
                await self.storage_repo.update_status_by_ids(
                    account_storage_ids,
                    status=StorageStatus.FOR_SALE,
                )

                existing_ids = set(
                    await self.product_repo.get_existing_storage_ids(account_storage_ids)
                )
                for account in product_accounts:
                    aid = account.account_storage.account_storage_id
                    if aid not in existing_ids:
                        await self.product_repo.create_product(
                            category_id=account.category_id,
                            account_storage_id=aid,
                        )
            except Exception:
                logger.exception("Failed to restore account storage status")

            await self.purchase_cancel_service.mark_failed(purchase_request_id, logger)

        if user:
            await self.user_cache_repo.set(user, int(self.conf.redis_time_storage.user))

        await self.accounts_cache_filler.fill_sold_accounts_by_owner_id(user_id)
        await self.accounts_cache_filler.fill_product_accounts_by_category_id(category_id)
        for sid in sold_account_ids:
            await self.accounts_cache_filler.fill_sold_accounts_by_account_id(sid)
        for pid in product_accounts:
            await self.accounts_cache_filler.fill_product_account_by_account_id(pid.account_id)

        await self.categories_cache_filler.fill_need_category(category_id)

        logger.info("cancel_purchase_request_accounts finished for purchase %s", purchase_request_id)

    async def _delete_accounts(
        self,
        account_storage: List,
        type_service_account: AccountServiceType,
    ) -> None:
        if not account_storage:
            return

        category = await self.category_service.get_category_by_id(
            category_id=account_storage[0].category_id,
            return_not_show=True,
            language=self.conf.app.default_lang,
        )

        for bad_account in account_storage:
            bad_account.account_storage.status = StorageStatus.FOR_SALE
            await move_in_account(
                account=bad_account.account_storage,
                type_service_name=type_service_account,
                status=StorageStatus.DELETED,
            )

            try:
                await self.storage_repo.update(
                    bad_account.account_storage.account_storage_id,
                    status=StorageStatus.DELETED,
                    is_valid=False,
                    is_active=False,
                )
                await self.product_repo.delete_by_account_id(bad_account.account_id)
            except Exception:
                logger = get_logger(__name__)
                logger.exception(
                    "Error marking bad account deleted %s",
                    bad_account.account_storage.account_storage_id,
                )

            try:
                if category:
                    await self.deleted_service.create_deleted_account(
                        CreateDeletedAccountDTO(
                            account_storage_id=bad_account.account_storage.account_storage_id,
                            category_name=category.name,
                            description=category.description,
                        ),
                        make_commit=False,
                    )

                event = EventSentLog(
                    text=(
                        "\n#Невалидный_аккаунт \n"
                        "При покупке был найден невалидный аккаунт, он удален с продажи \n"
                        "Данные об аккаунте: \n"
                        f"storage_account_id: {bad_account.account_storage.account_storage_id}\n"
                        f"Себестоимость: {category.cost_price if category else 'unknown'}\n"
                    ),
                    log_lvl=LogLevel.INFO,
                )
                await publish_event(event.model_dump(), "message.send_log")
            except Exception:
                logger = get_logger(__name__)
                logger.exception(
                    "Failed to log deleted account %s",
                    bad_account.account_storage.account_storage_id,
                )

        await self.session_db.commit()
