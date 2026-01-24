import asyncio
import shutil
import uuid
from pathlib import Path
from typing import List, Tuple

from sqlalchemy import update, delete

from src.bot_actions.messages import send_log
from src.broker.producer import publish_event
from src.config import get_config
from src.services.database.categories.actions.products.universal.actions_get import \
    get_product_universal_by_category_id, get_translations_universal_storage
from src.services.database.categories.actions.purchases.universal.cancel import cancel_purchase_universal_one, \
    cancel_purchase_universal_different
from src.services.database.categories.events.schemas import UniversalProductData, \
    NewPurchaseUniversal
from src.services.database.categories.models import PurchaseRequests
from src.services.database.categories.models import Purchases
from src.services.database.categories.models.main_category_and_product import ProductType
from src.services.database.categories.models.product_universal import UniversalStorageStatus, ProductUniversal, \
    SoldUniversal, UniversalStorage, UniversalStorageTranslation, PurchaseRequestUniversal
from src.services.database.categories.models.shemas.product_universal_schem import ProductUniversalFull, \
    UniversalStoragePydantic
from src.services.database.categories.models.shemas.purshanse_schem import StartPurchaseUniversal, \
    StartPurchaseUniversalOne
from src.services.database.core.database import get_db
from src.services.database.discounts.events import NewActivatePromoCode
from src.services.database.users.models.models_users import BalanceHolder
from src.services.filesystem.account_actions import rename_file
from src.services.filesystem.actions import move_file, copy_file
from src.services.products.universals.actions import create_path_universal_storage
from src.services.redis.filling.filling_universal import filling_sold_universal_by_owner_id, \
    filling_product_universal_by_category, filling_universal_by_product_id, filling_sold_universal_by_universal_id
from src.utils.core_logger import get_logger


async def _filling_redis_universal(
    user_id: int,
    full_reserved_products: List[ProductUniversalFull],
    sold_product_ids: List[int]
):
    """Заполнит redis необходимыми ключами для универсальных товаров"""
    await filling_product_universal_by_category()
    await filling_sold_universal_by_owner_id(user_id)
    for product in full_reserved_products:
        await filling_universal_by_product_id(product.product_universal_id)
    for sold in sold_product_ids:
        await filling_sold_universal_by_universal_id(sold)


async def _publish_purchase_universal(
    user_id: int,
    product_left: int | str,
    data: StartPurchaseUniversal | StartPurchaseUniversalOne,
    product_movement:  list[UniversalProductData]
):
    # Публикуем событие об активации промокода (если был)
    if data.promo_code_id:
        event = NewActivatePromoCode(
            promo_code_id=data.promo_code_id,
            user_id=user_id
        )
        await publish_event(event.model_dump(), 'promo_code.activated')

    new_purchase = NewPurchaseUniversal(
        user_id=user_id,
        category_id=data.category_id,
        amount_purchase=data.total_amount,
        product_movement=product_movement,
        user_balance_before=data.user_balance_before,
        user_balance_after=data.user_balance_after,
        product_left=product_left
    )
    await publish_event(new_purchase.model_dump(), 'purchase.universal')


