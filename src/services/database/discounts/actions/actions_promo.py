from datetime import datetime, timezone
from typing import Optional, List

import orjson
from sqlalchemy import select, func

from src.config import PAGE_SIZE
from src.services.redis.core_redis import get_redis
from src.services.database.admins.models import AdminActions
from src.services.database.core.database import get_db
from src.services.database.discounts.models import PromoCodes, ActivatedPromoCodes
from src.utils.codes import generate_code



async def get_promo_code_by_page(
    page: int = None,
    page_size: int = PAGE_SIZE,
    show_not_valid: bool = False
) -> List[PromoCodes]:
    async with get_db() as session_db:
        query = select(PromoCodes)
        if page:
            offset = (page - 1) * page_size
            query = query.limit(page_size).offset(offset)
        if not show_not_valid:
            query = query.where(PromoCodes.is_valid == True)

        result_db = await session_db.execute(query)
        return result_db.scalars().all()


async def get_count_promo_codes(consider_invalid: bool = False) -> int:
    async with get_db() as session_db:
        query = select(func.count()).select_from(PromoCodes)
        if not consider_invalid:
            query = query.where(PromoCodes.is_valid == True)

        result_db = await session_db.execute(query)
        return result_db.scalar()


async def get_valid_promo_code(
    code: str | None = None,
    promo_code_id: int | None = None
) -> PromoCodes | None:
    if code:
        async with get_redis() as session_redis:
            promo_code_json = await session_redis.get(f"promo_code:{code}")
            if promo_code_json:
                selected_promo_code = orjson.loads(promo_code_json)
                return PromoCodes(**selected_promo_code)

    async with get_db() as session_db:
        query = select(PromoCodes)
        if code:
            query = query.where(
                (PromoCodes.activation_code == code) &
                (PromoCodes.is_valid == True)
            )
        elif promo_code_id:
            query = query.where(
                (PromoCodes.promo_code_id == promo_code_id) &
                (PromoCodes.is_valid == True)
            )
        else:
            raise ValueError("Необходимо указать хотя бы 'code' или 'promo_code_id'")

        promo_code = (await session_db.execute(query)).scalars().first()
        if promo_code:
            return promo_code

async def create_promo_code(
    creator_id: int,
    code: Optional[str] = None,
    min_order_amount: int = 0,
    amount: int = None,
    discount_percentage: int = None,
    number_of_activations: int = 1,
    expire_at: datetime = None
) -> PromoCodes:
    """
    Создаст промокод с уникальным activation_code
    :param creator_id: id админа, который создал промокод
    :param code: если промокод с данным кодом не занят, то будет создан с ним
    :param min_order_amount: минимальная сумма для активации
    :param amount: сумма скидки (взаимоисключающая с discount_percentage)
    :param discount_percentage: процент скидки (взаимоисключающая с amount)
    :param number_of_activations: число активаций
    :param expire_at: годен до (указывать с utc)
    :return:
    :raise: ValueError: если переданный code уже используется
    """
    if amount is not None and discount_percentage is not None:
        raise ValueError("Передайте только один аргумент: amount ИЛИ discount_percentage")
    if amount is None and discount_percentage is None:
        raise ValueError("Передайте хотя бы один аргумент: amount ИЛИ discount_percentage")

    if code:
        async with get_redis() as session_redis:
            result = await session_redis.get(f"promo_code:{code}")
            if result: # если такой код уже есть
                raise ValueError("Данный код не уникальный! Есть ещё один активный промокод с там же кодом")
    else:
        while True:
            code = generate_code()

            async with get_redis() as session_redis:
                result = await session_redis.get(f"promo_code:{code}")
                if not result: # если создали уникальный код
                    break

    new_promo_code = PromoCodes(
        activation_code=code,
        min_order_amount=min_order_amount, # минимальная сумма для активации
        amount=amount, # одно из двух
        discount_percentage=discount_percentage, # одно из двух
        number_of_activations=number_of_activations,
        expire_at=expire_at,
    )
    async with get_db() as session_db:
        session_db.add(new_promo_code)
        await session_db.commit()
        await session_db.refresh(new_promo_code)

        new_admin_actions = AdminActions(
            user_id= creator_id,
            action_type = 'create_promo_code',
            details = {
                "message": "Администрация создала новый промокод",
                "promo_code_id": new_promo_code.promo_code_id
            }
        )
        session_db.add(new_admin_actions)
        await session_db.commit()

    if expire_at:
        storage_time = new_promo_code.expire_at - datetime.now(timezone.utc)
        second_storage = int(storage_time.total_seconds())
    else:
        second_storage = None

    async with get_redis() as session_redis:
        if second_storage is None: # если не надо устанавливать время хранения
            await session_redis.set(
                f"promo_code:{new_promo_code.activation_code}",
                orjson.dumps(new_promo_code.to_dict()),

            )
        else:
            await session_redis.setex(
                f"promo_code:{new_promo_code.activation_code}",
                second_storage,
                orjson.dumps(new_promo_code.to_dict())
            )

    return new_promo_code


async def check_activate_promo_code(promo_code_id: int, user_id: int) -> bool:
    """
    Проверит, активировал ли пользователь этот.
    :return True если активировал ранее
    """

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(ActivatedPromoCodes)
            .where(
                (ActivatedPromoCodes.promo_code_id == promo_code_id) &
                (ActivatedPromoCodes.user_id == user_id)
            )
        )
        return bool(result_db.scalars().all())



# написать функцию для деактивации промокода
# написать функцию для деактивации промокода
# написать функцию для деактивации промокода
# написать функцию для деактивации промокода
# написать функцию для деактивации промокода