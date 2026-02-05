from datetime import datetime, timezone
from typing import Optional, List

import orjson
from sqlalchemy import select, func, update

from src.bot_actions.messages import send_log
from src.bot_actions.messages.schemas import EventSentLog, LogLevel
from src.broker.producer import publish_event
from src.config import get_config
from src.services.redis.core_redis import get_redis
from src.services.database.admins.models import AdminActions
from src.services.database.core.database import get_db
from src.services.database.discounts.models import PromoCodes, ActivatedPromoCodes
from src.utils.codes import generate_code



async def get_promo_code_by_page(
    page: int = None,
    page_size: int = None,
    show_not_valid: bool = False
) -> List[PromoCodes]:
    if page_size is None:
        page_size = get_config().different.page_size

    async with get_db() as session_db:
        query = select(PromoCodes)
        if page:
            offset = (page - 1) * page_size
            query = query.limit(page_size).offset(offset)
        if not show_not_valid:
            query = query.where(PromoCodes.is_valid == True)

        result_db = await session_db.execute(query.order_by(PromoCodes.start_at.desc()))
        return result_db.scalars().all()


async def get_count_promo_codes(consider_invalid: bool = False) -> int:
    """
    :param consider_invalid: считать невалидные.
    """
    async with get_db() as session_db:
        query = select(func.count()).select_from(PromoCodes)
        if not consider_invalid:
            query = query.where(PromoCodes.is_valid == True)

        result_db = await session_db.execute(query)
        return result_db.scalar()


async def get_promo_code(
    code: str | None = None,
    promo_code_id: int | None = None,
    get_only_valid: bool = True
) -> PromoCodes | None:
    if code and get_only_valid: # в redis хранятся только валидные
        async with get_redis() as session_redis:
            promo_code_json = await session_redis.get(f"promo_code:{code}")
            if promo_code_json:
                selected_promo_code = orjson.loads(promo_code_json)
                return PromoCodes(**selected_promo_code)

    async with get_db() as session_db:
        query = select(PromoCodes)
        if code:
            query = query.where(
                (PromoCodes.activation_code == code)
            )
        elif promo_code_id:
            query = query.where(
                (PromoCodes.promo_code_id == promo_code_id)
            )
        else:
            raise ValueError("Необходимо указать хотя бы 'code' или 'promo_code_id'")

        if get_only_valid:
            query = query.where(
                (PromoCodes.is_valid == True)
            )

        promo_code = (await session_db.execute(query)).scalars().first()

        return promo_code if promo_code else None

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
            message = "Администрация создала новый промокод",
            details = {
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

    sale = f"Скидка от: {new_promo_code.min_order_amount} ₽\n"
    if new_promo_code.amount:
        sale += f"Сумма скидки: {new_promo_code.amount} ₽"
    elif new_promo_code.discount_percentage:
        sale += f"Процент скидки: {new_promo_code.discount_percentage} %"

    event = EventSentLog(
        text=(
            f"🛠️\n"
            f"#Админ_создал_новый_промокод \n\n"
            f"ID: {new_promo_code.promo_code_id}\n"
            f"Код активации: {new_promo_code.activation_code}\n"
            f"{sale}"
        ),
        log_lvl=LogLevel.INFO
    )
    await publish_event(event.model_dump(), "message.send_log")

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



async def deactivate_promo_code(user_id: int, promo_code_id: int):
    """
    :param user_id: ID админа
    :param promo_code_id: ID промокода
    """
    async with get_db() as session_db:
        result_db = await session_db.execute(
            update(PromoCodes)
            .where(PromoCodes.promo_code_id == promo_code_id)
            .values(is_valid=False)
            .returning(PromoCodes)
        )
        promo_code: PromoCodes = result_db.scalar_one_or_none()

        new_admin_actions = AdminActions(
            user_id=user_id,
            action_type='deactivate_promo_code',
            message = "Администрация деактивировала промокод",
            details={
                "promo_code_id": promo_code_id
            }
        )
        session_db.add(new_admin_actions)
        await session_db.commit()

        event = EventSentLog(
            text=(
                f"🛠️\n"
                f"#Администрация_деактивировала_промокод \n\n"
                f"promo_code_id: {promo_code_id}\n"
                f"Код промокода: {promo_code.activation_code}\n"
                f"admin_id: {user_id}"
            ),
            log_lvl=LogLevel.INFO
        )
        await publish_event(event.model_dump(), "message.send_log")

    async with get_redis() as session_redis:
        if promo_code and promo_code.activation_code:
            await session_redis.delete(f"promo_code:{promo_code.activation_code}")


async def get_activated_promo_code(activate_promo_code_id: int) -> ActivatedPromoCodes | None:
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(ActivatedPromoCodes)
            .where(ActivatedPromoCodes.activated_promo_code_id == activate_promo_code_id)
        )
        return result_db.scalar_one_or_none()
