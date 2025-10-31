import os
from datetime import datetime
import pandas as pd

from src.config import DT_FORMAT, TEMP_FILE_DIR
from src.services.database.referrals.actions.actions_ref import get_all_referrals, get_referral_income_page
from src.services.database.users.actions import get_user
from src.utils.i18n import get_i18n


def _strip_tz(value: datetime) -> str:
    """Убирает timezone из datetime, если есть и преобразует в строку"""
    if isinstance(value, datetime) and value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    return value.strftime(DT_FORMAT)

async def generate_referral_report_exel(owner_user_id: int, language: str) -> str:
    """
    Формирует файл с данными о рефералах. Файл не удаляется после создания.
    :return Путь к файлу
    """
    i18n = get_i18n(language, 'referral_report')

    referrals_orm = await get_all_referrals(owner_user_id)
    incomes_orm = await get_referral_income_page(owner_user_id)

    referrals: list[dict] = []
    for referral in referrals_orm:
        referral_user = await get_user(referral.referral_id)
        new_dict = {}
        new_dict[i18n.gettext('Referral ID')] = referral.referral_id
        new_dict[i18n.gettext('Referral username')] = referral_user.username
        new_dict[i18n.gettext('Level')] = referral.level
        new_dict[i18n.gettext('Join date')] = _strip_tz(referral.created_at)

        total_income = 0
        for income in incomes_orm:
            if income.referral_id == referral.referral_id:
                total_income += income.amount

        new_dict[i18n.gettext('Total brought')] = total_income
        referrals.append(new_dict)

    incomes: list[dict] = []
    for income in incomes_orm:
        new_dict = {}
        new_dict[i18n.gettext('Deposit ID')] = income.income_from_referral_id
        new_dict[i18n.gettext('Referral ID')] = income.referral_id
        new_dict[i18n.gettext('Amount')] = income.amount
        new_dict[i18n.gettext('Referral deposit percentage')] = income.percentage_of_replenishment
        new_dict[i18n.gettext('Deposit date')] = _strip_tz(income.created_at)

        incomes.append(new_dict)

    # Считаем статистику
    total_referrals = len(referrals)
    total_income = sum(income.amount or 0 for income in incomes_orm)
    level1 = len([r for r in referrals_orm if r.level == 1])
    level2 = len([r for r in referrals_orm if r.level == 2])

    # Формируем excel
    os.makedirs(TEMP_FILE_DIR, exist_ok=True)
    temp_path = TEMP_FILE_DIR /  f"referrals_report_{owner_user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    with pd.ExcelWriter(temp_path, engine="openpyxl") as writer:
        # блок 1 - служебная информация
        info_df = pd.DataFrame([
            [i18n.gettext('Export date'), datetime.now().strftime(DT_FORMAT)],
            [i18n.gettext('Owner ID'), owner_user_id],
            [i18n.gettext('Total referrals'), total_referrals],
            [i18n.gettext('Total income'), total_income],
        ], columns=[i18n.gettext('Parameter'), i18n.gettext('Parameter')])
        info_df.to_excel(writer, index=False, sheet_name="referrals_report", startrow=0)

        startrow = len(info_df) + 2

        # блок 2 - список рефералов
        pd.DataFrame(referrals, columns=[
            i18n.gettext('Referral ID'), i18n.gettext('Referral username'), i18n.gettext('Level'),
            i18n.gettext('Join date'), i18n.gettext('Total brought')
        ]).to_excel(writer, index=False, sheet_name="referrals_report", startrow=startrow)

        startrow += len(referrals) + 3

        # блок 3 - детали начислений
        pd.DataFrame(incomes, columns=[
            i18n.gettext('Deposit ID'), i18n.gettext('Referral ID'), i18n.gettext('Amount'),
            i18n.gettext('Referral deposit percentage'), i18n.gettext('Deposit date')
        ]).to_excel(writer, index=False, sheet_name="referrals_report", startrow=startrow)

        startrow += len(incomes) + 3

        # блок 4 - статистика
        stats_df = pd.DataFrame([
            [i18n.gettext('Total referrals'), total_referrals],
            [i18n.gettext('Total income'), total_income],
            [i18n.gettext('Level 1 referrals'), level1],
            [i18n.gettext('Level 2 referrals'), level2],
        ], columns=[i18n.gettext('Metric'), i18n.gettext('Value')])
        stats_df.to_excel(writer, index=False, sheet_name="referrals_report", startrow=startrow)

    return temp_path

