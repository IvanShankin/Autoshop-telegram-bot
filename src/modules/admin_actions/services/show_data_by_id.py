from src.bot_actions.messages import send_message
from src.config import get_config
from src.modules.admin_actions.keyboards.show_data_kb import back_in_show_data_by_id_kb
from src.modules.admin_actions.state.show_data_by_id import ShowDataById
from src.services.database.discounts.actions import get_voucher_by_id, get_promo_code
from src.services.database.discounts.actions.actions_promo import get_activated_promo_code
from src.services.database.discounts.actions.actions_vouchers import get_activate_voucher
from src.services.database.referrals.actions.actions_ref import get_referral, get_income_from_referral
from src.services.database.categories.actions import get_purchases, get_sold_accounts_by_account_id
from src.services.database.users.actions import get_replenishment
from src.services.database.users.actions.action_other_with_user import get_transfer_money, get_wallet_transaction
from src.services.database.users.models import Users
from src.utils.converter import safe_int_conversion
from src.utils.i18n import get_text
from src.services.secrets import decrypt_text, get_crypto_context, unwrap_dek


async def show_data_by_id_handler(state: str, message_text: str, user: Users, current_page: int):
    entered_id = safe_int_conversion(message_text, positive=False)
    message = None

    if not entered_id:
        await send_message(
            chat_id=user.user_id,
            message=get_text(user.language, "miscellaneous", "incorrect_value_entered"),
            reply_markup=back_in_show_data_by_id_kb(language=user.language, current_page=current_page)
        )
        return

    if state == ShowDataById.replenishment_by_id.state:
        message = await get_message_replenishment(entered_id, user.language)
    elif state == ShowDataById.sold_account_by_id.state:
        message = await get_message_sold_account_full(entered_id, user.language)
    elif state == ShowDataById.purchase_account_by_id.state:
        message = await get_message_purchase_account(entered_id, user.language)
    elif state == ShowDataById.transfer_money_by_id.state:
        message = await get_message_transfer_money(entered_id, user.language)
    elif state == ShowDataById.voucher_by_id.state:
        message = await get_message_voucher(entered_id, user.language)
    elif state == ShowDataById.activate_voucher_by_id.state:
        message = await get_message_activate_voucher(entered_id, user.language)
    elif state == ShowDataById.promo_code_by_id.state:
        message = await get_message_promo_code(entered_id, user.language)
    elif state == ShowDataById.promo_code_activation_by_id.state:
        message = await get_message_activated_promo_code(entered_id, user.language)
    elif state == ShowDataById.referral_by_id.state:
        message = await get_message_referral(entered_id, user.language)
    elif state == ShowDataById.income_from_ref_by_id.state:
        message = await get_message_income_from_referral(entered_id, user.language)
    elif state == ShowDataById.wallet_transaction_by_id.state:
        message = await get_message_wallet_transaction(entered_id, user.language)


    if not message:
        message = get_text(user.language, "admins_show_data_by_id", "no_data_found_for_this_id")

    await send_message(
        chat_id=user.user_id,
        message=message,
        reply_markup=back_in_show_data_by_id_kb(language=user.language, current_page=current_page)
    )


async def get_message_replenishment(replenishment_id: int, language: str) -> str | None:
    replenishment = await get_replenishment(replenishment_id)

    if not replenishment:
        return None

    return get_text(
        language,
        "admins_show_data_by_id",
        "replenishment_details"
    ).format(
        replenishment_id=replenishment.replenishment_id,
        user_id=replenishment.user_id,
        type_payment_id=replenishment.type_payment_id,
        origin_amount=replenishment.origin_amount,
        amount=replenishment.amount,
        status=get_text(language, "status_replenishments", replenishment.status),
        created_at=replenishment.created_at.strftime(get_config().different.dt_format),
        payment_system_id=replenishment.payment_system_id,
        invoice_url=replenishment.invoice_url,
        expire_at=replenishment.expire_at.strftime(get_config().different.dt_format)
    )


