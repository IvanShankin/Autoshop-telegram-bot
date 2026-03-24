from typing import Optional, List

from orjson import orjson

from src.read_models import SettingsDTO, StickersDTO, UiImagesDTO
from src.read_models.other import ReferralLevelsDTO, TypePaymentsDTO, UsersDTO, PromoCodesDTO, VouchersDTO
from src.repository.redis.base import BaseRedisRepo


class SettingsCacheRepository(BaseRedisRepo):

    def _key(self) -> str:
        return "settings"

    async def set(self, settings: SettingsDTO) -> None:
        await self._set_one(self._key(), settings)

    async def get(self) -> Optional[SettingsDTO]:
        return await self._get_one(self._key(), SettingsDTO)


class UsersCacheRepository(BaseRedisRepo):

    def _key(self, user_id: int) -> str:
        return f"user:{user_id}"

    async def set(self, user: UsersDTO, ttl: int) -> None:
        await self._set_one(self._key(user.user_id), user, ttl=ttl)

    async def get(self, user_id: int) -> Optional[UsersDTO]:
        return await self._get_one(self._key(user_id), UsersDTO)


class StickersCacheRepository(BaseRedisRepo):

    def _key(self, key: str) -> str:
        return f"sticker:{key}"

    async def set_many(self, stickers: List[StickersDTO]) -> None:
        async with self.redis_session.pipeline(transaction=False) as pipe:
            for sticker in stickers:
                await pipe.set(
                    self._key(sticker.key),
                    orjson.dumps(sticker.model_dump())
                )
            await pipe.execute()

    async def get(self, key: str) -> Optional[StickersDTO]:
        return await self._get_one(self._key(key), StickersDTO)


class UiImagesCacheRepository(BaseRedisRepo):

    def _key(self, key: str) -> str:
        return f"ui_image:{key}"

    async def set(self, image: UiImagesDTO) -> None:
        await self._set_one(self._key(image.key), image)

    async def get(self, key: str) -> Optional[UiImagesDTO]:
        return await self._get_one(self._key(key), UiImagesDTO)


class ReferralLevelsCacheRepository(BaseRedisRepo):

    def _key(self) -> str:
        return "referral_levels"

    async def set(self, levels: List[ReferralLevelsDTO]) -> None:
        await self._set_many(self._key(), levels)

    async def get(self) -> List[ReferralLevelsDTO]:
        return await self._get_many(self._key(), ReferralLevelsDTO)



class TypePaymentsCacheRepository(BaseRedisRepo):

    def _key_all(self) -> str:
        return "all_types_payments"

    def _key_one(self, type_payment_id: int) -> str:
        return f"type_payments:{type_payment_id}"

    async def set_all(self, items: List[TypePaymentsDTO]) -> None:
        await self._set_many(self._key_all(), items)

    async def get_all(self) -> List[TypePaymentsDTO]:
        return await self._get_many(self._key_all(), TypePaymentsDTO)

    async def set_one(self, item: TypePaymentsDTO) -> None:
        await self._set_one(self._key_one(item.type_payment_id), item)

    async def delete_one(self, type_payment_id: int) -> None:
        await self.redis_session.delete(self._key_one(type_payment_id))


class AdminsCacheRepository(BaseRedisRepo):

    def _key(self, user_id: int) -> str:
        return f"admin:{user_id}"

    async def set(self, user_id: int) -> None:
        await self.redis_session.set(self._key(user_id), "_")

    async def exists(self, user_id: int) -> bool:
        return await self.redis_session.exists(self._key(user_id)) == 1


class BannedAccountsCacheRepository(BaseRedisRepo):

    def _key(self, user_id: int) -> str:
        return f"banned_account:{user_id}"

    async def set(self, user_id: int, reason: str) -> None:
        await self.redis_session.set(self._key(user_id), reason)

    async def get(self, user_id: int) -> Optional[str]:
        return await self.redis_session.get(self._key(user_id))



class PromoCodesCacheRepository(BaseRedisRepo):

    def _key(self, code: str) -> str:
        return f"promo_code:{code}"

    async def set(self, promo: PromoCodesDTO, ttl: Optional[int]) -> None:
        await self._set_one(self._key(promo.activation_code), promo, ttl=ttl)

    async def get(self, code: str) -> Optional[PromoCodesDTO]:
        return await self._get_one(self._key(code), PromoCodesDTO)


class VouchersCacheRepository(BaseRedisRepo):

    def _key_by_user(self, user_id: int) -> str:
        return f"voucher_by_user:{user_id}"

    def _key_one(self, code: str) -> str:
        return f"voucher:{code}"

    async def set_by_user(self, user_id: int, vouchers: List[VouchersDTO], ttl: int):
        await self._set_many(self._key_by_user(user_id), vouchers, ttl=ttl)

    async def get_by_user(self, user_id: int) -> List[VouchersDTO]:
        return await self._get_many(self._key_by_user(user_id), VouchersDTO)

    async def set_by_code(self, voucher: VouchersDTO):
        await self._set_one(self._key_one(voucher.activation_code), voucher)

    async def get_by_code(self, code: str) -> Optional[VouchersDTO]:
        return await self._get_one(self._key_one(code), VouchersDTO)