async def _copy_universal_storage_prepare(
    src_storage: UniversalStoragePydantic,
    translations: List[UniversalStorageTranslation],
    new_status: UniversalStorageStatus,
    quantity: int = 1,
) -> List[Tuple[Path, UniversalStorage, List[UniversalStorageTranslation]]]:
    """
    Подготовить (скопировать) файловую часть: создает копии файлов на FS и возвращает
    список подготовленных данных для вставки в БД.
    Этот шаг выполняется ВНЕ транзакции.
    """
    prepared = []
    for _ in range(quantity):
        new_uuid = str(uuid.uuid4())
        final_path = None
        if src_storage.file_path:
            # создаём целевой путь (полный), но не трогаем БД
            src_path = create_path_universal_storage(
                status=src_storage.status,
                uuid=src_storage.storage_uuid,
            )
            final_path = create_path_universal_storage(
                status=new_status,
                uuid=new_uuid,
                return_path_obj=True
            )
            # ensure dir exists
            final_path.parent.mkdir(parents=True, exist_ok=True)

            # copy file (blocking or async wrapper)
            await asyncio.to_thread(
                copy_file,
                src=src_path,
                dst_dir=str(final_path.parent),
                file_name=final_path.name
            )


        storage = UniversalStorage(
            storage_uuid=new_uuid,
            file_path=str(final_path) if final_path else None,
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

        translations = [
            UniversalStorageTranslation(
                lang=t.lang,
                name=t.name,
                encrypted_description=t.encrypted_description,
                encrypted_description_nonce=t.encrypted_description_nonce,
            )
            for t in translations
        ]
        prepared.append((final_path, storage, translations))
    return prepared


async def finalize_purchase_universal_one(user_id: int, data: StartPurchaseUniversalOne) -> bool:
    # подготовка (IO) — копируем файлы в final paths до транзакции
    created_storages = []
    sold_ids = []
    purchase_ids = []
    product_movement = []

    translations = await get_translations_universal_storage(data.full_product.universal_storage_id)

    try:
        prepared = await _copy_universal_storage_prepare(
            src_storage=data.full_product.universal_storage,
            translations=translations,
            new_status=UniversalStorageStatus.BOUGHT,
            quantity=data.quantity_products
        )

        async with get_db() as session:
            async with session.begin():
                for final_path, new_storage, translations in prepared:
                    session.add(new_storage)
                    await session.flush()  # чтобы получить new_storage.universal_storage_id

                    # добавление перевода
                    for tr in translations:
                        tr.universal_storage_id = new_storage.universal_storage_id
                        session.add(tr)

                    # создание нового sold и purchase
                    new_sold = SoldUniversal(owner_id=user_id, universal_storage_id=new_storage.universal_storage_id)
                    session.add(new_sold)

                    new_purchase_request = PurchaseRequestUniversal(
                        purchase_request_id=data.purchase_request_id,
                        universal_storage_id=new_storage.universal_storage_id
                    )
                    session.add(new_purchase_request)

                    new_purchase = Purchases(
                        user_id=user_id,
                        universal_storage_id=new_storage.universal_storage_id,
                        product_type=ProductType.UNIVERSAL,
                        original_price=data.original_price_one,
                        purchase_price=data.purchase_price_one,
                        cost_price=data.cost_price_one,
                        net_profit=(data.purchase_price_one - data.cost_price_one)
                    )
                    session.add(new_purchase)
                    await session.flush()

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
                            net_profit=new_purchase.net_profit
                        )
                    )

                # ставим отметки в БД
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
        # commit происходит тут

        await _filling_redis_universal(
            user_id=user_id,
            full_reserved_products=[data.full_product],
            sold_product_ids=sold_ids,
        )
        await _publish_purchase_universal(user_id, "Бесконечно ...", data, product_movement)
        return True
    except Exception as e:
        # Очистка: удалить созданные строки хранилища и файлы, если они созданы
        # Созданные хранилища могут иметь идентификаторы; удалить их строки из базы данных и файлы
        await cancel_purchase_universal_one(
            user_id=user_id,
            paths_created_storage=[Path(s.file_path) for s in created_storages if s.file_path],
            sold_universal_ids=sold_ids,
            storage_universal_ids=[s.universal_storage_id for s in created_storages if s.universal_storage_id],
            purchase_ids=purchase_ids,
            total_amount=data.total_amount,
            purchase_request_id=data.purchase_request_id,
            product_universal=data.full_product
        )
        return False


