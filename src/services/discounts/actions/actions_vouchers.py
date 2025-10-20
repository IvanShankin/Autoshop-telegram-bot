from datetime import datetime, timezone
from typing import Optional, Tuple, List

import orjson
from dateutil.parser import parse
from sqlalchemy import update, select, func

from src.broker.producer import publish_event
from src.config import PAGE_SIZE
from src.exceptions.service_exceptions import NotEnoughMoney
from src.redis_dependencies.core_redis import get_redis
from src.redis_dependencies.filling_redis import filling_voucher_by_user_id, filling_user
from src.services.admins.models import AdminActions
from src.services.database.database import get_db
from src.services.discounts.events import NewActivationVoucher
from src.services.discounts.models import Vouchers, VoucherActivations
from src.services.discounts.models.schemas import SmallVoucher
from src.services.users.actions import update_user, get_user
from src.services.users.models import WalletTransaction, UserAuditLogs, Users
from src.utils.codes import generate_code
from src.utils.i18n import get_i18n
from src.bot_actions.actions import send_log


async def get_valid_voucher_by_user_page(user_id: int, page: int = None, page_size: int = PAGE_SIZE) -> List[SmallVoucher]:
    """Если не указывать page, то вернётся весь список. Отсортирован по дате (desc)"""
    async with get_redis() as session_redis:
        vouchers_json = await session_redis.get(f"voucher_by_user:{user_id}")
        if vouchers_json is not None:
            vouchers = [SmallVoucher(**voucher) for voucher in orjson.loads(vouchers_json)]

            # аналог постраничного вывода как в БД
            if page:
                start = (page - 1) * page_size
                end = start + page_size
                return vouchers[start:end]
            return vouchers

    async with (get_db() as session_db):
        query = select(
            Vouchers
        ).where(
            (Vouchers.creator_id == user_id) &
            (Vouchers.is_valid == True) &
            (Vouchers.is_created_admin == False)
        ).order_by(Vouchers.start_at.desc())

        if page:
            offset = (page - 1) * page_size
            query = query.limit(page_size).offset(offset)

        result_db = await session_db.execute(query)
        vouchers = result_db.scalars().all()
        return [SmallVoucher.from_orm_model(voucher) for voucher in vouchers]

async def get_count_voucher(user_id: int) -> int:
    async with get_redis() as session_redis:
        vouchers_json = await session_redis.get(f"voucher_by_user:{user_id}")
        if vouchers_json is not None:
            return len(orjson.loads(vouchers_json))

    async with get_db() as session_db:
        result = await session_db.execute(
            select(func.count()).where((Vouchers.creator_id == user_id) &(Vouchers.is_valid == True))
        )
        return result.scalar()

async def get_valid_voucher_by_code(
    code: str
) -> Vouchers | None:
    async with get_redis() as session_redis:
        voucher_json = await session_redis.get(f"voucher:{code}")
        if voucher_json:
            selected_voucher = orjson.loads(voucher_json)
            return Vouchers(
                voucher_id = selected_voucher['voucher_id'],
                creator_id = selected_voucher['creator_id'],
                is_created_admin = selected_voucher['is_created_admin'],

                activation_code = selected_voucher['activation_code'],
                amount = selected_voucher['amount'],
                activated_counter = selected_voucher['activated_counter'],
                number_of_activations = selected_voucher['number_of_activations'],

                start_at = parse(selected_voucher['start_at']),
                expire_at = parse(selected_voucher['expire_at']) if selected_voucher['expire_at'] else selected_voucher['expire_at'],
                is_valid = selected_voucher['is_valid']
            )

    async with get_db() as session_db:
        result = await session_db.execute(
            select(Vouchers)
            .where(
                (Vouchers.activation_code == code) &
                (Vouchers.is_valid == True)
            ))
        voucher = result.scalars().first()
        if voucher:
            return voucher

async def get_voucher_by_id(
    voucher_id: int,
    check_on_valid: bool = True
) -> Vouchers | None:
    """Если есть флаг check_on_valid, то при запросе к БД буде доп проверка на валидность"""
    async with get_db() as session_db:
        query = select(Vouchers).where((Vouchers.voucher_id == voucher_id))
        if check_on_valid:
            query.where(Vouchers.is_valid == True)

        result = await session_db.execute(query)
        return result.scalar_one_or_none()

