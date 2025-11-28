# запустить для ручного тестирования в телеграмме
import asyncio
import os
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from tests.helpers.func_fabric import create_income_from_referral_fabric
from src.utils.secret_data import encrypt_data
from tests.helpers.func_fabric import create_sold_account_factory, create_account_storage_factory
from tests.helpers.func_fabric import create_product_account_factory
from src.broker.consumer import start_background_consumer
from src.services.database.core.filling_database import create_database
from src.services.database.discounts.utils.set_not_valid import deactivate_expired_promo_codes_and_vouchers
from src.services.database.selling_accounts.actions import add_account_category, \
    add_account_services, get_account_service
from src.services.database.selling_accounts.models import AccountCategoryFull
from src.services.fastapi_core.server import start_server
from src.services.redis.filling_redis import filling_all_redis
from src.services.redis.tasks import start_dollar_rate_scheduler


async def create_need_model():
    await create_database()
    await filling_all_redis()
    await start_background_consumer()

    asyncio.create_task(deactivate_expired_promo_codes_and_vouchers())
    asyncio.create_task(start_dollar_rate_scheduler())
    asyncio.create_task(start_server())

    try:
        services = await add_account_services('telegram', 1)
    except ValueError: # если сервис уже есть
        services = await get_account_service(1)
        pass
    main_categories: AccountCategoryFull = []
    for i in range(3):
        cat = await add_account_category(
            account_service_id = services.account_service_id,
            language = 'ru',
            name = f"Имя {i}",
            description = "Описание",
            number_buttons_in_row = 1,
            is_accounts_storage = False,
            price_one_account = 200,
            cost_price_one_account = 100
        )
        main_categories.append(cat)

    for i in range(3):
        cat = await add_account_category(
            account_service_id=services.account_service_id,
            parent_id=main_categories[0].account_category_id,
            language='ru',
            name=f"Имя {i}",
            description="Описание",
            number_buttons_in_row=1,
            is_accounts_storage=True,
            price_one_account=200,
            cost_price_one_account=100
        )
        acc = await create_product_account_factory(account_category_id = cat.account_category_id)

async def create_acc():
    for i in range(10):
        await create_income_from_referral_fabric(1028495731, 7869052488)



if __name__ == "__main__":
    asyncio.run(create_acc())
    print("Создалось успешно")

