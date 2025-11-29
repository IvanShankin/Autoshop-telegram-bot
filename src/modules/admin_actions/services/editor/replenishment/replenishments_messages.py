from src.services.database.system.models import TypePayments
from src.utils.i18n import get_text


def message_type_payment(type_payment: TypePayments, language: str):
    return get_text(
        language,
        "admins_editor", "Top-up service_acc: {name_for_admin}\n\n"
        "ID: {ID}\n"
        "Username: {name_for_user}\n"
        "Index: {index}\n"
        "Show: {show}\n"
        "Commission: {commission}%%"
    ).format(
        name_for_admin=type_payment.name_for_admin,
        ID=type_payment.type_payment_id,
        name_for_user=type_payment.name_for_user,
        index=type_payment.index,
        show=type_payment.is_active,
        commission=type_payment.commission
    )