from datetime import datetime, timezone
from logging import Logger
from typing import Iterable, Optional

from redis.asyncio import Redis

from src.config import Config
from src.database.models.discount.schemas import SmallVoucher
from src.models.read_models import SoldAccountFull, SoldAccountSmall
from src.models.read_models.categories.product_universal import SoldUniversalFull, SoldUniversalSmall
from src.models.read_models.other import VouchersDTO
from src.repository.database.admins import AdminsRepository
from src.repository.database.categories import CategoriesRepository
from src.repository.database.categories.accounts import (
    ProductAccountsRepository,
    SoldAccountsRepository,
)
from src.repository.database.categories.universal import (
    ProductUniversalRepository,
    SoldUniversalRepository,
)
from src.repository.database.discount import PromoCodeRepository, VouchersRepository
from src.repository.database.referrals import ReferralLevelsRepository
from src.repository.database.systems import (
    StickersRepository,
    TypePaymentsRepository,
    UiImagesRepository,
    SettingsRepository,
)
from src.repository.database.users import BannedAccountsRepository, UsersRepository
from src.repository.redis import (
    AccountsCacheRepository,
    AdminsCacheRepository,
    BannedAccountsCacheRepository,
    CategoriesCacheRepository,
    PromoCodesCacheRepository,
    ReferralLevelsCacheRepository,
    SettingsCacheRepository,
    SoldUniversalCacheRepository,
    SoldUniversalSingleCacheRepository,
    StickersCacheRepository,
    TypePaymentsCacheRepository,
    UiImagesCacheRepository,
    VouchersCacheRepository,
)
from src.application.models.categories import CategoriesCacheFillerService
from src.application.models.products.accounts import AccountsCacheFillerService
from src.application.models.products.universal import UniversalCacheFillerService


