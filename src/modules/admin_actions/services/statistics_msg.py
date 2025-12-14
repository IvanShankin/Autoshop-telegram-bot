from src.services.database.system.actions.actions import get_statistics
from src.utils.i18n import get_text


async def get_statistics_message(interval_days: int, language: str) -> str:
    statistics = await get_statistics(interval_days)

    interval_msg = get_text(
        language,
        "admins_statistics",
        str(interval_days) if interval_days < 366 else "all time"
    )


    payment_systems_text = []
    for ps in statistics.replenishment_payment_systems:
        payment_systems_text.append(
            get_text(
                language,
                "admins_statistics",
                "Payment system: {name}\n"
                "Quantity replenishments: {quantity_replenishments}\n"
                "Amount replenishments: {amount_replenishments}\n"
            ).format(
                name=ps.name,
                quantity_replenishments=ps.quantity_replenishments,
                amount_replenishments=ps.amount_replenishments,
            )
        )

    payment_systems_block = "\n".join(payment_systems_text) if payment_systems_text else "-"

    return get_text(
        language,
        "admins_statistics",
        "Statistics {interval}\n\n"
        "\n"
        "Active users: {active_users}\n"
        "New users: {new_users}\n"
        "Total users: {total_users}\n"
        "\n"
        "Quantity sale accounts: {quantity_sale_accounts}\n"
        "Amount sale accounts: {amount_sale_accounts}\n"
        "Total net profit: {total_net_profit}\n"
        "\n"
        "Quantity replenishments: {quantity_replenishments}\n"
        "Amount replenishments: {amount_replenishments}\n"
        "\n"
        "Replenishment payment systems:\n"
        "{replenishment_payment_systems}\n"
        "\n"
        "Funds in bot: {funds_in_bot}\n"
        "Accounts for sale: {accounts_for_sale}\n"
        "\n"
        "Last backup: {last_backup}\n"
    ).format(
        interval=interval_msg,
        active_users=statistics.active_users,
        new_users=statistics.new_users,
        total_users=statistics.total_users,
        quantity_sale_accounts=statistics.quantity_sale_accounts,
        amount_sale_accounts=statistics.amount_sale_accounts,
        total_net_profit=statistics.total_net_profit,
        quantity_replenishments=statistics.quantity_replenishments,
        amount_replenishments=statistics.amount_replenishments,
        replenishment_payment_systems=payment_systems_block,
        funds_in_bot=statistics.funds_in_bot,
        accounts_for_sale=statistics.accounts_for_sale,
        last_backup=statistics.last_backup,
    )
