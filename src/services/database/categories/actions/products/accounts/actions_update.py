from datetime import datetime
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from src.services.database.categories.models import AccountStorage, TgAccountMedia
from src.services.database.core.database import get_db
from src.services.redis.filling import filling_product_account_by_account_id, \
    filling_sold_account_by_account_id, filling_sold_accounts_by_owner_id


async def update_account_storage(
    account_storage_id: int = None,
    storage_uuid: str = None,
    file_path: str = None,
    checksum: str = None,
    status: Literal["for_sale", "bought", "deleted"] = None,
    encrypted_key: str = None,
    encrypted_key_nonce: str = None,
    key_version: int = None,
    encryption_algo: str = None,
    login_encrypted: str = None,
    password_encrypted: str = None,
    last_check_at: datetime = None,
    is_valid: bool = None,
    is_active: bool = None,
) -> AccountStorage:
    async with get_db() as session:
        result = await session.execute(
            select(AccountStorage)
            .options(
                selectinload(AccountStorage.product_account),
                selectinload(AccountStorage.sold_account),
                selectinload(AccountStorage.deleted_account)
            )
            .where(AccountStorage.account_storage_id == account_storage_id)
        )
        account: AccountStorage = result.scalar_one_or_none()

        update_data = {}
        if storage_uuid is not None:
            update_data['storage_uuid'] = storage_uuid
        if file_path is not None:
            update_data['file_path'] = file_path
        if checksum is not None:
            update_data['checksum'] = checksum
        if status is not None:
            update_data['status'] = status
        if encrypted_key is not None:
            update_data['encrypted_key'] = encrypted_key
        if encrypted_key_nonce is not None:
            update_data['encrypted_key_nonce'] = encrypted_key_nonce
        if key_version is not None:
            update_data['key_version'] = key_version
        if encryption_algo is not None:
            update_data['encryption_algo'] = encryption_algo
        if login_encrypted is not None:
            update_data['login_encrypted'] = login_encrypted
        if password_encrypted is not None:
            update_data['password_encrypted'] = password_encrypted
        if last_check_at is not None:
            update_data['last_check_at'] = last_check_at
        if is_valid is not None:
            update_data['is_valid'] = is_valid
        if is_active is not None:
            update_data['is_active'] = is_active

        if update_data:
            await session.execute(
                update(AccountStorage)
                .where(AccountStorage.account_storage_id == account_storage_id)
                .values(**update_data)
            )
            await session.commit()

            # обновляем объект в памяти (чтобы вернуть актуальные данные)
            for key, value in update_data.items():
                setattr(account, key, value)

        # один AccountStorage - одна запись в другой таблице, но будем заполнять везде где есть
        if account.product_account:
            await filling_product_account_by_account_id(account.product_account.account_id)
        if account.sold_account:
            await filling_sold_account_by_account_id(account.sold_account.sold_account_id)
            await filling_sold_accounts_by_owner_id(account.sold_account.owner_id)

        return account


async def update_tg_account_media(
        tg_account_media_id: int,
        tdata_tg_id: str = None,
        session_tg_id: str = None
) -> TgAccountMedia | None:
    async with get_db() as session:
        update_data = {}
        if tdata_tg_id is not None:
            update_data['tdata_tg_id'] = tdata_tg_id
        if session_tg_id is not None:
            update_data['session_tg_id'] = session_tg_id

        if update_data:
            result = await session.execute(
                update(TgAccountMedia)
                .where(TgAccountMedia.tg_account_media_id == tg_account_media_id)
                .values(**update_data)
                .returning(TgAccountMedia)
            )
            tg_account_media = result.scalar_one_or_none()
            await session.commit()
            return tg_account_media
