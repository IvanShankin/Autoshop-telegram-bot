import pytest

from tests.helpers.helper_functions import comparison_models


class TestWalletTransactionService:

    @pytest.mark.asyncio
    async def test_get_wallet_transaction(
        self, session_db_fix, container_fix, replacement_fake_bot_fix, create_wallet_transaction
    ):
        record = await create_wallet_transaction()

        wallet_transaction = await container_fix.wallet_transaction_service.get_wallet_transaction(record.wallet_transaction_id)
        assert comparison_models(wallet_transaction, record)

    @pytest.mark.asyncio
    async def test_get_wallet_transaction_page(
        self, session_db_fix, container_fix, create_new_user, create_wallet_transaction
    ):

        user = await create_new_user()
        transaction_1 = await create_wallet_transaction(user.user_id, amount=100)
        transaction_2 = await create_wallet_transaction(user.user_id, amount=200)
        transaction_3 = await create_wallet_transaction(user.user_id, amount=300)

        transactions = await container_fix.wallet_transaction_service.get_wallet_transaction_page(
            user_id=user.user_id, page=1
        )

        assert comparison_models(transactions[0], transaction_3)
        assert comparison_models(transactions[1], transaction_2)
        assert comparison_models(transactions[2], transaction_1)