import uuid
from datetime import datetime, timezone, timedelta
from typing import Tuple

import orjson
from sqlalchemy import select

from src.services.database.admins.models import Admins, SentMasMessages, MessageForSending
from src.services.database.core.database import get_db
from src.services.database.discounts.models import Vouchers, PromoCodes, ActivatedPromoCodes
from src.services.database.referrals.models import Referrals, IncomeFromReferrals
from src.services.database.referrals.utils import create_unique_referral_code
from src.services.database.system.models import TypePayments
from src.services.database.system.models import UiImages, BackupLogs
from src.services.database.users.models import Users, Replenishments, NotificationSettings, WalletTransaction, \
    TransferMoneys
from src.services.redis.core_redis import get_redis
from src.services.redis.filling import filling_all_types_payments, \
    filling_types_payments_by_id


async def create_new_user_fabric(
        user_name: str = "test_username",
        union_ref_code: str = None,
        balance: int = 0,
        total_sum_replenishment: int = 0
) -> Users:
    """ Создаст нового пользователя в БД"""
    if union_ref_code is None:
        union_ref_code = await create_unique_referral_code()


    async with get_db() as session_db:
        result_db = await session_db.execute(select(Users.user_id))
        max_id = result_db.scalars().all()

        new_id = max(max_id, default=-1) + 1

        new_user = Users(
            user_id=new_id,
            username=user_name,
            balance=balance,
            unique_referral_code=union_ref_code,
            total_sum_replenishment=total_sum_replenishment,
        )

        session_db.add(new_user)
        await session_db.commit()
        await session_db.refresh(new_user)

        new_notifications = NotificationSettings(
           user_id=new_user.user_id
        )
        session_db.add(new_notifications)
        await session_db.commit()

    return new_user



async def create_admin_fabric(filling_redis: bool = True, user_id: int = None) -> Admins:
    if user_id is None:
        user = await create_new_user_fabric()
        user_id = user.user_id

    async with get_db() as session_db:
        new_admin = Admins(user_id=user_id)

        ui_image, _ = await create_ui_image_factory(str(uuid.uuid4()))
        new_message = MessageForSending(user_id=user_id, ui_image_key=ui_image.key)

        session_db.add(new_admin)
        session_db.add(new_message)
        await session_db.commit()
        await session_db.refresh(new_admin)

    if filling_redis:
        async with get_redis() as session_redis:
            await session_redis.set(f"admin:{new_admin.user_id}", '_')

    return new_admin




async def create_referral_fabric(owner_id: int = None, referral_id: int = None) -> (Referrals, Users, Users):
    """
       Создаёт тестовый реферала (у нового пользователя появляется владелец)
       :return Реферал(Referrals), Владельца(Users) и Реферала(Users)
    """
    async with get_db() as session_db:
        if referral_id is None:
            user = await create_new_user_fabric() # новый реферал
        else:
            result_db = await session_db.execute(select(Users).where(Users.user_id == referral_id))
            user = result_db.scalar()

        if owner_id is None: # создаём владельца
            owner = await create_new_user_fabric(user_name='owner_user')
            owner_id = owner.user_id
        else:
            result_db = await session_db.execute(select(Users).where(Users.user_id == owner_id))
            owner = result_db.scalar()

        # связываем реферала и владельца
        referral = Referrals(
            referral_id=user.user_id,
            owner_user_id=owner_id,
            level=1,
        )
        session_db.add(referral)
        await session_db.commit()
        await session_db.refresh(referral)

    return referral, owner, user



async def create_income_from_referral_fabric(
        referral_user_id: int = None,
        owner_id: int = None,
        replenishment_id: int = None,
        amount: int = 100,
        percentage_of_replenishment: int = 5,
) -> (IncomeFromReferrals, Users, Users):
    """
        Создаёт доход от реферала, если не указать реферала, то создаст нового, если не указать владельца, то создаст нового.
        :return Доход(IncomeFromReferrals), Реферал(Users), Владелец(Users)
    """
    async with get_db() as session_db:
        if owner_id is None: # создаём владельца
            owner = await create_new_user_fabric(user_name='owner_user')
            owner_id = owner.user_id
        else:
            result_db = await session_db.execute(select(Users).where(Users.user_id == owner_id))
            owner = result_db.scalar()
        if referral_user_id is None:
            referral = await create_new_user_fabric(user_name='referral_user')
            referral_user_id = referral.user_id
        else:
            result_db = await session_db.execute(select(Users).where(Users.user_id == referral_user_id))
            referral = result_db.scalar()
        if replenishment_id is None:
            replenishment = await create_replenishment_fabric()
            replenishment_id = replenishment.replenishment_id

        new_income = IncomeFromReferrals(
            replenishment_id=replenishment_id,
            owner_user_id = owner_id,
            referral_id = referral_user_id,
            amount = amount,
            percentage_of_replenishment = percentage_of_replenishment,
        )

        session_db.add(new_income)
        await session_db.commit()
        await session_db.refresh(new_income)

    return new_income, referral, owner



