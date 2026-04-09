from typing import Optional

from src.database.models.categories import ProductType
from src.exceptions.business import InvalidQuantityProducts
from src.models.read_models import StartPurchaseUniversal, StartPurchaseUniversalOne
from src.application.models.categories.categories_cache_filler_service import CategoriesCacheFillerService
from src.application.models.purchases.accounts.account_purchase_service import AccountPurchaseService
from src.application.models.purchases.universal.universal_purchase_service import UniversalPurchaseService


class PurchaseService:

    def __init__(
        self,
        account_purchase_service: AccountPurchaseService,
        universal_purchase_service: UniversalPurchaseService,
        categories_cache_filler: CategoriesCacheFillerService,
    ):
        self.account_purchase_service = account_purchase_service
        self.universal_purchase_service = universal_purchase_service
        self.categories_cache_filler = categories_cache_filler

    async def purchase(
        self,
        user_id: int,
        category_id: int,
        quantity_products: int,
        promo_code_id: Optional[int],
        product_type: ProductType,
        language: str,
    ) -> bool:
        """
        :exception InvalidQuantityProducts: Если количество товаров меньше либо равно нулю.
        """
        if quantity_products <= 0:
            raise InvalidQuantityProducts()

        if product_type == ProductType.ACCOUNT:
            result = await self.purchase_accounts(user_id, category_id, quantity_products, promo_code_id)
        elif product_type == ProductType.UNIVERSAL:
            result = await self.purchase_universal(
                user_id,
                category_id,
                quantity_products,
                language,
                promo_code_id,
            )
        else:
            result = False

        await self.categories_cache_filler.fill_need_category(category_id)
        return result

    async def purchase_accounts(
        self,
        user_id: int,
        category_id: int,
        quantity_accounts: int,
        promo_code_id: Optional[int] = None,
    ) -> bool:
        data = await self.account_purchase_service.start_purchase(
            user_id=user_id,
            category_id=category_id,
            quantity_accounts=quantity_accounts,
            promo_code_id=promo_code_id,
        )

        valid_list = await self.account_purchase_service.verify_reserved_accounts(
            data.product_accounts,
            data.type_service_account,
            data.purchase_request_id,
        )
        if valid_list is False:
            await self.account_purchase_service.cancel_purchase_request(
                user_id=user_id,
                category_id=category_id,
                mapping=[],
                sold_account_ids=[],
                purchase_ids=[],
                total_amount=data.total_amount,
                purchase_request_id=data.purchase_request_id,
                product_accounts=data.product_accounts,
            )
            return False

        data.product_accounts = valid_list
        return await self.account_purchase_service.finalize_purchase(user_id, data)

    async def purchase_universal(
        self,
        user_id: int,
        category_id: int,
        quantity_products: int,
        language: str,
        promo_code_id: Optional[int] = None,
    ) -> bool:
        data = await self.universal_purchase_service.start_purchase(
            user_id=user_id,
            category_id=category_id,
            quantity_products=quantity_products,
            promo_code_id=promo_code_id,
            language=language,
        )

        if isinstance(data, StartPurchaseUniversal):
            full_products = await self.universal_purchase_service.verify_reserved_universal_different(
                data.full_reserved_products,
                data.purchase_request_id,
            )
            if full_products is False:
                await self.universal_purchase_service.cancel_purchase_different(
                    user_id=user_id,
                    category_id=category_id,
                    mapping=[],
                    sold_universal_ids=[],
                    purchase_ids=[],
                    total_amount=data.total_amount,
                    purchase_request_id=data.purchase_request_id,
                    product_universal=data.full_reserved_products,
                )
                return False

            data.full_reserved_products = full_products
            return await self.universal_purchase_service.finalize_purchase_different(user_id, data)

        if isinstance(data, StartPurchaseUniversalOne):
            valid = await self.universal_purchase_service.verify_reserved_universal_one(data.full_product)
            if valid is False:
                await self.universal_purchase_service.cancel_purchase_one(
                    user_id=user_id,
                    category_id=category_id,
                    paths_created_storage=[],
                    sold_universal_ids=[],
                    storage_universal_ids=[],
                    purchase_ids=[],
                    total_amount=data.total_amount,
                    purchase_request_id=data.purchase_request_id,
                    product_universal=data.full_product,
                )
                return False

            return await self.universal_purchase_service.finalize_purchase_one(user_id, data)

        return False
