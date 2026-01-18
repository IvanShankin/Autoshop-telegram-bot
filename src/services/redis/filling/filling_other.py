from datetime import datetime, UTC

import orjson
from sqlalchemy import select

from src.services.database.admins.models import Admins
from src.services.database.core.database import get_db
from src.services.database.discounts.models import PromoCodes, Vouchers
from src.services.database.discounts.models import SmallVoucher
from src.services.database.referrals.models import ReferralLevels
from src.services.database.system.models import Settings, TypePayments
from src.services.database.system.models import UiImages
from src.services.database.users.models import Users, BannedAccounts
from src.services.redis.core_redis import get_redis
from src.services.redis.filling.helpers_func import _fill_redis_single_objects
from src.services.redis.time_storage import TIME_USER, TIME_ALL_VOUCHER


async def filling_settings():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(Settings))
        settings = result_db.scalars().first()

        if settings:
            async with get_redis() as session_redis:
                await session_redis.set("settings", orjson.dumps(settings.to_dict()))

async def filling_ui_image(key: str):
    async with get_db() as session_db:
        result_db = await session_db.execute(select(UiImages).where(UiImages.key == key))
        ui_image = result_db.scalar_one_or_none()

        if ui_image:
            async with get_redis() as session_redis:
                await session_redis.set(f"ui_image:{ui_image.key}", value=orjson.dumps(ui_image.to_dict()))

async def filling_referral_levels():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(ReferralLevels))
        referral_levels = result_db.scalars().all()

        if referral_levels:
            async with get_redis() as session_redis:
                list_for_redis = [referral.to_dict() for referral in referral_levels]
                await session_redis.set("referral_levels", orjson.dumps(list_for_redis))


async def filling_all_types_payments():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(TypePayments).order_by(TypePayments.index.asc()))
        types_payments = result_db.scalars().all()

        # сохраним даже пустой список
        async with get_redis() as session_redis:
            list_for_redis = [type_pay.to_dict() for type_pay in types_payments]
            await session_redis.set("all_types_payments", orjson.dumps(list_for_redis))


async def filling_types_payments_by_id(type_payment_id: int):
    async with get_db() as session_db:
        result_db = await session_db.execute(select(TypePayments).where(TypePayments.type_payment_id == type_payment_id))
        type_payment = result_db.scalar_one_or_none()

        async with get_redis() as session_redis:
            if type_payment:
                await session_redis.set(f'type_payments:{type_payment_id}', orjson.dumps(type_payment.to_dict()))
            else:
                await session_redis.delete(f'type_payments:{type_payment_id}')


async def filling_users():
    await _fill_redis_single_objects(
        model=Users,
        key_prefix='user',
        key_extractor=lambda user: user.user_id,
        ttl=lambda user: TIME_USER
    )


async def filling_user(user: Users):
    async with get_redis() as session_redis:
        await session_redis.setex(f"user:{user.user_id}", TIME_USER, orjson.dumps(user.to_dict()))


async def filling_admins():
    await _fill_redis_single_objects(
        model=Admins,
        key_prefix='admin',
        key_extractor=lambda admin: admin.user_id,
        value_extractor=lambda x: '_'
    )


async def filling_banned_accounts():
    await _fill_redis_single_objects(
        model=BannedAccounts,
        key_prefix='banned_account',
        key_extractor=lambda banned_accounts: banned_accounts.user_id,
        value_extractor=lambda x: x.reason
    )



async def filling_promo_code():
    await _fill_redis_single_objects(
        model=PromoCodes,
        key_prefix='promo_code',
        key_extractor=lambda promo_code: promo_code.activation_code,
        field_condition=(PromoCodes.is_valid == True),
        ttl=lambda promo_code: promo_code.expire_at - datetime.now(UTC) if promo_code.expire_at else None
    )


async def filling_voucher_by_user_id(user_id: int):
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(Vouchers)
            .where(
                (Vouchers.creator_id == user_id) &
                (Vouchers.is_valid == True) &
                (Vouchers.is_created_admin == False)
            ).order_by(Vouchers.start_at.desc())
        )
        vouchers = result_db.scalars().all()

    async with get_redis() as session_redis:
        result_list = [ SmallVoucher.from_orm_model(voucher).model_dump() for voucher in vouchers ]
        await session_redis.delete(f'voucher_by_user:{user_id}')
        await session_redis.setex(f'voucher_by_user:{user_id}', TIME_ALL_VOUCHER, orjson.dumps(result_list))


async def filling_vouchers():
    await _fill_redis_single_objects(
        model=Vouchers,
        key_prefix='voucher',
        key_extractor=lambda vouchers: vouchers.activation_code,
        field_condition=(Vouchers.is_valid == True),
        ttl=lambda vouchers: vouchers.expire_at - datetime.now(UTC) if vouchers.expire_at else None
    )

