from datetime import datetime, timezone
from typing import Optional

import orjson
from sqlalchemy import select

from src.redis_dependencies.core_redis import get_redis
from src.services.database.database import get_db
from src.services.discounts.models import PromoCodes
from src.utils.codes import generate_code


async def get_valid_promo_code(
    code: str
) -> PromoCodes | None:
    async with get_redis() as session_redis:
        promo_code_json = await session_redis.get(f"promo_code:{code}")
        if promo_code_json:
            selected_promo_code = orjson.loads(promo_code_json)
            return PromoCodes(
                promo_code_id=selected_promo_code['promo_code_id'],
                activation_code = selected_promo_code['activation_code'],
                min_order_amount = selected_promo_code['min_order_amount'],

                activated_counter = selected_promo_code['activated_counter'],
                amount = selected_promo_code['amount'],
                discount_percentage = selected_promo_code['discount_percentage'],
                number_of_activations = selected_promo_code['number_of_activations'],

                start_at = selected_promo_code['start_at'],
                expire_at = selected_promo_code['expire_at'],
                is_valid = selected_promo_code['is_valid']
            )

    async with get_db() as session_db:
        result = await session_db.execute(
            select(PromoCodes)
            .where(
                (PromoCodes.activation_code == code) &
                (PromoCodes.is_valid == True)
            ))
        promo_code = result.scalars().first()
        if promo_code:
            return promo_code

async def create_promo_code(
        code: Optional[str] = None,
        min_order_amount: int = 0,
        amount: int = None,
        discount_percentage: int = None,
        number_of_activations: int = 1,
        expire_at: datetime = None
) -> PromoCodes:
    """
    Создаст промокод с уникальным activation_code
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