async def finalize_purchase_universal_different(user_id: int, data: StartPurchaseUniversal):
    """
    Безопасно переносит файлы (в temp), создаёт DB записи в транзакции,
    затем финализирует перемещение temp->final. При ошибке — вызывает cancel_purchase_request_accounts.
    :return: Успех покупки
    """
    mapping: List[Tuple[str, str, str]] = []  # (orig, temp, final)
    sold_product_ids: List[int] = []
    purchase_ids: List[int] = []
    product_movement: list[UniversalProductData] = []

    logger = get_logger(__name__)

    try:
        # Подготовим перемещения в temp (вне транзакции) — НЕ изменяем DB
        for product in data.full_reserved_products:
            if not product.universal_storage.file_path:
                continue

            orig = str(Path(get_config().paths.universals_dir) / product.universal_storage.file_path) # полный путь
            final = create_path_universal_storage(
                status=UniversalStorageStatus.BOUGHT,
                uuid=product.universal_storage.storage_uuid
            )
            temp = final + ".part"  # временный файл рядом с финальным

            moved = await move_file(orig, temp)
            if not moved:
                # если не удалось найти/переместить — удаляем product из БД (или помечаем), лог и cancel
                text = f"#Внимание \n\nАккаунт не найден/не удалось переместить: {orig}"
                await send_log(text)
                logger.exception(text)

                # сразу откатываем — возвращаем то что успели переместить
                await cancel_purchase_universal_different(
                    user_id=user_id,
                    mapping=mapping,
                    sold_universal_ids=sold_product_ids,
                    purchase_ids=purchase_ids,
                    total_amount=data.total_amount,
                    purchase_request_id=data.purchase_request_id,
                    product_universal=data.full_reserved_products,
                )
                return False

            # Удаление директории где хранится аккаунт (uui). Директория уже будет пустой
            shutil.rmtree(str(Path(orig).parent))

            mapping.append((orig, temp, final))

        # Создаём DB-записи в одной транзакции
        async with get_db() as session:
            async with session.begin():
                # Перед созданием SoldUniversal — удаляем ProductUniversal записей в DB
                for product in data.full_reserved_products:
                    # удалим ProductUniversal
                    await session.execute(
                        delete(ProductUniversal)
                        .where(ProductUniversal.product_universal_id == product.product_universal_id)
                    )

                    new_sold = SoldUniversal(
                        owner_id=user_id,
                        universal_storage_id=product.universal_storage_id,
                    )
                    session.add(new_sold)
                    await session.flush()
                    sold_product_ids.append(new_sold.sold_universal_id)

                    # purchases row
                    new_purchase = Purchases(
                        user_id=user_id,
                        universal_storage_id=product.universal_storage_id,
                        product_type=ProductType.UNIVERSAL,
                        original_price=data.original_price_one,
                        purchase_price=data.purchase_price_one,
                        cost_price=data.cost_price_one,
                        net_profit=data.purchase_price_one - data.cost_price_one
                    )
                    session.add(new_purchase)
                    await session.flush()
                    purchase_ids.append(new_purchase.purchase_id)

                    if product.universal_storage.file_path:
                        file_path = create_path_universal_storage(
                            status=UniversalStorageStatus.BOUGHT,
                            uuid=product.universal_storage.storage_uuid
                        )
                    else:
                        file_path = None

                    # Обновляем UniversalStorage.status = 'bought' через update (на всякий случай)
                    await session.execute(
                        update(UniversalStorage)
                        .where(UniversalStorage.universal_storage_id == product.universal_storage_id)
                        .values(
                            status=UniversalStorageStatus.BOUGHT,
                            file_path=file_path
                        )
                    )

                    product_movement.append(
                        UniversalProductData(
                            universal_storage_id=product.universal_storage_id,
                            sold_universal_id=new_sold.sold_universal_id,
                            purchase_id=new_purchase.purchase_id,
                            cost_price = new_purchase.cost_price,
                            purchase_price = new_purchase.purchase_price,
                            net_profit = new_purchase.net_profit
                        )
                    )

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
            await cancel_purchase_universal_different(
                user_id=user_id,
                mapping=mapping,
                sold_universal_ids=sold_product_ids,
                purchase_ids=purchase_ids,
                total_amount=data.total_amount,
                purchase_request_id=data.purchase_request_id,
                product_universal=data.full_reserved_products,
            )
            return False

        await _filling_redis_universal(user_id, data.full_reserved_products, sold_product_ids)

        products_universal = await get_product_universal_by_category_id(data.category_id)
        await _publish_purchase_universal(
            user_id=user_id,
            product_left=len(products_universal),
            data=data,
            product_movement=product_movement
        )

        return True

    except Exception as e:
        logger.exception("Error in finalize_purchase: %s", e)
        await send_log(f"#Ошибка finalize_purchase_universal_different: {e}")

        await cancel_purchase_universal_different(
            user_id=user_id,
            mapping=mapping,
            sold_universal_ids=sold_product_ids,
            purchase_ids=purchase_ids,
            total_amount=data.total_amount,
            purchase_request_id=data.purchase_request_id,
            product_universal=data.full_reserved_products,
        )
        return False