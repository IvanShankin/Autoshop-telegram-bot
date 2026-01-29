from src.services.products.accounts.other.shemas import REQUIRED_HEADERS
from src.services.products.accounts.utils.helper_upload import get_account_storage_by_category_id
from src.services.filesystem.account_products import make_csv_bytes
from src.utils.pars_number import e164_to_pretty
from src.services.secrets import decrypt_text, unwrap_dek, get_crypto_context


async def upload_other_account(category_id: int) -> bytes:
    accounts = await get_account_storage_by_category_id(category_id)

    ready_acc = []
    crypto = get_crypto_context()

    for acc in accounts:
        account_key = unwrap_dek(
            acc.account_storage.encrypted_key,
            crypto.nonce_b64_dek,
            crypto.kek
        )

        ready_acc.append(
            {
                "phone": e164_to_pretty(acc.account_storage.phone_number),
                "login": decrypt_text(acc.account_storage.login_encrypted, acc.account_storage.login_nonce, account_key),
                "password": decrypt_text(acc.account_storage.password_encrypted, acc.account_storage.password_nonce, account_key),
            }
        )

    return make_csv_bytes(ready_acc, REQUIRED_HEADERS)