async def create_replenishment_fabric(amount: int = 110, user_id: int = None) -> Replenishments:
    """Создаёт пополнение для пользователя"""
    async with get_db() as session_db:
        if user_id is None:
            user = await create_new_user_fabric()
            user_id = user.user_id

        # создаём тип платежа (если ещё нет)
        result = await session_db.execute(select(TypePayments))
        type_payment = result.scalars().first()
        if not type_payment:
            type_payment = TypePayments(
                name_for_user="TestPay",
                name_for_admin="TestPayAdmin",
                index=1,
                commission=0.0,
            )
            session_db.add(type_payment)
            await session_db.commit()
            await session_db.refresh(type_payment)

        repl = Replenishments(
            user_id=user_id,
            type_payment_id=type_payment.type_payment_id,
            origin_amount=100,
            amount=amount, # сумма пополнения
            status="completed",
        )
        session_db.add(repl)
        await session_db.commit()
        await session_db.refresh(repl)

    return repl


async def create_type_payment_factory(
        filling_redis: bool = True,
        name_for_user: str = None,
        name_for_admin: str = None,
        is_active: bool = None,
        commission: float = None,
        index: int = None,
        extra_data: dict = None,
) -> TypePayments:
    """Создаст новый тип оплаты в БД"""
    async with get_db() as session_db:
        if index is None:
            result = await session_db.execute(select(TypePayments))
            all_types = result.scalars().all()
            index = max((service.index for service in all_types),default=-1) + 1  # вычисляем максимальный индекс

        new_type_payment = TypePayments(
            name_for_user= name_for_user if name_for_user else "Test Payment Method",
            name_for_admin= name_for_admin if name_for_admin else "Test Payment Method (Admin)",
            is_active= is_active if is_active else True,
            commission= commission if commission else 5,
            index= index,
            extra_data= extra_data if extra_data else {"api_key": "test_key", "wallet_id": "test_wallet"}
        )

        session_db.add(new_type_payment)
        await session_db.commit()
        await session_db.refresh(new_type_payment)

        if filling_redis:
            await filling_all_types_payments()

            result = await session_db.execute(select(TypePayments))
            all_types = result.scalars().all()
            for type_payment in all_types:
                await filling_types_payments_by_id(type_payment.type_payment_id)

    return new_type_payment


async def create_voucher_factory(
        filling_redis: bool = True,
        creator_id: int = None,
        expire_at: datetime = datetime.now(timezone.utc) + timedelta(days=1),
        is_valid: bool = True
) -> Vouchers:
    """Создаст новый ваучер в БД и в redis."""
    if creator_id is None:
        user = await create_new_user_fabric()
        creator_id = user.user_id

    voucher = Vouchers(
        creator_id=creator_id,
        activation_code="TESTCODE",
        amount=100,
        activated_counter=0,
        number_of_activations=5,
        expire_at=expire_at,
        is_valid=is_valid,
    )

    async with get_db() as session_db:
        session_db.add(voucher)
        await session_db.commit()
        await session_db.refresh(voucher)

    if filling_redis:
        async with get_redis() as session_redis:
            promo_dict = voucher.to_dict()
            await session_redis.set(f'voucher:{voucher.activation_code}', orjson.dumps(promo_dict))

    return voucher


async def create_ui_image_factory(key: str = "main_menu", show: bool = True, file_id: str = None) -> Tuple[UiImages, str]:
    """
       сохраняет запись UiImages в БД и возвращает (ui_image, abs_path).
    """
    from src.utils.ui_images_data import get_config
    # Подготовим директорию и файл
    conf = get_config()

    file_abs = conf.paths.ui_sections_dir / f"{key}.png"
    file_abs.write_bytes(b"fake-image-bytes")       # создаём тестовый файл

    async with get_db() as session:
        ui_image = UiImages(
            key=key,
            file_path=str(file_abs),
            file_id=file_id,
            show=show,
            updated_at=datetime.now(timezone.utc)
        )
        session.add(ui_image)
        await session.commit()
        await session.refresh(ui_image)

    # Вернём модель и абсолютный путь к файлу (для assert'ов)
    return ui_image, file_abs


