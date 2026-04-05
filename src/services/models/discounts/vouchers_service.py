from datetime import datetime, timezone
from typing import Tuple, Optional, List

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.event_models.discounts import NewActivationVoucher
from src.models.read_models import LogLevel
from src.config import Config
from src.database.models.discount import SmallVoucher
from src.exceptions import NotEnoughMoney
from src.models.create_models.discounts import CreateVoucherDTO
from src.models.read_models.other import UsersDTO, VouchersDTO
from src.repository.database.admins import AdminActionsRepository
from src.repository.database.discount import (
    VoucherActivationsRepository,
    VouchersRepository,
)
from src.repository.database.users import UserAuditLogsRepository, UsersRepository, WalletTransactionRepository
from src.repository.redis import UsersCacheRepository, VouchersCacheRepository
from src.services.events.publish_event_handler import PublishEventHandler
from src.utils.codes import generate_code
from src.utils.i18n import get_text


class VoucherService:

    def __init__(
        self,
        vouchers_repo: VouchersRepository,
        voucher_activations_repo: VoucherActivationsRepository,
        users_repo: UsersRepository,
        user_log_repo: UserAuditLogsRepository,
        wallet_transaction_repo: WalletTransactionRepository,
        admin_actions_repo: AdminActionsRepository,
        cache_vouchers_repo: VouchersCacheRepository,
        cache_users_repo: UsersCacheRepository,
        publish_event_handler: PublishEventHandler,
        conf: Config,
        session_db: AsyncSession,
    ):
        self.vouchers_repo = vouchers_repo
        self.voucher_activations_repo = voucher_activations_repo
        self.users_repo = users_repo
        self.user_log_repo = user_log_repo
        self.wallet_transaction_repo = wallet_transaction_repo
        self.admin_actions_repo = admin_actions_repo
        self.cache_vouchers_repo = cache_vouchers_repo
        self.cache_users_repo = cache_users_repo
        self.publish_event_handler = publish_event_handler
        self.conf = conf
        self.session_db = session_db

    async def create_voucher(
        self,
        user_id: int,
        data: CreateVoucherDTO,
    ) -> VouchersDTO:
        """
        Создаёт ваучер. У пользователя должно быть достаточно денег
        :param user_id: id пользователя
        :exception NotEnoughMoney: если у пользователя недостаточно денег
        """
        async with self.session_db.begin():
            user_db = await self.users_repo.get_by_id_for_update(user_id)
            if not user_db:
                raise ValueError("Пользователь не найден")

            required_amount = data.amount * data.number_of_activations if data.number_of_activations else 0

            if user_db.balance < required_amount and data.is_created_admin is False:
                raise NotEnoughMoney(
                    "У пользователя недостаточно денег",
                    required_amount - user_db.balance
                )

            while True:
                code = generate_code(15)
                cached = await self.cache_vouchers_repo.get_by_code(code)
                if cached:
                    continue

                exists = await self.vouchers_repo.get_by_code(code, only_valid=True)
                if not exists:
                    break

            if not data.is_created_admin:
                new_balance = user_db.balance - required_amount
                await self.users_repo.update(user_id=user_db.user_id, balance=new_balance)
                user_db.balance = new_balance

            new_voucher = await self.vouchers_repo.create_voucher(
                creator_id=user_id,
                is_created_admin=data.is_created_admin,
                activation_code=code,
                amount=data.amount,
                number_of_activations=data.number_of_activations,
                expire_at=data.expire_at,
            )

            if data.is_created_admin:
                await self.admin_actions_repo.add_admin_action(
                    user_id=user_db.user_id,
                    action_type="create_voucher",
                    message="Админ создал ваучер",
                    details={"voucher_id": new_voucher.voucher_id},
                )
            else:
                await self.user_log_repo.create_log(
                    user_id=user_db.user_id,
                    action_type="create_voucher",
                    message="Пользователь создал ваучер",
                    details={"voucher_id": new_voucher.voucher_id},
                )
                await self.wallet_transaction_repo.create_transaction(
                    user_id=user_db.user_id,
                    type="voucher",
                    amount=required_amount * -1,
                    balance_before=user_db.balance + required_amount,
                    balance_after=user_db.balance,
                )

        if data.is_created_admin:
            await self.publish_event_handler.send_log(
                text=(
                    f"🛠️\n"
                    f"#Админ_создал_ваучер \n\n"
                    f"Сумма: {data.amount} \n"
                    f"Число активаций: {data.number_of_activations} \n"
                    f"Годен до: {data.expire_at}"
                ),
                log_lvl=LogLevel.INFO,
            )

        ttl = None
        if data.expire_at:
            ttl = int((data.expire_at - datetime.now(timezone.utc)).total_seconds())

        await self.cache_vouchers_repo.set_by_code(new_voucher, ttl=ttl)

        if not data.is_created_admin:
            vouchers = await self.vouchers_repo.get_valid_by_page(user_id=user_db.user_id)
            small_list = [
                SmallVoucher(
                    voucher_id=v.voucher_id,
                    creator_id=v.creator_id,
                    amount=v.amount,
                    activation_code=v.activation_code,
                    activated_counter=v.activated_counter,
                    number_of_activations=v.number_of_activations,
                    is_valid=v.is_valid,
                )
                for v in vouchers
            ]
            await self.cache_vouchers_repo.set_small_by_user(
                user_id=user_db.user_id,
                vouchers=small_list,
                ttl=int(self.conf.redis_time_storage.all_voucher.total_seconds()),
            )

            await self.cache_users_repo.set(
                UsersDTO.model_validate(user_db),
                ttl=int(self.conf.redis_time_storage.user.total_seconds()),
            )

        return new_voucher

    async def get_valid_voucher_by_page(
        self,
        user_id: Optional[int] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        only_created_admin: bool = False,
    ) -> List[SmallVoucher]:
        """
        :param user_id: необходим если получаем по пользователю, а не по админам
        Если не указывать page, то вернётся весь список. Отсортирован по дате (desc)
        """
        if page_size is None:
            page_size = self.conf.different.page_size
        if not only_created_admin and user_id is not None:
            if await self.cache_vouchers_repo.exists_by_user(user_id):
                vouchers = await self.cache_vouchers_repo.get_small_by_user(user_id)
                if page:
                    start = (page - 1) * page_size
                    end = start + page_size
                    return vouchers[start:end]
                return vouchers

        items = await self.vouchers_repo.get_valid_by_page(
            user_id=user_id,
            page=page,
            page_size=page_size,
            only_created_admin=only_created_admin,
        )
        return [
            SmallVoucher(
                voucher_id=v.voucher_id,
                creator_id=v.creator_id,
                amount=v.amount,
                activation_code=v.activation_code,
                activated_counter=v.activated_counter,
                number_of_activations=v.number_of_activations,
                is_valid=v.is_valid,
            )
            for v in items
        ]

    async def get_count_voucher(
        self,
        user_id: Optional[int] = None,
        by_admins: bool = False,
    ) -> int:
        if user_id is not None and await self.cache_vouchers_repo.exists_by_user(user_id):
            return len(await self.cache_vouchers_repo.get_small_by_user(user_id))

        return await self.vouchers_repo.count(user_id=user_id, by_admins=by_admins)

    async def get_valid_voucher_by_code(self, code: str) -> Optional[VouchersDTO]:
        cached = await self.cache_vouchers_repo.get_by_code(code)
        if cached:
            return cached

        return await self.vouchers_repo.get_by_code(code, only_valid=True)

    async def get_voucher_by_id(
        self,
        voucher_id: int,
        check_on_valid: bool = True,
    ) -> Optional[VouchersDTO]:
        """Если есть флаг check_on_valid, то при запросе к БД будет доп проверка на валидность и вернёт только валидный"""
        return await self.vouchers_repo.get_by_id(
            voucher_id,
            check_on_valid=check_on_valid,
        )

    async def deactivate_voucher(self, voucher_id: int) -> int:
        """
        Сделает ваучер невалидным в БД (is_valid = False), вернёт деньги пользователю и удалит ваучер с redis.
        Сообщение пользователю НЕ будет отправлено!
        :return Возвращённая сумма пользователю
        :except Exception вызовет ошибку если произойдёт
        """
        owner_id = None
        try:
            voucher = await self.vouchers_repo.deactivate(voucher_id)
            await self.session_db.commit()

            if not voucher:
                return 0

            owner_id = voucher.creator_id

            if voucher.activation_code:
                await self.cache_vouchers_repo.delete_by_code(voucher.activation_code)

            if voucher.is_created_admin:
                await self.publish_event_handler.send_log(
                    text=f"#Деактивация_ваучера_созданным_админом \n\nID: {voucher.voucher_id}",
                    log_lvl=LogLevel.INFO,
                )
                return 0

            remaining = (voucher.number_of_activations or 0) - voucher.activated_counter
            refund_amount = remaining * voucher.amount

            if refund_amount <= 0:
                return 0

            user_db = await self.users_repo.get_by_id_for_update(voucher.creator_id)
            if not user_db:
                return 0

            balance_before = user_db.balance
            new_balance = balance_before + refund_amount
            await self.users_repo.update(user_id=user_db.user_id, balance=new_balance)
            user_db.balance = new_balance

            new_wallet_transaction = await self.wallet_transaction_repo.create_transaction(
                user_id=user_db.user_id,
                type="refund",
                amount=refund_amount,
                balance_before=balance_before,
                balance_after=new_balance,
            )

            await self.user_log_repo.create_log(
                user_id=user_db.user_id,
                action_type="deactivate_voucher",
                message="Ваучер деактивировался",
                details={"voucher_id": voucher_id},
            )
            await self.user_log_repo.create_log(
                user_id=user_db.user_id,
                action_type="return_money_from_vouchers",
                message="Пользователю вернулись деньги за ваучер который деактивировался",
                details={
                    "amount": refund_amount,
                    "voucher_id": voucher_id,
                    "transaction_id": new_wallet_transaction.wallet_transaction_id,
                },
            )

            await self.session_db.commit()

            vouchers = await self.vouchers_repo.get_valid_by_page(user_id=user_db.user_id)
            small_list = [
                SmallVoucher(
                    voucher_id=v.voucher_id,
                    creator_id=v.creator_id,
                    amount=v.amount,
                    activation_code=v.activation_code,
                    activated_counter=v.activated_counter,
                    number_of_activations=v.number_of_activations,
                    is_valid=v.is_valid,
                )
                for v in vouchers
            ]
            await self.cache_vouchers_repo.set_small_by_user(
                user_id=user_db.user_id,
                vouchers=small_list,
                ttl=int(self.conf.redis_time_storage.all_voucher.total_seconds()),
            )
            await self.cache_users_repo.set(
                UsersDTO.model_validate(user_db),
                ttl=int(self.conf.redis_time_storage.user.total_seconds()),
            )

            return refund_amount
        except Exception as e:
            log_message = get_text(
                "ru",
                "discount",
                "log_error_refunding_money_from_voucher",
            ).format(voucher_id=voucher_id, owner_id=owner_id, error=str(e))

            await self.publish_event_handler.send_log(text=log_message, log_lvl=LogLevel.INFO)

            raise e

    async def activate_voucher(self, user: UsersDTO, code: str, language: str) -> Tuple[str, bool]:
        """
        Проверит наличие ваучера с таким кодом, если он действителен и пользователь его ещё не активировал, то ваучер активируется.
        Если user не является создателем ваучера, то он может его активировать.

        Отправит сообщение создателю ваучера, что он активирован

        :param user: Тот кто хочет активировать ваучер.
        :param code: Код ваучера.
        :param language: Язык на котором будет возвращено сообщение.
        :return Tuple[str, bool]: Сообщение с результатом, успешность активации
        """
        balance_before = user.balance

        voucher = await self.cache_vouchers_repo.get_by_code(code)
        if not voucher:
            voucher = await self.vouchers_repo.get_by_code(code, only_valid=True)

        if not voucher:
            return get_text(language, "discount", "voucher_not_found"), False

        if voucher.creator_id == user.user_id:
            return get_text(language, "discount", "cannot_activate_own_voucher"), False

        if voucher.expire_at and voucher.expire_at < datetime.now(timezone.utc):
            await self.deactivate_voucher(voucher.voucher_id)
            return get_text(
                language,
                "discount",
                "voucher_expired_due_to_time",
            ).format(id=voucher.voucher_id, code=voucher.activation_code), False

        updated_user = None
        async with self.session_db.begin():
            activation = await self.voucher_activations_repo.get_by_voucher_and_user(
                voucher_id=voucher.voucher_id,
                user_id=user.user_id,
                for_update=True,
            )
            if activation:
                return get_text(language, "discount", "voucher_already_activated"), False

            user_db = await self.users_repo.get_by_id_for_update(user.user_id)
            if not user_db:
                return get_text(language, "discount", "voucher_not_found"), False

            new_balance = user_db.balance + voucher.amount
            updated_user = await self.users_repo.update(user_id=user_db.user_id, balance=new_balance)
            await self.voucher_activations_repo.create_activation(
                voucher_id=voucher.voucher_id,
                user_id=user.user_id,
            )

        await self.cache_users_repo.set(
            updated_user,
            ttl=int(self.conf.redis_time_storage.user.total_seconds()),
        )

        await self.publish_event_handler.voucher_activated(
            NewActivationVoucher(
                user_id=user.user_id,
                language=user.language,
                voucher_id=voucher.voucher_id,
                amount=voucher.amount,
                balance_before=balance_before,
                balance_after=updated_user.balance,
            )
        )

        return get_text(
            language, "discount", "voucher_successfully_activated"
        ).format(amount=voucher.amount, new_balance=updated_user.balance), True