async def get_message_purchase_account(purchase_id: int, language: str) -> str | None:
    purchase_account = await get_purchases(purchase_id)

    if not purchase_account:
        return None

    return get_text(
        language,
        "admins_show_data_by_id",
        "account_purchase_details"
    ).format(
        purchase_id=purchase_account.purchase_id,
        user_id=purchase_account.user_id,
        account_storage_id=purchase_account.account_storage_id,
        original_price=purchase_account.original_price,
        purchase_price=purchase_account.purchase_price,
        cost_price=purchase_account.cost_price,
        net_profit=purchase_account.net_profit,
        purchase_date=purchase_account.purchase_date.strftime(get_config().different.dt_format)
    )

async def get_message_transfer_money(transfer_money_id: int, language: str) -> str | None:
    transfer_money = await get_transfer_money(transfer_money_id)

    if not transfer_money:
        return None

    return get_text(
        language,
        "admins_show_data_by_id",
        "money_transfer_details"
    ).format(
        transfer_money_id=transfer_money.transfer_money_id,
        user_from_id=transfer_money.user_from_id,
        user_where_id=transfer_money.user_where_id,
        amount=transfer_money.amount,
        created_at=transfer_money.created_at.strftime(get_config().different.dt_format),
    )


async def get_message_voucher(voucher_id: int, language: str) -> str | None:
    voucher = await get_voucher_by_id(voucher_id)

    if not voucher:
        return None

    return get_text(
        language,
        "admins_show_data_by_id",
        "voucher_details"
    ).format(
        voucher_id=voucher.voucher_id,
        creator_id=voucher.creator_id,
        is_created_admin=voucher.is_created_admin,
        activation_code=voucher.activation_code,
        amount=voucher.amount,
        activated_counter=voucher.activated_counter,
        number_of_activations=voucher.number_of_activations,
        start_at=voucher.start_at.strftime(get_config().different.dt_format),
        expire_at=(
            voucher.expire_at.strftime(get_config().different.dt_format)
            if voucher.expire_at else
            get_text(language,"admins_show_data_by_id", "endlessly")
        ),
        is_valid=voucher.is_valid,
    )


async def get_message_activate_voucher(activate_voucher_id: int, language: str) -> str | None:
    activate_voucher = await get_activate_voucher(activate_voucher_id)

    if not activate_voucher:
        return None

    return get_text(
        language,
        "admins_show_data_by_id",
        "voucher_activation_details"
    ).format(
        voucher_activation_id=activate_voucher.voucher_activation_id,
        voucher_id=activate_voucher.voucher_id,
        user_id=activate_voucher.user_id,
        created_at=activate_voucher.created_at.strftime(get_config().different.dt_format),
    )


async def get_message_promo_code(promo_code_id: int, language: str) -> str | None:
    promo = await get_promo_code(promo_code_id = promo_code_id, get_only_valid=False)

    if not promo:
        return None

    return get_text(
        language,
        "admins_show_data_by_id",
        "promo_code_details"
    ).format(
        promo_code_id=promo.promo_code_id,
        activation_code=promo.activation_code,
        min_order_amount=promo.min_order_amount,
        activated_counter=promo.activated_counter,
        amount=promo.amount if promo.amount is not None else get_text(language,"admins_show_data_by_id","no"),
        discount_percentage=(
            promo.discount_percentage
            if promo.discount_percentage is not None else
            get_text(language,"admins_show_data_by_id","no")
        ),
        number_of_activations=promo.number_of_activations,
        start_at=promo.start_at.strftime(get_config().different.dt_format),
        expire_at=(
            promo.expire_at.strftime(get_config().different.dt_format)
            if promo.expire_at else
            get_text(language, "admins_show_data_by_id", "endlessly")
        ),
        is_valid=promo.is_valid,
    )


