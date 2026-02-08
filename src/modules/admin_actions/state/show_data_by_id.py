from aiogram.fsm.state import State, StatesGroup


class ShowDataById(StatesGroup):
    replenishment_by_id = State()
    sold_account_by_id = State()
    purchase_by_id = State()
    sold_universal_product_by_id = State()
    transfer_money_by_id = State()
    voucher_by_id = State()
    activate_voucher_by_id = State()
    promo_code_by_id = State()
    promo_code_activation_by_id = State()
    referral_by_id = State()
    income_from_ref_by_id = State()
    wallet_transaction_by_id = State()