from src.application._secrets.crypto_context import get_crypto_context
from src.domain.crypto.decrypt import decrypt_text
from src.domain.crypto.key_ops import unwrap_dek
from src.infrastructure.files.file_system import make_csv_bytes
from src.models.read_models import EventSentLog, LogLevel
from src.infrastructure.rabbit_mq.producer import publish_event
from src.exceptions.business import ServerError
from src.application.products.accounts.other.dto.schemas import REQUIRED_HEADERS
from src.application.products.accounts.utils._helper_upload import get_account_storage_by_category_id
from src.utils.core_logger import get_logger
from src.utils.pars_number import e164_to_pretty


async def upload_other_account(category_id: int) -> bytes:
    """
    :except ServerError: Любая ошибка необрабатываемая
    """
    accounts = await get_account_storage_by_category_id(category_id)

    ready_acc = []
    crypto = get_crypto_context()

    try:
        for acc in accounts:
            account_key = unwrap_dek(
                acc.account_storage.encrypted_key,
                acc.account_storage.encrypted_key_nonce,
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
    except Exception as e:
        message = f"Ошибка при выгрузке 'других' аккаунтов {str(e)}"
        get_logger(__name__).exception(message)
        event = EventSentLog(
            text=message,
            log_lvl=LogLevel.ERROR
        )
        await publish_event(event.model_dump(), "message.send_log")
        raise ServerError()