async def create_voucher(
        user_id: int,
        is_created_admin: bool,
        amount: int,
        number_of_activations: int,
        expire_at: Optional[datetime] = None,
) -> Vouchers:
    """
    Создаёт ваучер. У пользователя должно быть достаточно денег
    :param user_id: id пользователя
    :param is_created_admin: флаг создания ваучера админом
    :param amount: сумма одного ваучера
    :param number_of_activations: количество активаций
    :param expire_at: время жизни
    :return:
    :exception NotEnoughMoney: если у пользователя недостаточно денег
    """

    user = await get_user(user_id)
    required_amount = amount * number_of_activations

    if user.balance < required_amount and is_created_admin == False:
        raise NotEnoughMoney("У пользователя недостаточно денег", required_amount - user.balance)

    while True:
        code = generate_code(15)
        result = await get_valid_voucher_by_code(code)
        if not result:  # если создали уникальный код
            break

    async with get_db() as session_db:
        async with session_db.begin(): # Транзакия. При выходе произведёт commit
            await session_db.execute(
                update(Users)
                .where(Users.user_id == user.user_id)
                .values(balance=user.balance - required_amount)
            )

            new_voucher = Vouchers(
                creator_id=user_id,
                is_created_admin=is_created_admin,
                activation_code=code,
                amount=amount,
                number_of_activations=number_of_activations,
                expire_at=expire_at
            )
            session_db.add(new_voucher)
        await session_db.refresh(new_voucher)

        # создание лога
        if is_created_admin:
            new_admin_actions = AdminActions(
                user_id = user.user_id,
                action_type = 'create_voucher',
                details = {'message': "Админ создал ваучер", "voucher_id": new_voucher.voucher_id}
            )
            session_db.add(new_admin_actions)
            await session_db.commit()
            await send_log(
                f'#Админ_создал_ваучер \n\nСумма: {amount} \nЧисло активаций: {number_of_activations} \nГоден до: {expire_at}'
            )
        else:
            new_user_log = UserAuditLogs(
                user_id=user.user_id,
                action_type="create_voucher",
                details={
                    "message": 'Пользователь создал ваучер',
                    "voucher_id": new_voucher.voucher_id,
                },
            )
            wallet_transaction = WalletTransaction(
                user_id = user.user_id,
                type = 'voucher',
                amount = required_amount,
                balance_before = user.balance, # тут старые данные
                balance_after = user.balance + required_amount
            )
            session_db.add(new_user_log)
            session_db.add(wallet_transaction)
            await session_db.commit()

    if expire_at:
        storage_time = expire_at - datetime.now(timezone.utc)
        second_storage = int(storage_time.total_seconds())
    else:
        second_storage = None

    # заполнение redis
    await filling_user(user)

    async with get_redis() as session_redis:
        if second_storage is None:  # если не надо устанавливать время хранения
            await session_redis.set(
                f"voucher:{new_voucher.activation_code}",
                orjson.dumps(new_voucher.to_dict()),
            )
        else:
            await session_redis.setex(
                f"voucher:{new_voucher.activation_code}",
                second_storage,
                orjson.dumps(new_voucher.to_dict())
            )

        await filling_voucher_by_user_id(user.user_id)

    return new_voucher


