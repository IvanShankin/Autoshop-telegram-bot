from datetime import datetime
from typing import Literal, Any, List

import orjson
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from src.services.database.selling_accounts.models.models import AccountStorage
from src.services.redis.core_redis import get_redis
from src.services.redis.filling_redis import filling_all_account_services, filling_account_categories_by_service_id, \
    filling_account_categories_by_category_id, filling_account_services, filling_product_account_by_account_id, \
    filling_product_accounts_by_category_id, filling_sold_account_by_account_id, filling_sold_accounts_by_owner_id
from src.services.database.core.database import get_db
from src.services.database.selling_accounts.models import AccountServices, AccountCategories, ProductAccounts, \
    AccountCategoryTranslation, AccountCategoryFull

def _create_dict(data: List[tuple[str, Any]]) -> dict:
    """
    Формирует словарь, если переменная есть, то запишет её с указанным ключом
    :param data: List[("имя для ключа", значение)]
    """
    result = {}
    for key_name, value in data:
        if value is not None:
            result[key_name] = value
    return result


async def update_account_service(
        account_service_id: int,
        name: str = None,
        index: int = None,
        show: bool = None
) -> AccountServices:
    """Можно изменить всё кроме типа сервиса"""
    async with get_db() as session:
        # загружаем текущий объект
        result = await session.execute(
            select(AccountServices).where(AccountServices.account_service_id == account_service_id)
        )
        service: AccountServices = result.scalar_one_or_none()
        if not service:
            raise ValueError(f"Сервис аккаунтов с id = {account_service_id} не найден")

        # собираем только те поля, которые реально переданы
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if show is not None:
            update_data["show"] = show
        if index is not None and index != service.index:
            old_index = service.index or 0
            new_index = index

            # обновляем индексы
            if new_index < old_index:
                # сдвигаем все записи между new_index и old_index-1 вверх (+1)
                await session.execute(
                    update(AccountServices)
                    .where(AccountServices.index >= new_index)
                    .where(AccountServices.index < old_index)
                    .values(index=AccountServices.index + 1)
                )
            elif new_index > old_index:
                # сдвигаем все записи между old_index+1 и new_index вниз (-1)
                await session.execute(
                    update(AccountServices)
                    .where(AccountServices.index <= new_index)
                    .where(AccountServices.index > old_index)
                    .values(index=AccountServices.index - 1)
                )

            update_data["index"] = new_index

        if update_data:
            await session.execute(
                update(AccountServices)
                .where(AccountServices.account_service_id == account_service_id)
                .values(**update_data)
            )

            await session.commit()

            # обновляем объект в памяти (чтобы вернуть актуальные данные)
            for key, value in update_data.items():
                setattr(service, key, value)

    if update_data:
        await filling_all_account_services() # обновляем redis для поддержания целостности индексов

        if index is None: # если индекс не меняли, то достаточно обновить только один ключ в redis
            async with get_redis() as session_redis:
                await session_redis.set(f"account_service:{account_service_id}", orjson.dumps(service.to_dict()))
        else:
            await filling_account_services()

    return service


async def update_account_category(
        account_category_id: int,
        index: int = None,
        show: bool = None,
        is_accounts_storage: bool = None,
        price_one_account: int = None,
        cost_price_one_account: int = None,
) -> AccountCategories:
    if price_one_account is not None and price_one_account <= 0:
        raise ValueError("Цена аккаунтов должна быть положительным числом")
    if cost_price_one_account is not None  and cost_price_one_account < 0:
        raise ValueError("Себестоимость аккаунтов должна быть положительным числом")

    async with get_db() as session:
        # загружаем текущий объект
        result = await session.execute(
            select(AccountCategories).where(AccountCategories.account_category_id == account_category_id)
        )
        category: AccountCategories = result.scalar_one_or_none()
        if not category:
            raise ValueError(f"Категория аккаунтов с id = {account_category_id} не найдена")

        # собираем только те поля, которые реально переданы
        update_data = {}
        if is_accounts_storage is not None:
            if category.is_accounts_storage:
                result = await session.execute(
                    select(ProductAccounts).where(ProductAccounts.account_category_id == account_category_id)
                )
                product_account: ProductAccounts = result.scalars().first()
                if product_account: # если данная категория хранит аккаунты
                    raise ValueError(
                        f"Категория с id = {account_category_id} хранит аккаунты. "
                        f"Необходимо извлечь их для применения изменений"
                    )

            update_data["is_accounts_storage"] = is_accounts_storage
        if show is not None:
            update_data["show"] = show
        if price_one_account is not None:
            update_data["price_one_account"] = price_one_account
        if cost_price_one_account is not None:
            update_data["cost_price_one_account"] = cost_price_one_account
        if index is not None and index != category.index:
            old_index = category.index or 0
            new_index = index

            # обновляем индексы
            if new_index < old_index:
                # сдвигаем все записи между new_index и old_index-1 вверх (+1)
                await session.execute(
                    update(AccountCategories)
                    .where(AccountCategories.index >= new_index)
                    .where(AccountCategories.index < old_index)
                    .values(index=AccountCategories.index + 1)
                )
            elif new_index > old_index:
                # сдвигаем все записи между old_index+1 и new_index вниз (-1)
                await session.execute(
                    update(AccountCategories)
                    .where(AccountCategories.index <= new_index)
                    .where(AccountCategories.index > old_index)
                    .values(index=AccountCategories.index - 1)
                )

            update_data["index"] = new_index

        if update_data:
            await session.execute(
                update(AccountCategories)
                .where(AccountCategories.account_category_id == account_category_id)
                .values(**update_data)
            )

            await session.commit()

            # обновляем объект в памяти (чтобы вернуть актуальные данные)
            for key, value in update_data.items():
                setattr(category, key, value)

    if update_data:
        # обновит redis с новыми index
        await filling_account_categories_by_service_id()
        await filling_account_categories_by_category_id()

    return category


