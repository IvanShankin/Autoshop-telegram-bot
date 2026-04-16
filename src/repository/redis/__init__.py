from src.repository.redis.accounts import AccountsCacheRepository

from src.repository.redis.categories import CategoriesCacheRepository

from src.repository.redis.other import (
    AdminsCacheRepository,
    BannedAccountsCacheRepository,
    DollarRateCacheRepository,
    PromoCodesCacheRepository,
    ReferralLevelsCacheRepository,
    SettingsCacheRepository,
    StickersCacheRepository,
    SubscriptionCacheRepository,
    TypePaymentsCacheRepository,
    UiImagesCacheRepository,
    UsersCacheRepository,
    VouchersCacheRepository,
)

from src.repository.redis.product_universal import (
    ProductUniversalCacheRepository,
    ProductUniversalSingleCacheRepository,
    SoldUniversalCacheRepository,
    SoldUniversalSingleCacheRepository,
)

__all__ = [
    # accounts.py
    "AccountsCacheRepository",

    # categories.py
    "CategoriesCacheRepository",

    # other.py
    "AdminsCacheRepository",
    "BannedAccountsCacheRepository",
    "DollarRateCacheRepository",
    "PromoCodesCacheRepository",
    "ReferralLevelsCacheRepository",
    "SettingsCacheRepository",
    "StickersCacheRepository",
    "SubscriptionCacheRepository",
    "TypePaymentsCacheRepository",
    "UiImagesCacheRepository",
    "UsersCacheRepository",
    "VouchersCacheRepository",

    # product_universal.py
    "ProductUniversalCacheRepository",
    "ProductUniversalSingleCacheRepository",
    "SoldUniversalCacheRepository",
    "SoldUniversalSingleCacheRepository",
]