async def deactivate_voucher(voucher_id: int) -> int:
    """
    Сделает ваучер невалидным в БД (is_valid = False), вернёт деньги пользователю и удалит ваучер с redis.
    Сообщение пользователю НЕ будет отправлено!
    :return Возвращённая сумма пользователю
    :except Exception вызовет ошибку если есть
    """
    owner_id = None
    try:
        async with get_db() as session_db:
            result_db = await session_db.execute(
                update(Vouchers)
                .where(Vouchers.voucher_id == voucher_id)
                .values(is_valid=False)
                .returning(Vouchers)
            )
            voucher: Vouchers = result_db.scalar_one_or_none()
            owner_id = voucher.creator_id
            await session_db.commit()

            # удаление с redis
            async with get_redis() as session_redis:
                await session_redis.delete(f"voucher:{voucher.activation_code}")

            await filling_voucher_by_user_id(owner_id)

            # сумма возврата = количество неактивированных ваучеров * сумму одного ваучера
            refund_amount = (voucher.number_of_activations - voucher.activated_counter) * voucher.amount

            # если создатель ваучера админ или сумма для возврата <= нуля
            if voucher.is_created_admin or refund_amount <= 0:
                return 0

            # обновление баланса у пользователя
            user = await get_user(voucher.creator_id)
            balance_before = user.balance
            user.balance = user.balance + refund_amount
            await update_user(user)

            new_wallet_transaction = WalletTransaction(
                user_id=user.user_id,
                type='refund',
                amount=refund_amount,
                balance_before=balance_before,
                balance_after=user.balance,
            )
            session_db.add(new_wallet_transaction)
            await session_db.commit()
            await session_db.refresh(new_wallet_transaction)

            new_user_log_1 = UserAuditLogs(
                user_id=user.user_id,
                action_type="deactivate_voucher",
                details={
                    'message': "Ваучер деактивировался",
                    'voucher_id': voucher_id,
                },
            )
            new_user_log_2 = UserAuditLogs(
                user_id=user.user_id,
                action_type="return_money_from_vouchers",
                details={
                    "message": 'Пользователю вернулись деньги за ваучер который деактивировался',
                    "amount": refund_amount,
                    'voucher_id': voucher_id,
                    "transaction_id": new_wallet_transaction.wallet_transaction_id
                },
            )
            session_db.add(new_user_log_1)
            session_db.add(new_user_log_2)

            await session_db.commit()

            return refund_amount
    except Exception as e:
        i18n = get_i18n('ru', 'discount_dom')
        log_message = i18n.gettext(
            "#Error_refunding_money_from_voucher \n\nVoucher ID: {voucher_id} \nOwner ID: {owner_id} \nError: {error}"
        ).format(voucher_id=voucher_id, owner_id=owner_id, error=str(e))

        await send_log(log_message)
        raise e



async def activate_voucher(user: Users, code: str, language: str) -> Tuple[str, bool]:
    """
    Проверит наличие ваучера с таким кодом, если он действителен и пользователь его ещё не активировал, то ваучер активируется.
    Если user не является создателем ваучера, то он может его активировать.

    Отошлёт сообщение создателю ваучера, что он активирован

    :param user: Тот кто хочет активировать ваучер.
    :param code: Код ваучера.
    :param language: Язык на котором будет возвращено сообщение.
    :return Tuple[str, bool]: Сообщение с результатом, успешность активации
    """
    i18n = get_i18n(language, "discount_dom")
    balance_before = user.balance

    voucher = await get_valid_voucher_by_code(code)
    if not voucher:
        return i18n.gettext("Voucher with this code not found"), False

    # если кто пытается активировать ваучера является его создателем
    if voucher.creator_id == user.user_id:
        return i18n.gettext("You cannot activate the voucher. You are its creator"), False

    # если ваучер просрочен
    if voucher.expire_at and voucher.expire_at < datetime.now(timezone.utc):
        await deactivate_voucher(voucher.voucher_id)
        return i18n.gettext(
            "Voucher expired \n\nID '{id}' \nCode '{code}' \n\nVoucher expired due to time limit. It can no longer be activated"
        ).format(id=voucher.voucher_id, code=voucher.activation_code), False

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(VoucherActivations)
            .where(
                (VoucherActivations.voucher_id == voucher.voucher_id) &
                (VoucherActivations.user_id == user.user_id)
            )
            .with_for_update() # чтобы блокировать эту запись, для того что бы другие её вызовы не могли получить неактуальные данные
        )
        log_activate = result_db.scalar_one_or_none()
        if log_activate:
            return i18n.gettext("You have already activated this voucher. It can only be activated once"), False

    user.balance = user.balance + voucher.amount
    user = await update_user(user)

    async with get_db() as session_db:
        new_activated = VoucherActivations(
            voucher_id=voucher.voucher_id,
            user_id=user.user_id,
        )
        session_db.add(new_activated)
        await session_db.commit()

    new_event = NewActivationVoucher(
        user_id = user.user_id,
        language = user.language,
        voucher_id = voucher.voucher_id,
        amount = voucher.amount,
        balance_before = balance_before,
        balance_after = user.balance
    )
    await publish_event(new_event.model_dump(), "voucher.activated")

    return i18n.gettext(
        "Voucher successfully activated! \n\nVoucher amount: {amount} \nCurrent balance: {new_balance}"
    ).format(amount=voucher.amount, new_balance=user.balance), True




