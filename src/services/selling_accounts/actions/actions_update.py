import orjson
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from src.redis_dependencies.core_redis import get_redis
from src.redis_dependencies.filling_redis import filling_all_account_services, filling_account_categories_by_service_id, \
    filling_account_categories_by_category_id, filling_account_services
from src.redis_dependencies.time_storage import TIME_SOLD_ACCOUNTS_BY_OWNER, TIME_SOLD_ACCOUNTS_BY_ACCOUNT
from src.services.database.database import get_db
from src.services.selling_accounts.actions.actions_get import get_sold_accounts_by_owner_id
from src.services.selling_accounts.models import AccountServices, AccountCategories, ProductAccounts, \
    AccountCategoryTranslation, SoldAccounts, SoldAccountsTranslation
from src.services.selling_accounts.models.models_with_tranlslate import AccountCategoryFull, SoldAccountsFull


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


async def update_sold_account(
        sold_account_id: int,
        is_valid: bool = None,
        is_deleted: bool = None,
) -> SoldAccounts:
    async with get_db() as session:
        # загружаем текущий объект
        result = await session.execute(
            select(SoldAccounts)
            .options(selectinload(SoldAccounts.translations))
            .where(SoldAccounts.sold_account_id == sold_account_id)
        )
        account: SoldAccounts = result.scalar_one_or_none()
        if not account:
            raise ValueError(f"Аккаунта с id = {sold_account_id} не найдено")

        # собираем поля которые передали
        update_data = {}
        if is_valid is not None:
            update_data['is_valid'] = is_valid
        if is_deleted is not None:
            update_data['is_deleted'] = is_deleted

        if update_data:
            await session.execute(
                update(SoldAccounts)
                .where(SoldAccounts.sold_account_id == sold_account_id)
                .values(**update_data)
            )

            await session.commit()

            # обновляем объект в памяти (чтобы вернуть актуальные данные)
            for key, value in update_data.items():
                setattr(account, key, value)

        # обновляем redis
        result_db = await session.execute(
            select(SoldAccountsTranslation.lang)
            .where(SoldAccountsTranslation.sold_account_id == sold_account_id)
            .distinct()
        )
        list_lang = result_db.scalars().all() # список всех языков

        async with get_redis() as session_redis:
            for lang in list_lang:

                if is_deleted is not None: # если аккаунт стал удалённым, то такое не храним в redis
                    # меняем по одиночному значению
                    await session_redis.delete(f"sold_accounts_by_accounts_id:{sold_account_id}:{lang}")

                    # меняем по ключу со списком
                    # не обновлённый список (ожидаемо, но может быть и обновлённым)
                    account_list = await get_sold_accounts_by_owner_id(account.owner_id, lang)
                    new_list = [acc.model_dump() for acc in account_list if acc.sold_account_id != sold_account_id]
                    await session_redis.setex(
                        f"sold_accounts_by_owner_id:{account.owner_id}:{lang}",
                        TIME_SOLD_ACCOUNTS_BY_OWNER,
                        orjson.dumps(new_list)
                    )
                else:
                    # меняем по одиночному значению
                    account_full = SoldAccountsFull.from_orm_with_translation(account, lang)
                    await session_redis.setex(
                        f"sold_accounts_by_accounts_id:{sold_account_id}:{lang}",
                        TIME_SOLD_ACCOUNTS_BY_ACCOUNT,
                        orjson.dumps(account_full.model_dump())
                    )

                    # меняем по ключу со списком
                    # не обновлённый список (ожидаемо, но может быть и обновлённым)
                    account_list = await get_sold_accounts_by_owner_id(account.owner_id, lang)
                    new_list = []
                    for acc in account_list:
                        if acc.sold_account_id != sold_account_id:
                            new_list.append(acc.model_dump())
                        else:
                            new_list.append(account_full.model_dump()) # добавление изменённой модели

                    await session_redis.setex(
                        f"sold_accounts_by_owner_id:{account.owner_id}:{lang}",
                        TIME_SOLD_ACCOUNTS_BY_OWNER,
                        orjson.dumps(new_list)
                    )

        return account