class CacheWarmupService:

    def __init__(
        self,
        settings_repo: SettingsRepository,
        stickers_repo: StickersRepository,
        referral_levels_repo: ReferralLevelsRepository,
        type_payments_repo: TypePaymentsRepository,
        admins_repo: AdminsRepository,
        banned_accounts_repo: BannedAccountsRepository,
        categories_repo: CategoriesRepository,
        product_accounts_repo: ProductAccountsRepository,
        sold_accounts_repo: SoldAccountsRepository,
        product_universal_repo: ProductUniversalRepository,
        sold_universal_repo: SoldUniversalRepository,
        users_repo: UsersRepository,
        promo_codes_repo: PromoCodeRepository,
        ui_image_repo: UiImagesRepository,
        vouchers_repo: VouchersRepository,

        settings_cache_repo: SettingsCacheRepository,
        stickers_cache_repo: StickersCacheRepository,
        referral_levels_cache_repo: ReferralLevelsCacheRepository,
        type_payments_cache_repo: TypePaymentsCacheRepository,
        admins_cache_repo: AdminsCacheRepository,
        banned_accounts_cache_repo: BannedAccountsCacheRepository,
        categories_cache_repo: CategoriesCacheRepository,
        promo_codes_cache_repo: PromoCodesCacheRepository,
        vouchers_cache_repo: VouchersCacheRepository,
        ui_images_cache_repo: UiImagesCacheRepository,
        accounts_cache_repo: AccountsCacheRepository,
        sold_universal_cache_repo: SoldUniversalCacheRepository,
        sold_universal_single_cache_repo: SoldUniversalSingleCacheRepository,
        accounts_cache_filler_service: AccountsCacheFillerService,
        universal_cache_filler_service: UniversalCacheFillerService,
        category_cache_filler_service: CategoriesCacheFillerService,
        session_redis: Redis,
        logger: Logger,
        conf: Config,
    ):
        self.settings_repo = settings_repo
        self.stickers_repo = stickers_repo
        self.referral_levels_repo = referral_levels_repo
        self.type_payments_repo = type_payments_repo
        self.admins_repo = admins_repo
        self.banned_accounts_repo = banned_accounts_repo
        self.categories_repo = categories_repo
        self.product_accounts_repo = product_accounts_repo
        self.sold_accounts_repo = sold_accounts_repo
        self.product_universal_repo = product_universal_repo
        self.sold_universal_repo = sold_universal_repo
        self.users_repo = users_repo
        self.promo_codes_repo = promo_codes_repo
        self.ui_image_repo = ui_image_repo
        self.vouchers_repo = vouchers_repo

        self.settings_cache_repo = settings_cache_repo
        self.stickers_cache_repo = stickers_cache_repo
        self.referral_levels_cache_repo = referral_levels_cache_repo
        self.type_payments_cache_repo = type_payments_cache_repo
        self.admins_cache_repo = admins_cache_repo
        self.banned_accounts_cache_repo = banned_accounts_cache_repo
        self.categories_cache_repo = categories_cache_repo
        self.promo_codes_cache_repo = promo_codes_cache_repo
        self.vouchers_cache_repo = vouchers_cache_repo
        self.ui_images_cache_repo = ui_images_cache_repo
        self.accounts_cache_repo = accounts_cache_repo
        self.sold_universal_cache_repo = sold_universal_cache_repo
        self.sold_universal_single_cache_repo = sold_universal_single_cache_repo
        self.accounts_cache_filler_service = accounts_cache_filler_service
        self.universal_cache_filler_service = universal_cache_filler_service
        self.category_cache_filler_service = category_cache_filler_service
        self.logger = logger
        self.session_redis = session_redis
        self.conf = conf

    async def warmup(self):
        await self._flush_redis()
        await self._fill_settings()
        await self._fill_stickers()
        await self._fill_referral_levels()
        await self._fill_type_payments()
        await self._fill_ui_images()
        await self._fill_vouchers_per_user()
        await self._fill_voucher_codes()
        await self._fill_promo_codes()
        await self._fill_admins()
        await self._fill_banned_accounts()
        await self._fill_categories()
        await self._fill_product_accounts()
        await self._fill_product_universal()
        await self._fill_sold_accounts()
        await self._fill_sold_universal()
        self.logger.info("Redis filling successfully")

    async def _flush_redis(self):
        await self.session_redis.flushall()

    async def _fill_settings(self):
        settings = await self.settings_repo.get()
        if settings:
            await self.settings_cache_repo.set(settings)

    async def _fill_stickers(self):
        stickers = await self.stickers_repo.get_all()
        if not stickers:
            return
        await self.stickers_cache_repo.set_many(stickers)
        for sticker in stickers:
            await self.stickers_cache_repo.set(sticker)

    async def _fill_referral_levels(self):
        referral_levels = await self.referral_levels_repo.get_all()
        if referral_levels:
            await self.referral_levels_cache_repo.set(referral_levels)

    async def _fill_type_payments(self):
        types = await self.type_payments_repo.get_all()
        if not types:
            return
        await self.type_payments_cache_repo.set_all(types)
        for item in types:
            await self.type_payments_cache_repo.set_one(item)

    async def _fill_ui_images(self):
        images = await self.ui_image_repo.get_all()
        for image in images:
            await self.ui_images_cache_repo.set(image)

    async def _fill_vouchers_per_user(self):
        ttl = int(self.conf.redis_time_storage.all_voucher.total_seconds())
        async for user_id in self.users_repo.gen_user_ids():
            vouchers = await self.vouchers_repo.get_valid_by_page(user_id=user_id)
            small_items = [self._map_to_small_voucher(v) for v in vouchers]
            await self.vouchers_cache_repo.set_small_by_user(
                user_id=user_id,
                vouchers=small_items,
                ttl=ttl,
            )

    async def _fill_voucher_codes(self):
        vouchers = await self.vouchers_repo.get_valid_by_page()
        for voucher in vouchers:
            ttl = self._calc_ttl(voucher.expire_at)
            await self.vouchers_cache_repo.set_by_code(voucher, ttl=ttl)

    async def _fill_promo_codes(self):
        promo_codes = await self.promo_codes_repo.get_page()
        for promo in promo_codes:
            ttl = self._calc_ttl(promo.expire_at)
            await self.promo_codes_cache_repo.set(promo, ttl=ttl)

    async def _fill_admins(self):
        admin_ids = await self.admins_repo.get_all_user_ids()
        for user_id in admin_ids:
            await self.admins_cache_repo.set(user_id)

    async def _fill_banned_accounts(self):
        banned_accounts = await self.banned_accounts_repo.get_all()
        for ban in banned_accounts:
            await self.banned_accounts_cache_repo.set(ban.user_id, ban.reason)

    async def _fill_categories(self):
        category_ids = await self.categories_repo.get_all_ids()
        if not category_ids:
            return
        await self.category_cache_filler_service.fill_need_category(
            categories_ids=category_ids
        )

    async def _fill_product_accounts(self):
        category_ids = await self.product_accounts_repo.get_all_category_ids()
        for category_id in set(category_ids):
            await self.accounts_cache_filler_service.fill_product_accounts_by_category_id(
                category_id
            )
        account_ids = await self.product_accounts_repo.get_all_account_ids()
        for account_id in account_ids:
            await self.accounts_cache_filler_service.fill_product_account_by_account_id(
                account_id
            )

    async def _fill_product_universal(self):
        category_ids = await self.product_universal_repo.get_all_category_ids()
        for category_id in set(category_ids):
            await self.universal_cache_filler_service.fill_product_universal_by_category_id(
                category_id
            )
        product_ids = await self.product_universal_repo.get_all_ids()
        for product_id in product_ids:
            await self.universal_cache_filler_service.fill_product_universal_by_product_id(
                product_id
            )

    async def _fill_sold_accounts(self):
        owner_ids = await self.sold_accounts_repo.get_all_owner_ids()
        for owner_id in owner_ids:
            await self._fill_sold_accounts_by_owner(owner_id)

        sold_ids = await self.sold_accounts_repo.get_all_ids()
        for sold_id in sold_ids:
            await self._fill_sold_account_by_id(sold_id)

    async def _fill_sold_accounts_by_owner(self, owner_id: int):
        sold_accounts = await self.sold_accounts_repo.get_by_owner_id_with_relations(
            owner_id,
            active_only=True,
        )
        if not sold_accounts:
            await self.accounts_cache_repo.delete_sold_accounts_by_owner_id(owner_id)
            return

        languages = self._extract_account_languages(sold_accounts)
        if not languages:
            await self.accounts_cache_repo.delete_sold_accounts_by_owner_id(owner_id)
            return

        for lang in languages:
            items = [
                SoldAccountSmall.from_orm_with_translation(account, lang=lang)
                for account in sold_accounts
            ]
            await self.accounts_cache_repo.set_sold_accounts_by_owner_id(
                owner_id,
                items,
                lang,
            )

    async def _fill_sold_account_by_id(self, sold_account_id: int):
        sold_account = await self.sold_accounts_repo.get_by_id_with_relations(
            sold_account_id,
            active_only=True,
        )
        if not sold_account:
            await self.accounts_cache_repo.delete_sold_accounts_by_account_id(sold_account_id)
            return

        languages = self._extract_account_languages([sold_account])
        if not languages:
            await self.accounts_cache_repo.delete_sold_accounts_by_account_id(sold_account_id)
            return

        for lang in languages:
            dto = SoldAccountFull.from_orm_with_translation(sold_account, lang=lang)
            await self.accounts_cache_repo.set_sold_accounts_by_account_id(dto, lang)

    async def _fill_sold_universal(self):
        owner_ids = await self.sold_universal_repo.get_all_owner_ids()
        owner_ttl = int(
            self.conf.redis_time_storage.sold_universal_account_product_by_owner.total_seconds()
        )
        for owner_id in owner_ids:
            await self._fill_sold_universal_by_owner(owner_id, owner_ttl)

        sold_ids = await self.sold_universal_repo.get_all_ids()
        sold_ttl = int(
            self.conf.redis_time_storage.sold_universal_product_by_product.total_seconds()
        )
        for sold_id in sold_ids:
            await self._fill_sold_universal_by_id(sold_id, sold_ttl)

    async def _fill_sold_universal_by_owner(self, owner_id: int, ttl: int):
        sold_items = await self.sold_universal_repo.get_by_owner_with_relations(
            owner_id,
            active_only=True,
        )
        if not sold_items:
            await self.sold_universal_cache_repo.delete_by_owner(owner_id)
            return

        languages = self._extract_universal_languages(sold_items)
        if not languages:
            await self.sold_universal_cache_repo.delete_by_owner(owner_id)
            return

        for lang in languages:
            items = [
                SoldUniversalSmall.from_orm_model(sold, lang)
                for sold in sold_items
            ]
            await self.sold_universal_cache_repo.set_by_owner(
                owner_id,
                lang,
                items,
                ttl,
            )

    async def _fill_sold_universal_by_id(self, sold_id: int, ttl: int):
        sold_item = await self.sold_universal_repo.get_by_id_with_relations(
            sold_id,
            active_only=True,
        )
        if not sold_item:
            await self.sold_universal_single_cache_repo.delete_by_id(sold_id)
            return

        languages = self._extract_universal_languages([sold_item])
        if not languages:
            await self.sold_universal_single_cache_repo.delete_by_id(sold_id)
            return

        for lang in languages:
            dto = SoldUniversalFull.from_orm_model(sold_item, language=lang)
            await self.sold_universal_single_cache_repo.set(dto, lang, ttl)

    @staticmethod
    def _extract_account_languages(accounts: Iterable["SoldAccounts"]):
        return {
            translate.lang
            for account in accounts
            for translate in account.translations
            if translate.lang
        }

    @staticmethod
    def _extract_universal_languages(items: Iterable["SoldUniversal"]):
        return {
            translate.lang
            for item in items
            for translate in item.storage.translations
            if translate.lang
        }

    @staticmethod
    def _calc_ttl(expire_at: Optional[datetime]) -> Optional[int]:
        if not expire_at:
            return None
        seconds = int((expire_at - datetime.now(timezone.utc)).total_seconds())
        return seconds if seconds > 0 else None

    @staticmethod
    def _map_to_small_voucher(voucher: VouchersDTO) -> SmallVoucher:
        return SmallVoucher(
            voucher_id=voucher.voucher_id,
            creator_id=voucher.creator_id or 0,
            amount=voucher.amount,
            activation_code=voucher.activation_code,
            activated_counter=voucher.activated_counter,
            number_of_activations=voucher.number_of_activations,
            is_valid=voucher.is_valid,
        )

