import asyncio
import shutil
import uuid
from collections import deque
from logging import Logger
from pathlib import Path
from typing import List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.crypto.crypto_context import CryptoProvider
from src.application.events.publish_event_handler import PublishEventHandler
from src.application.products.universals.universal_products import UniversalProduct
from src.application.products.universals.use_cases import ValidationsUniversalProducts
from src.infrastructure.files.path_builder import PathBuilder
from src.config import Config
from src.database.models.categories import StorageStatus, ProductType
from src.database.models.categories.product_universal import UniversalStorage, UniversalStorageTranslation
from src.exceptions.business import NotEnoughProducts
from src.exceptions.domain import UniversalProductNotFound
from src.models.read_models import ProductUniversalFull
from src.models.read_models.categories.purshanse_schem import StartPurchaseUniversalOne, StartPurchaseUniversal
from src.models.read_models.events.purchase import UniversalProductData, NewPurchaseUniversal
from src.repository.redis import UsersCacheRepository
from src.infrastructure.files.file_system import move_file, copy_file, rename_file
from src.application.models.categories.categories_cache_filler_service import CategoriesCacheFillerService
from src.application.models.categories.category_service import CategoryService
from src.application.models.products.universal.universal_cache_filler_service import UniversalCacheFillerService
from src.application.models.products.universal.universal_deleted_service import UniversalDeletedService
from src.models.create_models.universal import CreateDeletedUniversalDTO
from src.application.models.purchases.general.purchase_cancel_service import PurchaseCancelService
from src.application.models.purchases.general.purchase_request_service import PurchaseRequestService
from src.application.models.purchases.general.purchase_validation_service import PurchaseValidationService
from src.repository.database.categories import (
    ProductUniversalRepository,
    UniversalStorageRepository,
    PurchaseRequestUniversalRepository,
    SoldUniversalRepository,
    PurchasesRepository,
)

SEMAPHORE_LIMIT_UNIVERSAL = 50
MAX_REPLACEMENT_ATTEMPTS = 3
REPLACEMENT_QUERY_LIMIT = 5


