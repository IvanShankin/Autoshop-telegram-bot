from src.modules.admin_actions.state.editors.editor_categories import GetServiceName, GetDataForCategory, \
    UpdateNameForCategory, RenameService, UpdateDescriptionForCategory, UpdateCategoryImage, ImportTgAccounts, \
    UpdateNumberInCategory, ImportOtherAccounts
from src.modules.admin_actions.state.editors.editor_images import GetNewImage
from src.modules.admin_actions.state.editors.editor_promo_code import CreatePromoCode
from src.modules.admin_actions.state.editors.editor_ref_system import GetNewPersent, GetAchievementAmount, \
    CreateRefLevel
from src.modules.admin_actions.state.editors.editor_replenishment import GetTypePaymentName, GetTypePaymentCommission
from src.modules.admin_actions.state.editors.editor_vouchers import CreateAdminVoucher
from src.modules.admin_actions.state.user_management import GetUserIdOrUsername, IssueBan, SetNewBalance


__all__ = [
    # категории
    "GetServiceName",
    "RenameService",
    "GetDataForCategory",
    "UpdateNameForCategory",
    "UpdateDescriptionForCategory",
    "UpdateCategoryImage",
    "UpdateNumberInCategory",
    "ImportTgAccounts",
    "ImportOtherAccounts",

    # изображения
    "GetNewImage",

    # промокоды
    "CreatePromoCode",

    # реферальная система
    "GetNewPersent",
    "GetAchievementAmount",
    "CreateRefLevel",

    # пополнение
    "GetTypePaymentName",
    "GetTypePaymentCommission",

    # ваучеры
    "CreateAdminVoucher",

    # управление пользователями
    "GetUserIdOrUsername",
    "SetNewBalance",
    "IssueBan",
]