async def get_message_activated_promo_code(activated_promo_code_id: int, language: str) -> str | None:
    activated_promo_code = await get_activated_promo_code(
        activated_promo_code_id
    )

    if not activated_promo_code:
        return None

    return get_text(
        language,
        "admins_show_data_by_id",
        "promo_code_activation_details"
    ).format(
        activated_promo_code_id=activated_promo_code.activated_promo_code_id,
        promo_code_id=activated_promo_code.promo_code_id,
        user_id=activated_promo_code.user_id,
        created_at=activated_promo_code.created_at.strftime(get_config().different.dt_format),
    )


async def get_message_referral(referral_id: int, language: str) -> str | None:
    referral = await get_referral(referral_id)

    if not referral:
        return None

    return get_text(
        language,
        "admins_show_data_by_id",
        "referral_details"
    ).format(
        referral_id=referral.referral_id,
        owner_user_id=referral.owner_user_id,
        level=referral.level,
        created_at=referral.created_at.strftime(get_config().different.dt_format),
    )


async def get_message_income_from_referral(
    income_from_referral_id: int,
    language: str
) -> str | None:
    income = await get_income_from_referral(income_from_referral_id)

    if not income:
        return None

    return get_text(
        language,
        "admins_show_data_by_id",
        "referral_income_details"
    ).format(
        income_from_referral_id=income.income_from_referral_id,
        replenishment_id=income.replenishment_id,
        owner_user_id=income.owner_user_id,
        referral_id=income.referral_id,
        amount=income.amount,
        percentage_of_replenishment=income.percentage_of_replenishment,
        created_at=income.created_at.strftime(get_config().different.dt_format),
    )


async def get_message_wallet_transaction(
    wallet_transaction_id: int,
    language: str
) -> str | None:
    tx = await get_wallet_transaction(wallet_transaction_id)

    if not tx:
        return None

    return get_text(
        language,
        "admins_show_data_by_id",
        "wallet_transaction_details"
    ).format(
        wallet_transaction_id=tx.wallet_transaction_id,
        user_id=tx.user_id,
        type=get_text(language, "type_wallet_transaction", tx.type),
        amount=tx.amount,
        balance_before=tx.balance_before,
        balance_after=tx.balance_after,
        created_at=tx.created_at.strftime(get_config().different.dt_format),
    )


async def get_message_sold_account_full(
    sold_account_id: int,
    language: str,
) -> str:
    sold_account_full = await get_sold_accounts_by_account_id(sold_account_id, language = language)

    storage = sold_account_full.account_storage

    crypto = get_crypto_context()
    account_key = unwrap_dek(
        storage.encrypted_key,
        crypto.nonce_b64_dek,
        crypto.kek,
    )

    if storage.login_encrypted:
        login = decrypt_text(storage.login_encrypted, storage.login_nonce, account_key)
    else:
        login = get_text(language,"admins_show_data_by_id","no")

    if storage.password_encrypted:
        password = decrypt_text(storage.password_encrypted, storage.password_nonce, account_key)
    else:
        password = get_text(language,"admins_show_data_by_id","no")
    
    return get_text(
        language,
        "admins_show_data_by_id",
        "sold_account_details"
    ).format(
        sold_account_id=sold_account_full.sold_account_id,
        owner_id=sold_account_full.owner_id,
        type_account_service=storage.type_account_service,
        name=sold_account_full.name,
        description=sold_account_full.description,
        sold_at=sold_account_full.sold_at.strftime(get_config().different.dt_format),

        account_storage_id=storage.account_storage_id,
        storage_uuid=storage.storage_uuid,
        checksum=storage.checksum,
        status=storage.status,
        key_version=storage.key_version,
        encryption_algo=storage.encryption_algo,
        phone_number=storage.phone_number,
        login_encrypted=login,
        password_encrypted=password,
        is_active=storage.is_active,
        is_valid=storage.is_valid,
        added_at=storage.added_at.strftime(get_config().different.dt_format),
        last_check_at=(
            storage.last_check_at.strftime(get_config().different.dt_format)
            if storage.last_check_at else
            get_text(language,"admins_show_data_by_id","no")
        ),
    )

