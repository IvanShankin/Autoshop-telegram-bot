from src.services.accounts.other.shemas import REQUIRED_HEADERS
from src.services.accounts.utils.helper_upload import get_account_storage_by_category_id
from src.services.filesystem.input_account import make_csv_bytes
from src.utils.pars_number import e164_to_pretty
from src.utils.secret_data import decrypt_data


async def upload_other_account(category_id: int) -> bytes:
    accounts = await get_account_storage_by_category_id(category_id)

    ready_acc = []
    for acc in accounts:
        ready_acc.append(
            {
                "phone": e164_to_pretty(acc.account_storage.phone_number),
                "login": decrypt_data(acc.account_storage.login_encrypted),
                "password": decrypt_data(acc.account_storage.password_encrypted),
            }
        )

    return make_csv_bytes(ready_acc, REQUIRED_HEADERS)
