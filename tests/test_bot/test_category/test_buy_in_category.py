import pytest
from types import SimpleNamespace
from src.utils.i18n import get_text
from tests.helpers.fake_aiogram.fake_aiogram_module import FakeCallbackQuery


class TestBuyAccount:
    @pytest.mark.asyncio
    async def test_buy_acc_not_enough_accounts_alerts_user(
            self,
            patch_fake_aiogram,
            replacement_fake_bot_fix,
            create_new_user,
            create_category,
    ):
        """
        Если category.quantity_product < BuyProduct.quantity_products — показывается alert,
        сообщение не редактируется.
        """
        from src.modules.categories.handlers.handler_categories import buy_in_category

        fake_bot = replacement_fake_bot_fix
        user = await create_new_user(balance=1000)
        category = await create_category(is_product_storage=True)
        # quantity_product_account по умолчанию 0, так что условия нехватки выполняются

        cb = FakeCallbackQuery(data=f"buy_in_category:{category.category_id}:5:None", chat_id=user.user_id,
                               username=user.username)
        cb.message = SimpleNamespace(message_id=10)

        await buy_in_category(cb, user)

        # Проверяем: сообщение не редактировалось (только alert)
        assert not fake_bot.check_str_in_edited_messages("Thank you for your purchase"), \
            "Сообщение неожиданно отредактировалось, хотя должно быть только alert о нехватке аккаунтов"

    @pytest.mark.asyncio
    async def test_buy_acc_min_amount_for_promo_not_reached(
            self,
            patch_fake_aiogram,
            replacement_fake_bot_fix,
            create_new_user,
            create_category,
            create_promo_code,
    ):
        """
        Если promo_code.min_order_amount > total_sum — показывается alert о минимальной сумме.
        """
        from src.modules.categories.handlers.handler_categories import buy_in_category

        fake_bot = replacement_fake_bot_fix
        user = await create_new_user(balance=10000)
        category = await create_category(price=50, is_product_storage=True)
        promo = await create_promo_code()  # min_order_amount=100

        # BuyProduct.quantity_products = 1 => total_sum = 50 < 100
        cb = FakeCallbackQuery(data=f"buy_in_category:{category.category_id}:1:{promo.promo_code_id}",
                               chat_id=user.user_id, username=user.username)
        cb.message = SimpleNamespace(message_id=20)

        await buy_in_category(cb, user)

        # Проверяем отсутствие редактирования (был alert)
        assert not fake_bot.check_str_in_edited_messages("Thank you for your purchase"), \
            "Неожиданное редактирование сообщения при недостижении минимальной суммы промокода"

    @pytest.mark.asyncio
    async def test_buy_acc_invalid_promo_code_alert(
            self,
            patch_fake_aiogram,
            replacement_fake_bot_fix,
            create_new_user,
            create_category,
            monkeypatch,
    ):
        """
        Если discount_calculation выбрасывает InvalidPromoCode — показывается alert,
        сообщение не редактируется.
        """
        from src.modules.categories.handlers.handler_categories import buy_in_category
        from src.exceptions import InvalidPromoCode

        fake_bot = replacement_fake_bot_fix
        user = await create_new_user(balance=10000)
        category = await create_category(is_product_storage=True)

        async def fake_discount_calculation(amount, promo_code_id=None):
            raise InvalidPromoCode()

        from src.services.database.discounts.utils import calculation
        monkeypatch.setattr(calculation, "discount_calculation", fake_discount_calculation)

        cb = FakeCallbackQuery(data=f"buy_in_category:{category.category_id}:1:9999",
                               chat_id=user.user_id, username=user.username)
        cb.message = SimpleNamespace(message_id=30)

        await buy_in_category(cb, user)

        assert not fake_bot.check_str_in_edited_messages("Thank you for your purchase"), \
            "Сообщение не должно было редактироваться при невалидном промокоде"

    @pytest.mark.asyncio
    async def test_buy_acc_not_enough_money_edits_message(
            self,
            patch_fake_aiogram,
            replacement_fake_bot_fix,
            create_new_user,
            create_category,
            create_product_account
    ):
        """
        Если balance < total_sum — редактируется сообщение о нехватке средств.
        """
        from src.modules.categories.handlers.handler_categories import buy_in_category

        fake_bot = replacement_fake_bot_fix
        user = await create_new_user(balance=50)
        category = await create_category(price=200, is_product_storage=True)
        _ = await create_product_account(category_id=category.category_id)

        cb = FakeCallbackQuery(data=f"buy_in_category:{category.category_id}:1:None",
                               chat_id=user.user_id, username=user.username)
        cb.message = SimpleNamespace(message_id=40)

        await buy_in_category(cb, user)

        expected_text = get_text(user.language, 'miscellaneous', "Insufficient funds: {amount}").format(amount=150)

        assert fake_bot.get_edited_message(user.user_id, cb.message.message_id, expected_text), \
            "Не отредактировалось сообщение о нехватке средств"

    @pytest.mark.asyncio
    async def test_buy_acc_successful_purchase(
            self,
            patch_fake_aiogram,
            replacement_fake_bot_fix,
            create_new_user,
            create_category,
            create_product_account,
            monkeypatch,
    ):
        """
        Успешная покупка: purchase_accounts возвращает True -> сообщение 'Thank you for your purchase...'
        """
        from src.modules.categories.services.buy_in_category import buy_product

        fake_bot = replacement_fake_bot_fix
        user = await create_new_user(balance=1000)
        category = await create_category(price=100, is_product_storage=True)
        _ = await create_product_account(category_id=category.category_id)

        async def fake_purchase_accounts(**kwargs):
            return True

        from src.modules.categories.services import buy_in_category
        monkeypatch.setattr(buy_in_category, "purchase_accounts", fake_purchase_accounts)

        cb = FakeCallbackQuery(data=f"buy_in_category:{category.category_id}:1:None",
                               chat_id=user.user_id, username=user.username)
        cb.message = SimpleNamespace(message_id=50)

        await buy_product(
            category_id=1,
            promo_code_id=None,
            quantity_products=1,
            callback=cb,
            user=user
        )

        assert fake_bot.check_str_in_edited_messages("Thank you for your purchase"), \
            "Не появилось сообщение об успешной покупке"


    @pytest.mark.asyncio
    async def test_buy_acc_purchase_failed_shows_no_enough_accounts_message(
            self,
            patch_fake_aiogram,
            replacement_fake_bot_fix,
            create_new_user,
            create_category,
            create_product_account,
            monkeypatch,
    ):
        """
        Если purchase_accounts возвращает False — должно отредактироваться сообщение с текстом
        'There are not enough accounts on the server...'
        """
        from src.modules.categories.services.buy_in_category import buy_product

        fake_bot = replacement_fake_bot_fix
        user = await create_new_user(balance=1000)
        category = await create_category(price=100, is_product_storage=True)
        _ = await create_product_account(category_id=category.category_id)

        async def fake_purchase_accounts(**kwargs):
            return False

        from src.modules.categories.services import buy_in_category
        monkeypatch.setattr(buy_in_category, "purchase_accounts", fake_purchase_accounts)

        cb = FakeCallbackQuery(data=f"buy_in_category:{category.category_id}:1:None",
                               chat_id=user.user_id, username=user.username)
        cb.message = SimpleNamespace(message_id=60)

        await buy_product(
            category_id=1,
            promo_code_id= None,
            quantity_products=1,
            callback=cb,
            user=user
        )

        assert fake_bot.check_str_in_edited_messages("There are not enough accounts on the server"), \
            "Не появилось сообщение о нехватке аккаунтов при result=False"



