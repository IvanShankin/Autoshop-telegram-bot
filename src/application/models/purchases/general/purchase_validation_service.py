from typing import Optional

from src.config import Config
from src.exceptions import CategoryNotFound, NotEnoughMoney
from src.exceptions.domain import UserNotFound
from src.models.read_models import ResultCheckCategory
from src.repository.database.categories import CategoriesRepository
from src.repository.database.users import UsersRepository
from src.application._database.discounts.utils.calculation import discount_calculation
from src.models.read_models import CategoryFull


class PurchaseValidationService:

    def __init__(
        self,
        categories_repo: CategoriesRepository,
        users_repo: UsersRepository,
        conf: Config,
    ):
        self.categories_repo = categories_repo
        self.users_repo = users_repo
        self.conf = conf

    async def check_category_and_money(
        self,
        user_id: int,
        category_id: int,
        quantity_products: int,
        promo_code_id: Optional[int],
    ) -> ResultCheckCategory:
        """
        :exception CategoryNotFound: Если категория не найдена или отсутствуют переводы.
        :exception UserNotFound: Если пользователь не найден.
        :exception NotEnoughMoney: Если недостаточно средств.
        :summary: Получает категорию, считает скидку и проверяет баланс перед покупкой.
        """
        category_orm = await self.categories_repo.get_by_id_with_translations(category_id)
        translations = (
            category_orm.translations
            if category_orm and getattr(category_orm, "translations", None)
            else []
        )
        if not category_orm or not translations:
            raise CategoryNotFound("Данной категории больше не существует")

        quantity_map = await self.categories_repo.get_quantity_products_map([category_id])
        category_full = CategoryFull.from_orm_with_translation(
            category=category_orm,
            quantity_product=quantity_map.get(category_id, 0),
            lang=self.conf.app.default_lang,
            fallback=self.conf.app.default_lang,
        )

        original_price_per = category_full.price or 0
        original_total = original_price_per * quantity_products

        if promo_code_id:
            discount_amount, _ = await discount_calculation(original_total, promo_code_id=promo_code_id)
        else:
            discount_amount = 0

        final_total = max(0, original_total - discount_amount)

        user = await self.users_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound()

        if user.balance < final_total:
            raise NotEnoughMoney(
                "Недостаточно средств для покупки товара",
                final_total - user.balance,
            )

        return ResultCheckCategory(
            category=category_full,
            translations_category=translations,
            final_total=final_total,
            user_balance_before=user.balance,
        )
