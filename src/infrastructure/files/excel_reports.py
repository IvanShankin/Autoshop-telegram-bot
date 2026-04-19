import io
from datetime import datetime, UTC
from typing import Callable

import pandas as pd

from src.application.utils.date_time_formatter import DateTimeFormatter
from src.models.read_models import ReferralReportDTO


class ExcelReportExporter:

    def __init__(
        self,
        get_text: Callable,
        dt_formatter: DateTimeFormatter
    ):
        self.get_text = get_text
        self.dt_formatter = dt_formatter

    def _format_date(self, value: datetime) -> str:
        return self.dt_formatter.format(value)

    def export(
        self,
        data: ReferralReportDTO,
        language: str,
        owner_user_id: int
    ) -> bytes:

        buffer = io.BytesIO()

        # ===== referrals =====
        referrals_rows = [
            {
                self.get_text(language, "referral_report", "referral_id"): r.referral_id,
                self.get_text(language, "referral_report", "referral_username"): r.username,
                self.get_text(language, "referral_report", "level"): r.level,
                self.get_text(language, "referral_report", "join_date"): self.dt_formatter.format(r.join_date),
                self.get_text(language, "referral_report", "total_brought"): r.total_income,
            }
            for r in data.referrals
        ]

        # ===== incomes =====
        incomes_rows = [
            {
                self.get_text(language, "referral_report", "deposit_id"): i.deposit_id,
                self.get_text(language, "referral_report", "referral_id"): i.referral_id,
                self.get_text(language, "referral_report", "amount"): i.amount,
                self.get_text(language, "referral_report", "referral_deposit_percentage"): i.percentage,
                self.get_text(language, "referral_report", "deposit_date"): self._format_date(i.created_at),
            }
            for i in data.incomes
        ]

        # ===== stats =====
        total_referrals = len(data.referrals)
        total_income = sum(i.amount for i in data.incomes)

        level1 = sum(1 for r in data.referrals if r.level == 1)
        level2 = sum(1 for r in data.referrals if r.level == 2)

        # ===== Excel =====
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:

            sheet = "referrals_report"

            info_df = pd.DataFrame([
                [self.get_text(language, "referral_report", "export_date"),
                 self.dt_formatter.format(datetime.now(UTC))],
                [self.get_text(language, "referral_report", "owner_id"), owner_user_id],
                [self.get_text(language, "referral_report", "total_referrals"), total_referrals],
                [self.get_text(language, "referral_report", "total_income"), total_income],
            ], columns=[
                self.get_text(language, "referral_report", "parameter"),
                self.get_text(language, "referral_report", "value"),
            ])

            info_df.to_excel(writer, index=False, sheet_name=sheet, startrow=0)

            startrow = len(info_df) + 2

            pd.DataFrame(referrals_rows).to_excel(
                writer, index=False, sheet_name=sheet, startrow=startrow
            )

            startrow += len(referrals_rows) + 3

            pd.DataFrame(incomes_rows).to_excel(
                writer, index=False, sheet_name=sheet, startrow=startrow
            )

            startrow += len(incomes_rows) + 3

            stats_df = pd.DataFrame([
                [self.get_text(language, "referral_report", "total_referrals"), total_referrals],
                [self.get_text(language, "referral_report", "total_income"), total_income],
                [self.get_text(language, "referral_report", "level_1_referrals"), level1],
                [self.get_text(language, "referral_report", "level_2_referrals"), level2],
            ], columns=[
                self.get_text(language, "referral_report", "metric"),
                self.get_text(language, "referral_report", "value"),
            ])

            stats_df.to_excel(writer, index=False, sheet_name=sheet, startrow=startrow)

        buffer.seek(0)
        return buffer.getvalue()