import os

import pytest
from openpyxl import load_workbook

from src.services.database.referrals.reports import generate_referral_report_exel


@pytest.mark.asyncio
async def test_generate_referral_report(create_new_user, create_referral, create_income_from_referral):
    user = await create_new_user()
    ref_1, _, _ = await create_referral(owner_id=user.user_id)
    ref_2, _, _ = await create_referral(owner_id=user.user_id)
    ref_3, _, _ = await create_referral(owner_id=user.user_id)

    income_1, _, _ = await create_income_from_referral(referral_user_id=ref_1.referral_id, owner_id=user.user_id)
    income_2, _, _ = await create_income_from_referral(referral_user_id=ref_1.referral_id, owner_id=user.user_id)
    income_3, _, _ = await create_income_from_referral(referral_user_id=ref_1.referral_id, owner_id=user.user_id)

    path = await generate_referral_report_exel(user.user_id, 'ru')

    # Проверяем, что Excel читается
    wb = load_workbook(path)
    sheet = wb["referrals_report"]

    # Проверим, что есть хотя бы одна строка с ID владельца
    values = [cell for row in sheet.iter_rows(values_only=True) for cell in row if cell]
    assert any(str(user.user_id) in str(v) for v in values), "ID владельца не найден в файле"

    wb.close()
    os.remove(path)