class UniversalPurchaseService:

    def __init__(
        self,
        validation_service: PurchaseValidationService,
        purchase_request_service: PurchaseRequestService,
        purchase_cancel_service: PurchaseCancelService,
        product_repo: ProductUniversalRepository,
        storage_repo: UniversalStorageRepository,
        purchase_request_universal_repo: PurchaseRequestUniversalRepository,
        sold_repo: SoldUniversalRepository,
        purchases_repo: PurchasesRepository,
        deleted_service: UniversalDeletedService,
        category_service: CategoryService,
        cache_filler: UniversalCacheFillerService,
        categories_cache_filler: CategoriesCacheFillerService,
        user_cache_repo: UsersCacheRepository,
        publish_event_handler: PublishEventHandler,
        path_builder: PathBuilder,
        crypto_provider: CryptoProvider,
        validations_universal_products: ValidationsUniversalProducts,
        universal_product: UniversalProduct,
        conf: Config,
        logger: Logger,
        session_db: AsyncSession,
    ):
        self.validation_service = validation_service
        self.purchase_request_service = purchase_request_service
        self.purchase_cancel_service = purchase_cancel_service
        self.product_repo = product_repo
        self.storage_repo = storage_repo
        self.purchase_request_universal_repo = purchase_request_universal_repo
        self.sold_repo = sold_repo
        self.purchases_repo = purchases_repo
        self.deleted_service = deleted_service
        self.category_service = category_service
        self.cache_filler = cache_filler
        self.categories_cache_filler = categories_cache_filler
        self.user_cache_repo = user_cache_repo
        self.publish_event_handler = publish_event_handler
        self.path_builder = path_builder
        self.crypto_provider = crypto_provider
        self.validations_universal_products = validations_universal_products
        self.universal_product = universal_product
        self.conf = conf
        self.logger = logger
        self.session_db = session_db

    async def _reset_session_transaction(self) -> None:
        if self.session_db.in_transaction():
            await self.session_db.rollback()

    async def start_purchase(
        self,
        user_id: int,
        category_id: int,
        quantity_products: int,
        promo_code_id: int | None,
        language: str,
    ) -> StartPurchaseUniversal | StartPurchaseUniversalOne:
        """
        :exception NotEnoughProducts: Если товаров недостаточно.
        :exception UniversalProductNotFound: Если товар не найден.
        :exception CategoryNotFound: Если категория не найдена.
        :exception UserNotFound: Если пользователь не найден.
        :exception NotEnoughMoney: Если недостаточно средств.
        :summary: Проверяет категорию/баланс, создаёт заявку и резервирует нужные товары.
        """
        result_check = await self.validation_service.check_category_and_money(
            user_id,
            category_id,
            quantity_products,
            promo_code_id,
        )

        if self.session_db.in_transaction():
            await self.session_db.rollback()

        if result_check.category.reuse_product:
            return await self._start_purchase_one(
                result_check,
                user_id,
                promo_code_id,
                quantity_products,
                category_id,
            )

        return await self._start_purchase_different(
            result_check,
            user_id,
            promo_code_id,
            quantity_products,
            category_id,
            language,
        )

    async def _start_purchase_one(
        self,
        result_check,
        user_id: int,
        promo_code_id: int | None,
        quantity_products: int,
        category_id: int,
    ) -> StartPurchaseUniversalOne:
        """
        :exception UniversalProductNotFound: Если товар не найден.
        :summary: Подтверждает покупку одного продукта, фиксируя заявку и списание средств.
        """
        product_full = await self.product_repo.get_full_by_category(
            category_id=category_id,
            language=self.conf.app.default_lang,
            only_for_sale=True,
        )
        if not product_full or not product_full[0]:
            raise UniversalProductNotFound()

        await self._reset_session_transaction()
        async with self.session_db.begin():
            new_purchase_request = await self.purchase_request_service.create_request(
                user_id=user_id,
                promo_code_id=promo_code_id,
                quantity=quantity_products,
                total_amount=result_check.final_total,
            )

            user = await self.purchase_request_service.hold_funds(
                user_id=user_id,
                purchase_request_id=new_purchase_request.purchase_request_id,
                amount=result_check.final_total,
            )

        await self.user_cache_repo.set(user, int(self.conf.redis_time_storage.user.total_seconds()))

        return StartPurchaseUniversalOne(
            purchase_request_id=new_purchase_request.purchase_request_id,
            category_id=category_id,
            promo_code_id=promo_code_id,
            full_product=product_full[0],
            translations_category=result_check.translations_category,
            original_price_one=result_check.category.price,
            purchase_price_one=(
                result_check.final_total // quantity_products
                if result_check.final_total > 0
                else result_check.final_total
            ),
            cost_price_one=result_check.category.cost_price,
            total_amount=result_check.final_total,
            user_balance_before=result_check.user_balance_before,
            user_balance_after=user.balance,
            quantity_products=quantity_products,
        )

    async def _start_purchase_different(
        self,
        result_check,
        user_id: int,
        promo_code_id: int | None,
        quantity_products: int,
        category_id: int,
        language: str,
    ) -> StartPurchaseUniversal:
        """
        :exception NotEnoughProducts: Если товаров недостаточно.
        :summary: Резервирует `quantity_products`, создаёт PurchaseRequestUniversal и фиксирует списание.
        """
        await self._reset_session_transaction()
        async with self.session_db.begin():
            new_purchase_request = await self.purchase_request_service.create_request(
                user_id=user_id,
                promo_code_id=promo_code_id,
                quantity=quantity_products,
                total_amount=result_check.final_total,
            )

            reserved_products = await self.product_repo.get_for_update_by_category(
                category_id=category_id,
                limit=quantity_products,
                status=StorageStatus.FOR_SALE,
            )
            if len(reserved_products) < quantity_products:
                raise NotEnoughProducts("У данной категории недостаточно продуктов")

            storage_ids = [prod.storage.universal_storage_id for prod in reserved_products]
            await self.storage_repo.update_status_by_ids(
                storage_ids,
                status=StorageStatus.RESERVED,
            )

            await self.purchase_request_universal_repo.create_many(
                purchase_request_id=new_purchase_request.purchase_request_id,
                universal_storage_ids=storage_ids,
            )

            user = await self.purchase_request_service.hold_funds(
                user_id=user_id,
                purchase_request_id=new_purchase_request.purchase_request_id,
                amount=result_check.final_total,
            )

        full_reserved_products = [
            ProductUniversalFull.from_orm_model(product, language)
            for product in reserved_products
        ]

        await self.user_cache_repo.set(user, int(self.conf.redis_time_storage.user.total_seconds()))
        await self.cache_filler.fill_product_universal_by_category_id(category_id)
        for prod_id in [product.product_universal_id for product in reserved_products]:
            await self.cache_filler.fill_product_universal_by_product_id(prod_id)
        await self.categories_cache_filler.fill_need_category(category_id)

        return StartPurchaseUniversal(
            purchase_request_id=new_purchase_request.purchase_request_id,
            category_id=category_id,
            promo_code_id=promo_code_id,
            media_type=full_reserved_products[0].universal_storage.media_type,
            full_reserved_products=full_reserved_products,
            translations_category=result_check.translations_category,
            original_price_one=result_check.category.price,
            purchase_price_one=(
                result_check.final_total // quantity_products
                if result_check.final_total > 0
                else result_check.final_total
            ),
            cost_price_one=result_check.category.cost_price,
            total_amount=result_check.final_total,
            user_balance_before=result_check.user_balance_before,
            user_balance_after=user.balance,
        )

    async def verify_reserved_universal_one(self, product_universal: ProductUniversalFull) -> bool:
        """
        Проверяет файл/описание по DEK; при ошибке перемещает в удалённые и логирует.
        """
        crypto = self.crypto_provider.get()
        result_check = await self.validations_universal_products.check_valid_universal_product(
            product=product_universal,
            status=StorageStatus.FOR_SALE,
        )
        if not result_check:
            await self._delete_universal([product_universal])
            category = await self.category_service.get_category_by_id(
                product_universal.category_id,
                return_not_show=True,
                language=self.conf.app.default_lang,
            )
            await self.publish_event_handler.send_log(
                text=(
                    "\n#Невалидный_продукт \n"
                    "При покупке был найден невалидный универсальный продукт, он удален с продажи \n"
                    "Категория теперь не отображается! \n"
                    f"ID категории: {category.category_id if category else 'unknown'}\n"
                    f"Имя категории: {category.name if category else 'unknown'}\n"
                    f"Описание внутри категории: {category.description if category else 'unknown'}\n"
                )
            )

        return result_check

    async def verify_reserved_universal_different(
        self,
        reserved_products: List[ProductUniversalFull],
        purchase_request_id: int,
    ) -> List[ProductUniversalFull] | bool:
        """
        Проверяет каждый продукт, удаляет невалидные и подставляет кандидатов через PurchaseRequestUniversal.
        """
        if not reserved_products:
            return False

        crypto = self.crypto_provider.get()
        sem = asyncio.Semaphore(SEMAPHORE_LIMIT_UNIVERSAL)

        async def validate_slot(product: ProductUniversalFull):
            async with sem:
                return product, await self.validations_universal_products.check_valid_universal_product(
                    product,
                    StorageStatus.FOR_SALE,
                )

        initial_checks = await asyncio.gather(*[validate_slot(p) for p in reserved_products], return_exceptions=True)

        invalid_products: list[ProductUniversalFull] = []
        valid_products: list[ProductUniversalFull] = []
        for res in initial_checks:
            if isinstance(res, Exception):
                self.logger.exception("Validation task exception: %s", res)
                return False
            prod, ok = res
            if ok:
                valid_products.append(prod)
            else:
                invalid_products.append(prod)

        if not invalid_products:
            return valid_products

        await self._delete_universal(invalid_products)

        bad_queue = deque(invalid_products)
        attempts = 0

        while bad_queue and attempts < MAX_REPLACEMENT_ATTEMPTS:
            attempts += 1
            to_fetch = min(max(REPLACEMENT_QUERY_LIMIT, len(bad_queue)), len(bad_queue) * 2)

            try:
                await self._reset_session_transaction()
                async with self.session_db.begin():
                    candidates = await self.product_repo.get_for_update_candidates(
                        category_id=bad_queue[0].category_id,
                        limit=to_fetch,
                    )
                    if not candidates:
                        self.logger.debug(
                            "No replacement candidates on attempt %s for request %s",
                            attempts,
                            purchase_request_id,
                        )
                        return False

                    storage_ids = [c.storage.universal_storage_id for c in candidates]
                    await self.storage_repo.update_status_by_ids(
                        storage_ids,
                        status=StorageStatus.RESERVED,
                    )
            except Exception as e:
                self.logger.exception("DB error while selecting/reserving replacement batch: %s", e)
                await asyncio.sleep(0.2)
                continue

            candidates_full = [
                ProductUniversalFull.from_orm_model(c, self.conf.app.default_lang)
                for c in candidates
            ]

            async def validate_candidate(cand: ProductUniversalFull):
                async with sem:
                    try:
                        ok = await self.validations_universal_products.check_valid_universal_product(
                            cand,
                            StorageStatus.FOR_SALE,
                        )
                        return cand, ok
                    except Exception as e:
                        self.logger.exception("Candidate validation exception: %s", e)
                        return cand, False

            checks = await asyncio.gather(*[validate_candidate(c) for c in candidates_full], return_exceptions=False)

            valid_candidates = [c for c, ok in checks if ok]
            invalid_candidates = [c for c, ok in checks if not ok]

            try:
                if invalid_candidates:
                    await self._delete_universal(invalid_candidates)

                await self._reset_session_transaction()
                async with self.session_db.begin():
                    while valid_candidates and bad_queue:
                        chosen = valid_candidates.pop(0)
                        bad = bad_queue.popleft()

                        await self.purchase_request_universal_repo.update_universal_storage_id(
                            purchase_request_id=purchase_request_id,
                            old_storage_id=bad.universal_storage.universal_storage_id,
                            new_storage_id=chosen.universal_storage.universal_storage_id,
                        )
                        valid_products.append(chosen)

                    if valid_candidates:
                        keep_ids = [c.universal_storage.universal_storage_id for c in valid_candidates]
                        await self.storage_repo.update_status_by_ids(
                            keep_ids,
                            status=StorageStatus.FOR_SALE,
                        )
            except Exception as e:
                self.logger.exception("DB error while applying candidate results: %s", e)
                try:
                    ids = [c.storage.universal_storage_id for c in candidates]
                    await self.storage_repo.update_status_by_ids(
                        ids,
                        status=StorageStatus.FOR_SALE,
                    )
                    await self.session_db.commit()
                except Exception:
                    self.logger.exception("Failed to revert candidate statuses after error")
                await asyncio.sleep(0.2)
                continue

        if bad_queue:
            self.logger.error(
                "Could not find replacements for %d products after %d attempts (request %s)",
                len(bad_queue),
                attempts,
                purchase_request_id,
            )
            return False

        return valid_products

    async def finalize_purchase_different(self, user_id: int, data: StartPurchaseUniversal) -> bool:
        """
        :summary: Перемещает файлы, сохраняет SoldUniversal/Purchases и фиксирует статусы.
        :return: True при успехе и False при откате.
        """
        """
        Переносит файлы в final, создаёт SoldUniversal + Purchases и обновляет _redis + статусы.
        :return: True при успехе, False при откате.
        """
        mapping: List[Tuple[str, str, str]] = []
        sold_product_ids: List[int] = []
        purchase_ids: List[int] = []
        product_movement: List[UniversalProductData] = []

        try:
            for product in data.full_reserved_products:
                if not product.universal_storage.original_filename:
                    continue

                orig = self.path_builder.build_path_universal_storage(
                    status=StorageStatus.FOR_SALE,
                    uuid=product.universal_storage.storage_uuid,
                )
                final = self.path_builder.build_path_universal_storage(
                    status=StorageStatus.BOUGHT,
                    uuid=product.universal_storage.storage_uuid,
                )
                temp = final + ".part"

                moved = await move_file(orig, temp)
                if not moved:
                    text = f"#Внимание \n\nПродукт не найден/не удалось переместить: {orig}"
                    self.logger.exception(text)
                    await self.publish_event_handler.send_log(text)

                    await self.cancel_purchase_different(
                        user_id=user_id,
                        category_id=data.category_id,
                        mapping=mapping,
                        sold_universal_ids=sold_product_ids,
                        purchase_ids=purchase_ids,
                        total_amount=data.total_amount,
                        purchase_request_id=data.purchase_request_id,
                        product_universal=data.full_reserved_products,
                    )
                    return False

                shutil.rmtree(str(Path(orig).parent))
                mapping.append((orig, temp, final))

            await self._reset_session_transaction()
            async with self.session_db.begin():
                for product in data.full_reserved_products:
                    await self.product_repo.delete(product.product_universal_id)

                    new_sold = await self.sold_repo.create_sold(
                        owner_id=user_id,
                        universal_storage_id=product.universal_storage_id,
                    )
                    sold_product_ids.append(new_sold.sold_universal_id)

                    new_purchase = await self.purchases_repo.create_purchase(
                        user_id=user_id,
                        universal_storage_id=product.universal_storage_id,
                        product_type=ProductType.UNIVERSAL,
                        original_price=data.original_price_one,
                        purchase_price=data.purchase_price_one,
                        cost_price=data.cost_price_one,
                        net_profit=data.purchase_price_one - data.cost_price_one,
                    )
                    purchase_ids.append(new_purchase.purchase_id)

                    await self.storage_repo.update(
                        product.universal_storage_id,
                        status=StorageStatus.BOUGHT,
                    )

                    product_movement.append(
                        UniversalProductData(
                            universal_storage_id=product.universal_storage_id,
                            sold_universal_id=new_sold.sold_universal_id,
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
                    self.logger.exception("Failed to rename temp %s -> %s", temp, final)
                    rename_fail = True
                    break

            if rename_fail:
                await self.cancel_purchase_different(
                    user_id=user_id,
                    category_id=data.category_id,
                    mapping=mapping,
                    sold_universal_ids=sold_product_ids,
                    purchase_ids=purchase_ids,
                    total_amount=data.total_amount,
                    purchase_request_id=data.purchase_request_id,
                    product_universal=data.full_reserved_products,
                )
                return False

            await self.cache_filler.fill_product_universal_by_category_id(data.category_id)
            await self.cache_filler.fill_sold_universal_by_owner_id(user_id)
            for product in data.full_reserved_products:
                await self.cache_filler.fill_product_universal_by_product_id(product.product_universal_id)
            for sold_id in sold_product_ids:
                await self.cache_filler.fill_sold_universal_by_universal_id(sold_id)

            await self.categories_cache_filler.fill_need_category(data.category_id)

            if data.promo_code_id:
                await self.publish_event_handler.promo_code_activated(
                    promo_code_id=data.promo_code_id,
                    user_id=user_id,
                )

            product_left = len(await self.product_repo.get_by_category_for_sale(data.category_id))

            await self.publish_event_handler.new_purchase_universal(
                data=NewPurchaseUniversal(
                    user_id=user_id,
                    category_id=data.category_id,
                    amount_purchase=data.total_amount,
                    product_movement=product_movement,
                    user_balance_before=data.user_balance_before,
                    user_balance_after=data.user_balance_after,
                    product_left=product_left,
                )
            )
            return True

        except Exception as e:
            self.logger.exception("Error in finalize_purchase: %s", e)
            await self.publish_event_handler.send_log(text=f"#Ошибка finalize_purchase_universal_different: {e}")

            await self.cancel_purchase_different(
                user_id=user_id,
                category_id=data.category_id,
                mapping=mapping,
                sold_universal_ids=sold_product_ids,
                purchase_ids=purchase_ids,
                total_amount=data.total_amount,
                purchase_request_id=data.purchase_request_id,
                product_universal=data.full_reserved_products,
            )
            return False

    async def finalize_purchase_one(self, user_id: int, data: StartPurchaseUniversalOne) -> bool:
        """
        Копирует storage, создаёт записи и сбрасывает результат покупки.
        """
        created_storages: list[UniversalStorage] = []
        sold_ids: list[int] = []
        purchase_ids: list[int] = []
        product_movement: list[UniversalProductData] = []

        translations = list(getattr(data.full_product.universal_storage, "translations", []) or [])

        try:
            prepared = await self._copy_universal_storage_prepare(
                src_storage=data.full_product.universal_storage,
                translations=translations,
                new_status=StorageStatus.BOUGHT,
                quantity=data.quantity_products,
            )

            await self._reset_session_transaction()
            async with self.session_db.begin():
                for _, new_storage, trans_list in prepared:
                    self.session_db.add(new_storage)
                    await self.session_db.flush()

                    for tr in trans_list:
                        tr.universal_storage_id = new_storage.universal_storage_id
                        self.session_db.add(tr)

                    new_sold = await self.sold_repo.create_sold(
                        owner_id=user_id,
                        universal_storage_id=new_storage.universal_storage_id,
                    )
                    new_purchase = await self.purchases_repo.create_purchase(
                        user_id=user_id,
                        universal_storage_id=new_storage.universal_storage_id,
                        product_type=ProductType.UNIVERSAL,
                        original_price=data.original_price_one,
                        purchase_price=data.purchase_price_one,
                        cost_price=data.cost_price_one,
                        net_profit=data.purchase_price_one - data.cost_price_one,
                    )

                    await self.purchase_request_universal_repo.create_many(
                        purchase_request_id=data.purchase_request_id,
                        universal_storage_ids=[new_storage.universal_storage_id],
                    )

                    created_storages.append(new_storage)
                    sold_ids.append(new_sold.sold_universal_id)
                    purchase_ids.append(new_purchase.purchase_id)

                    product_movement.append(
                        UniversalProductData(
                            universal_storage_id=new_storage.universal_storage_id,
                            sold_universal_id=new_sold.sold_universal_id,
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

            await self.cache_filler.fill_sold_universal_by_owner_id(user_id)
            for sold_id in sold_ids:
                await self.cache_filler.fill_sold_universal_by_universal_id(sold_id)
            await self.cache_filler.fill_product_universal_by_category_id(data.category_id)
            await self.cache_filler.fill_product_universal_by_product_id(data.full_product.product_universal_id)
            await self.categories_cache_filler.fill_need_category(data.category_id)

            if data.promo_code_id:
                await self.publish_event_handler.promo_code_activated(
                    promo_code_id=data.promo_code_id,
                    user_id=user_id,
                )

            await self.publish_event_handler.new_purchase_universal(
                data=NewPurchaseUniversal(
                    user_id=user_id,
                    category_id=data.category_id,
                    amount_purchase=data.total_amount,
                    product_movement=product_movement,
                    user_balance_before=data.user_balance_before,
                    user_balance_after=data.user_balance_after,
                    product_left="Бесконечно ...",
                )
            )

            return True

        except Exception as e:
            self.logger.exception("Исключение при покупки универсального товара с reuse_product")
            await self.cancel_purchase_one(
                user_id=user_id,
                category_id=data.category_id,
                paths_created_storage=[
                    self.path_builder.build_path_universal_storage(status=StorageStatus.BOUGHT, uuid=s.storage_uuid)
                    for s in created_storages if s.original_filename
                ],
                sold_universal_ids=sold_ids,
                storage_universal_ids=[s.universal_storage_id for s in created_storages if s.universal_storage_id],
                purchase_ids=purchase_ids,
                total_amount=data.total_amount,
                purchase_request_id=data.purchase_request_id,
                product_universal=data.full_product,
            )
            return False

    async def cancel_purchase_different(
        self,
        user_id: int,
        category_id: int,
        mapping: List[Tuple[str, str, str]],
        sold_universal_ids: List[int],
        purchase_ids: List[int],
        total_amount: int,
        purchase_request_id: int,
        product_universal: List[ProductUniversalFull],
    ) -> None:
        """
        :exception UserNotFound: Если пользователь не найден.
        :summary: Возвращает средства и откатывает записи/статусы, как в `cancel_purchase_universal_different`.
        """
        user = None

        await self.purchase_cancel_service.return_files(mapping)

        await self._reset_session_transaction()
        async with self.session_db.begin():
            user = await self.purchase_request_service.release_funds(user_id, total_amount)

            if purchase_ids:
                await self.purchases_repo.delete_by_ids(purchase_ids)
            if sold_universal_ids:
                await self.sold_repo.delete_by_ids(sold_universal_ids)

            try:
                storage_ids = [p.universal_storage_id for p in product_universal]
                await self.storage_repo.update_status_by_ids(
                    storage_ids,
                    status=StorageStatus.FOR_SALE,
                )

                existing_ids = set(await self.product_repo.get_existing_storage_ids(storage_ids))
                for prod in product_universal:
                    if prod.universal_storage_id not in existing_ids:
                        await self.product_repo.create_product(
                            category_id=prod.category_id,
                            universal_storage_id=prod.universal_storage_id,
                        )
            except Exception:
                self.logger.exception("Failed to restore universal storage status")

            await self.purchase_cancel_service.mark_failed(purchase_request_id)

        if user:
            await self.user_cache_repo.set(user, int(self.conf.redis_time_storage.user.total_seconds()))

        await self.cache_filler.fill_product_universal_by_category_id(category_id)
        await self.cache_filler.fill_sold_universal_by_owner_id(user_id)
        for prod in product_universal:
            await self.cache_filler.fill_product_universal_by_product_id(prod.product_universal_id)
        for sold_id in sold_universal_ids:
            await self.cache_filler.fill_sold_universal_by_universal_id(sold_id)

        await self.categories_cache_filler.fill_need_category(category_id)

    async def cancel_purchase_one(
        self,
        user_id: int,
        category_id: int,
        paths_created_storage: List[str],
        sold_universal_ids: List[int],
        storage_universal_ids: List[int],
        purchase_ids: List[int],
        total_amount: int,
        purchase_request_id: int,
        product_universal: ProductUniversalFull,
    ) -> None:
        """
        :exception UserNotFound: Если пользователь не найден.
        :summary: Удаляет временные файлы, откатывает записи и возвращает деньги.
        """
        user = None

        for path in paths_created_storage:
            try:
                path_obj = Path(path)
                if path_obj.exists():
                    if path_obj.is_dir():
                        shutil.rmtree(path_obj, ignore_errors=True)
                    else:
                        path_obj.unlink(missing_ok=True)
            except Exception:
                self.logger.exception("Failed to remove created storage path %s", path)

        await self._reset_session_transaction()
        async with self.session_db.begin():
            user = await self.purchase_request_service.release_funds(user_id, total_amount)

            if purchase_ids:
                await self.purchases_repo.delete_by_ids(purchase_ids)
            if sold_universal_ids:
                await self.sold_repo.delete_by_ids(sold_universal_ids)
            if storage_universal_ids:
                await self.storage_repo.delete_by_ids(storage_universal_ids)

            await self.purchase_cancel_service.mark_failed(purchase_request_id)

        if user:
            await self.user_cache_repo.set(user, int(self.conf.redis_time_storage.user.total_seconds()))

        await self.cache_filler.fill_sold_universal_by_owner_id(user_id)
        for sold_id in sold_universal_ids:
            await self.cache_filler.fill_sold_universal_by_universal_id(sold_id)
        await self.cache_filler.fill_product_universal_by_category_id(category_id)
        await self.cache_filler.fill_product_universal_by_product_id(product_universal.product_universal_id)
        await self.categories_cache_filler.fill_need_category(category_id)

    async def _delete_universal(self, universal_product: List[ProductUniversalFull]) -> None:
        """
        Помечает переводы как удалённые: перемещает файлы, обновляет статусы и пишет удалённые записи.
        """
        if not universal_product:
            return

        category = await self.category_service.get_category_by_id(
            category_id=universal_product[0].category_id,
            return_not_show=True,
            language=self.conf.app.default_lang,
        )

        for bad_prod in universal_product:
            await self.universal_product.move_universal_storage(
                storage=bad_prod.universal_storage,
                new_status=StorageStatus.DELETED,
            )

            try:
                await self.storage_repo.update(
                    bad_prod.universal_storage.universal_storage_id,
                    status=StorageStatus.DELETED,
                    is_active=False,
                )
                await self.product_repo.delete(bad_prod.product_universal_id)
            except Exception:
                self.logger.exception(
                    "Error marking bad product deleted %s",
                    bad_prod.universal_storage.universal_storage_id,
                )

            try:
                await self.deleted_service.create_deleted_universal(
                    CreateDeletedUniversalDTO(
                        universal_storage_id=bad_prod.universal_storage.universal_storage_id
                    ),
                    make_commit=False,
                )

                await self.publish_event_handler.send_log(
                    text=(
                        "\n#Невалидный_продукт \n"
                        "При покупке был найден невалидный универсальный продукт, он удален с продажи \n"
                        "Данные об продукте: \n"
                        f"universal_storage_id: {bad_prod.universal_storage.universal_storage_id}\n"
                        f"Себестоимость: {category.cost_price if category else 'unknown'}\n"
                    )
                )
            except Exception:
                self.logger.exception(
                    "Failed to log deleted product %s",
                    bad_prod.universal_storage.universal_storage_id,
                )

        await self.session_db.commit()

    async def _copy_universal_storage_prepare(
        self,
        src_storage,
        translations: List[UniversalStorageTranslation],
        new_status: StorageStatus,
        quantity: int = 1,
    ) -> List[Tuple[Path, UniversalStorage, List[UniversalStorageTranslation]]]:
        prepared = []
        for _ in range(quantity):
            new_uuid = str(uuid.uuid4())
            final_path = None
            if src_storage.original_filename:
                src_path = self.path_builder.build_path_universal_storage(
                    status=StorageStatus.FOR_SALE,
                    uuid=src_storage.storage_uuid,
                )
                final_path = self.path_builder.build_path_universal_storage(
                    status=new_status,
                    uuid=new_uuid,
                    as_path=True,
                )
                final_path.parent.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(
                    copy_file,
                    src=src_path,
                    dst_dir=str(final_path.parent),
                    file_name=final_path.name,
                )

            storage = UniversalStorage(
                storage_uuid=new_uuid,
                original_filename=src_storage.original_filename,
                encrypted_tg_file_id=src_storage.encrypted_tg_file_id,
                encrypted_tg_file_id_nonce=src_storage.encrypted_tg_file_id_nonce,
                checksum=src_storage.checksum,
                encrypted_key=src_storage.encrypted_key,
                encrypted_key_nonce=src_storage.encrypted_key_nonce,
                key_version=src_storage.key_version,
                encryption_algo=src_storage.encryption_algo,
                status=new_status,
                media_type=src_storage.media_type,
                is_active=src_storage.is_active,
            )

            new_translations = [
                UniversalStorageTranslation(
                    lang=t.lang,
                    name=t.name,
                    encrypted_description=t.encrypted_description,
                    encrypted_description_nonce=t.encrypted_description_nonce,
                )
                for t in translations
            ]
            prepared.append((final_path, storage, new_translations))

        return prepared