async def create_transfer_moneys_fabric(
    user_from_id: int = None,
    user_where_id: int = None,
    amount: int = 100,
) -> TransferMoneys:
    if user_from_id is None:
        user = await create_new_user_fabric()
        user_from_id = user.user_id

    if user_where_id is None:
        user = await create_new_user_fabric()
        user_where_id = user.user_id

    async with get_db() as session_db:
        new_transfer = TransferMoneys(
            user_from_id = user_from_id,
            user_where_id = user_where_id,
            amount = amount
        )

        session_db.add(new_transfer)
        await session_db.commit()
        await session_db.refresh(new_transfer)

        return new_transfer


async def create_wallet_transaction_fabric(user_id: int, type: str = 'replenish', amount: int = 100) -> WalletTransaction:
    if user_id is None:
        user = await create_new_user_fabric()
        user_id = user.user_id

    async with get_db() as session:
        transaction = WalletTransaction(
            user_id = user_id,
            type = type,
            amount = amount,
            balance_before = 0,
            balance_after = 100
        )

        session.add(transaction)
        await session.commit()
        await session.refresh(transaction)
        return transaction


async def create_promo_codes_fabric(
    activation_code: str = "TESTCODE",
    min_order_amount: int = 100,
    amount: int = 100,
    discount_percentage: int = None,
    number_of_activations: int = 5,
    expire_at: datetime = datetime.now(timezone.utc) + timedelta(days=1),
    is_valid: bool = True,
) -> PromoCodes:
    promo = PromoCodes(
        activation_code=activation_code,
        min_order_amount=min_order_amount,
        amount=amount,
        discount_percentage=discount_percentage,
        number_of_activations=number_of_activations,
        expire_at=expire_at,
        is_valid=is_valid,
    )

    async with get_db() as session_db:
        session_db.add(promo)
        await session_db.commit()
        await session_db.refresh(promo)

    async with get_redis() as session_redis:
        promo_dict = promo.to_dict()
        await session_redis.set(f'promo_code:{promo.activation_code}', orjson.dumps(promo_dict))

    return promo


async def create_promo_code_activation_fabric(
    promo_code_id: int = None,
    user_id: int = None,
) -> ActivatedPromoCodes:
    if promo_code_id is None:
        promo = await create_promo_codes_fabric()
        promo_code_id = promo.promo_code_id

    if user_id is None:
        user = await create_new_user_fabric()
        user_id = user.user_id

    async with get_db() as session_db:
        new_activated_promo_codes = ActivatedPromoCodes(
            promo_code_id=promo_code_id,
            user_id=user_id
        )

        session_db.add(new_activated_promo_codes)
        await session_db.commit()
        await session_db.refresh(new_activated_promo_codes)

        return new_activated_promo_codes


async def create_sent_mass_message_fabric(
    admin_id: int = None,
    content: str = "content",
    photo_path: str = "photo_path",
    button_url: str = "https://example.com",
    number_received: int = 10,
    number_sent: int = 10,
) -> SentMasMessages:
    if not admin_id:
        admin = await create_admin_fabric() 
        admin_id = admin.user_id
        
    async with get_db() as session_db: 
        sent_message = SentMasMessages(
            user_id = admin_id,
            content = content,
            photo_path = photo_path,
            button_url = button_url,
            number_received = number_received,
            number_sent = number_sent
        )
        session_db.add(sent_message)
        await session_db.commit()
        await session_db.refresh(sent_message)

    return sent_message


async def create_backup_log_fabric(
    storage_file_name: str = None,
    storage_encrypted_dek_name: str = None,
    encrypted_dek_b64: str = "encrypted_dek_b64",
    dek_nonce_b64: str = "dek_nonce_b64",
    size_bytes: int = 12345,
) -> BackupLogs:
    if storage_file_name is None:
        storage_file_name = str(uuid.uuid4())

    if storage_encrypted_dek_name is None:
        storage_encrypted_dek_name = str(uuid.uuid4())

    async with get_db() as session_db:
        log = BackupLogs(
            storage_file_name=storage_file_name,
            storage_encrypted_dek_name=storage_encrypted_dek_name,
            encrypted_dek_b64 = encrypted_dek_b64,
            dek_nonce_b64 = dek_nonce_b64,
            size_bytes = size_bytes
        )
        session_db.add(log)
        await session_db.commit()
        await session_db.refresh(log)

    return log
