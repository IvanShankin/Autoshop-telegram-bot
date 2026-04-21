from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.referrals import CreateReferralIncomeDTO
from src.models.create_models.users import CreateUserAuditLogDTO, CreateWalletTransactionDTO
from src.models.read_models import ReferralIncomeResult, ReferralReplenishmentCompleted, ReferralReportItemDTO, \
    ReferralIncomeItemDTO, ReferralReportDTO
from src.models.read_models.other import ReferralsDTO, UsersDTO
from src.repository.database.referrals import ReferralsRepository
from src.application.models.referrals.referral_income_service import ReferralIncomeService
from src.application.models.referrals.referral_lvls_service import ReferralLevelsService
from src.application.models.users.user_service import UserService
from src.application.models.users.user_log_service import UserLogService
from src.application.models.users.wallet_transaction import WalletTransactionService


class ReferralService:

    def __init__(
        self,
        referral_repo: ReferralsRepository,
        referral_income_service: ReferralIncomeService,
        referral_lvls_service: ReferralLevelsService,
        log_service: UserLogService,
        user_service: UserService,
        wallet_transaction_service: WalletTransactionService,
        session_db: AsyncSession,
    ):
        self.referral_repo = referral_repo
        self.referral_income_service = referral_income_service
        self.referral_lvls_service = referral_lvls_service
        self.log_service = log_service
        self.user_service = user_service
        self.wallet_transaction_service = wallet_transaction_service
        self.session_db = session_db

    async def get_all_referrals(self, user_id: int) -> Sequence[ReferralsDTO]:
        return await self.referral_repo.get_all_by_owner(user_id)

    async def get_referral(self, referral_id: int) -> Optional[ReferralsDTO]:
        return await self.referral_repo.get_by_referral_id(referral_id)

    async def add_referral(self, referral_id: int, owner_id: int) -> ReferralsDTO:
        ref_lvls = await self.referral_lvls_service.get_referral_levels()
        min_level = min(ref_lvls, key=lambda x: x.level)

        referral = await self.referral_repo.create_referral(
            referral_id=referral_id,
            owner_user_id=owner_id,
            level=min_level.level,
        )

        await self.log_service.create_log(
            user_id=owner_id,
            data=CreateUserAuditLogDTO(
                action_type="new_referral",
                message="У пользователя новый реферал",
                details={"referral_id": referral_id},
            ),
        )
        await self.log_service.create_log(
            user_id=referral_id,
            data=CreateUserAuditLogDTO(
                action_type="became_referral",
                message="Пользователь стал рефералом",
                details={"owner_id": owner_id},
            ),
        )
        await self.session_db.commit()

        return referral

    async def process_referral_replenishment(
        self,
        data: ReferralReplenishmentCompleted,
    ) -> Optional[ReferralIncomeResult]:
        """
        Обрабатывает пополнение от рефералла:
        - проверяет дубликаты по replenishment_id
        - обновляет уровень реферала
        - начисляет доход владельцу
        - создает запись дохода, транзакцию и лог
        """
        if data.amount <= 0:
            return None

        async with self.session_db.begin():
            existing_income = await self.referral_income_service.get_income_by_replenishment_id(
                data.replenishment_id
            )
            if existing_income:
                return None

            referral = await self.referral_repo.get_by_referral_id(data.user_id)
            if not referral:
                return None

            last_level = referral.level
            current_level = last_level
            percent_current_level = 0.0

            levels = await self.referral_lvls_service.get_referral_levels()
            selected_level = None

            if data.total_sum_replenishment is not None:
                for lvl in levels:
                    if data.total_sum_replenishment >= lvl.amount_of_achievement:
                        selected_level = lvl
            else:
                for lvl in levels:
                    if lvl.level == last_level:
                        selected_level = lvl
                        break

            if selected_level:
                current_level = selected_level.level
                percent_current_level = selected_level.percent

            income_amount = int(data.amount * percent_current_level / 100)
            if income_amount <= 0:
                return None

            owner = await self.user_service.get_user_for_update(referral.owner_user_id)
            if not owner:
                return None

            if current_level != last_level:
                await self.referral_repo.update_level(referral_id=data.user_id, level=current_level)

            balance_before = owner.balance
            owner.balance += income_amount
            owner.total_profit_from_referrals = (owner.total_profit_from_referrals or 0) + income_amount

            income = await self.referral_income_service.create_income(
                CreateReferralIncomeDTO(
                    replenishment_id=data.replenishment_id,
                    owner_user_id=owner.user_id,
                    referral_id=data.user_id,
                    amount=income_amount,
                    percentage_of_replenishment=int(percent_current_level),
                )
            )

            transaction = await self.wallet_transaction_service.create_wallet_transaction(
                user_id=owner.user_id,
                data=CreateWalletTransactionDTO(
                    type="referral",
                    amount=income_amount,
                    balance_before=balance_before,
                    balance_after=owner.balance,
                ),
            )

            await self.log_service.create_log(
                user_id=owner.user_id,
                data=CreateUserAuditLogDTO(
                    action_type="profit_from_referral",
                    message="Пользователь получил средства за пополнение от своего реферала",
                    details={
                        "income_from_referral_id": income.income_from_referral_id,
                        "wallet_transaction_id": transaction.wallet_transaction_id,
                    },
                ),
            )


        await self.user_service.cache_user_repo.set(
            user=UsersDTO.model_validate(owner),
            ttl=int(self.user_service.conf.redis_time_storage.user.total_seconds()),
        )

        return ReferralIncomeResult(
            owner_user_id=owner.user_id,
            owner_language=owner.language,
            referral_id=data.user_id,
            replenishment_id=data.replenishment_id,
            replenishment_amount=data.amount,
            income_amount=income_amount,
            last_level=last_level,
            current_level=current_level,
            percent=percent_current_level,
        )

    async def build_report_data(self, owner_user_id: int) -> ReferralReportDTO:
        referrals = await self.referral_repo.get_all_by_owner(owner_user_id)
        incomes = await self.referral_income_service.get_referral_income_page(owner_user_id)

        users_map = {
            user.user_id: user
            for user in await self.user_service.get_user_by_ids([r.referral_id for r in referrals])
        }

        referral_items = []

        for referral in referrals:
            user = users_map.get(referral.referral_id)

            total_income = sum(
                i.amount for i in incomes if i.referral_id == referral.referral_id
            )

            referral_items.append(
                ReferralReportItemDTO(
                    referral_id=referral.referral_id,
                    username=user.username if user else None,
                    level=referral.level,
                    join_date=referral.created_at,
                    total_income=total_income
                )
            )

        income_items = [
            ReferralIncomeItemDTO(
                deposit_id=i.income_from_referral_id,
                referral_id=i.referral_id,
                amount=i.amount,
                percentage=i.percentage_of_replenishment,
                created_at=i.created_at
            )
            for i in incomes
        ]

        return ReferralReportDTO(
            referrals=referral_items,
            incomes=income_items
        )