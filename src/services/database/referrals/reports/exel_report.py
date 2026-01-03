import io
from datetime import datetime
import pandas as pd

from src.config import get_config
from src.services.database.referrals.actions import get_all_referrals, get_referral_income_page
from src.services.database.users.actions import get_user
from src.utils.i18n import get_text


def _strip_tz(value: datetime) -> str:
    """Убирает timezone из datetime, если есть и преобразует в строку"""
    if isinstance(value, datetime) and value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    return value.strftime(get_config().different.dt_format)


async def generate_referral_report_excel(owner_user_id: int, language: str) -> bytes:
    """
    Формирует Excel-отчёт в ОЗУ и возвращает байты файла.
    """

    # Получаем данные
    referrals_orm = await get_all_referrals(owner_user_id)
    incomes_orm = await get_referral_income_page(owner_user_id)

    # Подготовка списка рефералов
    referrals: list[dict] = []
    for referral in referrals_orm:
        referral_user = await get_user(referral.referral_id)
        new_dict = {}
        new_dict[get_text(language, 'referral_report', 'Referral ID')] = referral.referral_id
        new_dict[get_text(language, 'referral_report', 'Referral username')] = referral_user.username
        new_dict[get_text(language, 'referral_report', 'Level')] = referral.level
        new_dict[get_text(language, 'referral_report', 'Join date')] = _strip_tz(referral.created_at)

        total_income = 0
        for income in incomes_orm:
            if income.referral_id == referral.referral_id:
                total_income += income.amount

        new_dict[get_text(language, 'referral_report', 'Total brought')] = total_income
        referrals.append(new_dict)

    # Подготовка списка доходов
    incomes: list[dict] = []
    for income in incomes_orm:
        new_dict = {}
        new_dict[get_text(language, 'referral_report', 'Deposit ID')] = income.income_from_referral_id
        new_dict[get_text(language, 'referral_report', 'Referral ID')] = income.referral_id
        new_dict[get_text(language, 'referral_report', 'Amount')] = income.amount
        new_dict[get_text(language, 'referral_report', 'Referral deposit percentage')] = income.percentage_of_replenishment
        new_dict[get_text(language, 'referral_report', 'Deposit date')] = _strip_tz(income.created_at)

        incomes.append(new_dict)

    # Считаем статистику
    total_referrals = len(referrals)
    total_income = sum(income.amount or 0 for income in incomes_orm)
    level1 = len([r for r in referrals_orm if r.level == 1])
    level2 = len([r for r in referrals_orm if r.level == 2])

    # Формируем excel
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        # блок 1 - служебная информация
        info_df = pd.DataFrame([
            [get_text(language, 'referral_report', 'Export date'), datetime.now().strftime(get_config().different.dt_format)],
            [get_text(language, 'referral_report', 'Owner ID'), owner_user_id],
            [get_text(language, 'referral_report', 'Total referrals'), total_referrals],
            [get_text(language, 'referral_report', 'Total income'), total_income],
        ], columns=[get_text(language, 'referral_report', 'Parameter'), get_text(language, 'referral_report', 'Parameter')])
        info_df.to_excel(writer, index=False, sheet_name="referrals_report", startrow=0)

        startrow = len(info_df) + 2

        # блок 2 - список рефералов
        pd.DataFrame(referrals, columns=[
            get_text(language, 'referral_report', 'Referral ID'),
            get_text(language, 'referral_report', 'Referral username'),
            get_text(language, 'referral_report', 'Level'),
            get_text(language, 'referral_report', 'Join date'),
            get_text(language, 'referral_report', 'Total brought')
        ]).to_excel(writer, index=False, sheet_name="referrals_report", startrow=startrow)

        startrow += len(referrals) + 3

        # блок 3 - детали начислений
        pd.DataFrame(incomes, columns=[
            get_text(language, 'referral_report', 'Deposit ID'),
            get_text(language, 'referral_report', 'Referral ID'),
            get_text(language, 'referral_report', 'Amount'),
            get_text(language, 'referral_report', 'Referral deposit percentage'),
            get_text(language, 'referral_report', 'Deposit date')
        ]).to_excel(writer, index=False, sheet_name="referrals_report", startrow=startrow)

        startrow += len(incomes) + 3

        # блок 4 - статистика
        stats_df = pd.DataFrame([
            [get_text(language, 'referral_report', 'Total referrals'), total_referrals],
            [get_text(language, 'referral_report', 'Total income'), total_income],
            [get_text(language, 'referral_report', 'Level 1 referrals'), level1],
            [get_text(language, 'referral_report', 'Level 2 referrals'), level2],
        ], columns=[get_text(language, 'referral_report', 'Metric'), get_text(language, 'referral_report', 'Value')])
        stats_df.to_excel(writer, index=False, sheet_name="referrals_report", startrow=startrow)

    buffer.seek(0)
    return buffer.getvalue()

