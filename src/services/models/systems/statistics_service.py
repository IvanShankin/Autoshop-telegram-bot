from datetime import datetime, UTC, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.categories import (
    Categories,
    ProductAccounts,
    ProductType,
    ProductUniversal,
    Purchases,
)
from src.database.models.system import BackupLogs
from src.database.models.users import Replenishments, Users
from src.repository.database.systems import TypePaymentsRepository
from src.services._database.system.shemas.shemas import (
    ReplenishmentPaymentSystem,
    StatisticsData,
)


class StatisticsService:

    def __init__(
        self,
        type_payments_repo: TypePaymentsRepository,
        session_db: AsyncSession,
    ):
        self.type_payments_repo = type_payments_repo
        self.session_db = session_db

    async def get_statistics(self, interval_days: int) -> StatisticsData:
        up_to_date = datetime.now(UTC) - timedelta(days=interval_days)

        result = await self.session_db.execute(
            select(
                func.count().filter(Users.last_used >= up_to_date).label("active"),
                func.count().filter(Users.created_at >= up_to_date).label("new"),
                func.count().label("total"),
            )
        )

        row = result.one()
        active_users = row.active
        new_users = row.new
        total_users = row.total

        result = await self.session_db.execute(
            select(
                Purchases.product_type,
                func.count().label("quantity"),
                func.coalesce(func.sum(Purchases.purchase_price), 0).label("amount"),
                func.coalesce(func.sum(Purchases.net_profit), 0).label("profit"),
            )
            .where(Purchases.purchase_date >= up_to_date)
            .group_by(Purchases.product_type)
        )

        sales = {row.product_type: row for row in result.all()}

        acc = sales.get(ProductType.ACCOUNT)
        univ = sales.get(ProductType.UNIVERSAL)

        quantity_sale_accounts = acc.quantity if acc else 0
        amount_sale_accounts = acc.amount if acc else 0
        total_net_profit_account = acc.profit if acc else 0

        quantity_sale_universal = univ.quantity if univ else 0
        amount_sale_universal = univ.amount if univ else 0
        total_net_profit_universal = univ.profit if univ else 0

        result = await self.session_db.execute(
            select(
                Replenishments.type_payment_id,
                func.count(Replenishments.replenishment_id).label("quantity"),
                func.coalesce(func.sum(Replenishments.amount), 0).label("amount"),
            )
            .group_by(Replenishments.type_payment_id)
            .where(Replenishments.created_at >= up_to_date)
        )

        repl_stats = {r.type_payment_id: r for r in result.all()}

        all_type_payments = await self.type_payments_repo.get_all()

        quantity_replenishments = 0
        amount_replenishments = 0
        replenishment_payment_systems = []

        for tp in all_type_payments:
            stat = repl_stats.get(tp.type_payment_id)

            qty = stat.quantity if stat else 0
            amt = stat.amount if stat else 0

            replenishment_payment_systems.append(
                ReplenishmentPaymentSystem(
                    name=tp.name_for_user,
                    quantity_replenishments=qty,
                    amount_replenishments=amt,
                )
            )

            quantity_replenishments += qty
            amount_replenishments += amt

        result = await self.session_db.execute(
            select(func.coalesce(func.sum(Categories.price), 0))
            .select_from(ProductAccounts)
            .join(ProductAccounts.category)
        )
        funds_in_bot = result.scalar()

        result_db = await self.session_db.execute(
            select(func.count()).select_from(ProductAccounts)
        )
        accounts_for_sale = result_db.scalar()

        result_db = await self.session_db.execute(
            select(func.count()).select_from(ProductUniversal)
        )
        universals_for_sale = result_db.scalar()

        result_db = await self.session_db.execute(
            select(BackupLogs.created_at)
            .order_by(desc(BackupLogs.created_at))
            .limit(1)
        )
        last_backup = result_db.scalar_one_or_none()
        last_backup = last_backup if last_backup else "-"

        return StatisticsData(
            active_users=active_users,
            new_users=new_users,
            total_users=total_users,
            quantity_sale=quantity_sale_accounts + quantity_sale_universal,
            amount_sale=amount_sale_accounts + amount_sale_universal,
            total_net_profit=total_net_profit_account + total_net_profit_universal,
            quantity_sale_accounts=quantity_sale_accounts,
            amount_sale_accounts=amount_sale_accounts,
            total_net_profit_account=total_net_profit_account,
            quantity_sale_universal=quantity_sale_universal,
            amount_sale_universal=amount_sale_universal,
            total_net_profit_universal=total_net_profit_universal,
            quantity_replenishments=quantity_replenishments,
            amount_replenishments=amount_replenishments,
            replenishment_payment_systems=replenishment_payment_systems,
            funds_in_bot=funds_in_bot,
            accounts_for_sale=accounts_for_sale,
            universals_for_sale=universals_for_sale,
            last_backup=last_backup,
        )