async def update_account_category_translation(
        account_category_id: int,
        language: str,
        name: str = None,
        description: str = None
) -> AccountCategoryFull:
    async with get_db() as session:
        # загружаем текущий объект
        result = await session.execute(
            select(AccountCategories).where(AccountCategories.account_category_id == account_category_id)
        )
        category: AccountCategories = result.scalar_one_or_none()
        if not category:
            raise ValueError(f"Категория аккаунтов с id = {account_category_id} не найдена")

        result = await session.execute(
            select(AccountCategoryTranslation)
            .where(
                (AccountCategoryTranslation.account_category_id == account_category_id) &
                (AccountCategoryTranslation.lang == language)
            )
        )
        translation: AccountCategoryTranslation = result.scalar_one_or_none()
        if not translation:
            raise ValueError(f"Перевод с языком '{language}' не найден")

        # собираем поля которые передали
        update_data = {}
        if name is not None:
            update_data['name'] = name
        if description is not None:
            update_data['description'] = description

        if update_data:
            await session.execute(
                update(AccountCategoryTranslation)
                .where(
                    (AccountCategoryTranslation.account_category_id == account_category_id) &
                    (AccountCategoryTranslation.lang == language)
                )
                .values(**update_data)
            )

            await session.commit()

            # обновляем объект в памяти (чтобы вернуть актуальные данные)
            for key, value in update_data.items():
                setattr(translation, key, value)

    if update_data:
        # обновит redis с новыми index
        await filling_account_categories_by_service_id()
        await filling_account_categories_by_category_id()

    return translation


async def update_account_storage(
    account_storage_id: int = None,
    storage_uuid: str = None,
    file_path: str = None,
    checksum: str = None,
    status: Literal["for_sale", "bought", "deleted"] = None,
    encrypted_key: str = None,
    encrypted_key_nonce: str = None,
    key_version: int = None,
    encryption_algo: str = None,
    login_encrypted: str = None,
    password_encrypted: str = None,
    last_check_at: datetime = None,
    is_valid: bool = None,
    is_active: bool = None,
) -> AccountStorage:
    async with get_db() as session:
        result = await session.execute(
            select(AccountStorage)
            .options(
                selectinload(AccountStorage.product_account),
                selectinload(AccountStorage.sold_account),
                selectinload(AccountStorage.deleted_account)
            )
            .where(AccountStorage.account_storage_id == account_storage_id)
        )
        account: AccountStorage = result.scalar_one_or_none()

        update_data = _create_dict([
            ('storage_uuid', storage_uuid),
            ('file_path', file_path),
            ('checksum', checksum),
            ('status', status),
            ('encrypted_key', encrypted_key),
            ('encrypted_key_nonce', encrypted_key_nonce),
            ('key_version', key_version),
            ('encryption_algo', encryption_algo),
            ('login_encrypted', login_encrypted),
            ('password_encrypted', password_encrypted),
            ('last_check_at', last_check_at),
            ('is_valid', is_valid),
            ('is_active', is_active),
        ])

        if update_data:
            await session.execute(
                update(AccountStorage)
                .where(AccountStorage.account_storage_id == account_storage_id)
                .values(**update_data)
            )
            await session.commit()

            # обновляем объект в памяти (чтобы вернуть актуальные данные)
            for key, value in update_data.items():
                setattr(account, key, value)

        # один AccountStorage - одна запись в другой таблице, но будем заполнять везде где есть
        if account.product_account:
            await filling_product_account_by_account_id(account.product_account.account_id)
            await filling_product_accounts_by_category_id()
        if account.sold_account:
            await filling_sold_account_by_account_id(account.sold_account.sold_account_id)
            await filling_sold_accounts_by_owner_id(account.sold_account.owner_id)

        return account