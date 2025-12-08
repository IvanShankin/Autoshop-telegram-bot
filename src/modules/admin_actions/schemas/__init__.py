from src.modules.admin_actions.schemas.editors.editor_categories import GetServiceNameData, GetDataForCategoryData, \
    UpdateNameForCategoryData, RenameServiceData, UpdateDescriptionForCategoryData, UpdateCategoryOnlyId, \
    ImportAccountsData
from src.modules.admin_actions.schemas.editors.editor_images import GetNewImageData
from src.modules.admin_actions.schemas.editors.editor_promo_code import CreatePromoCodeData
from src.modules.admin_actions.schemas.editors.editor_ref_system import GetNewPersentData, GetAchievementAmountData, \
    CreateRefLevelData
from src.modules.admin_actions.schemas.editors.editor_replenishment import GetTypePaymentNameData, \
    GetTypePaymentCommissionData
from src.modules.admin_actions.schemas.editors.editor_vouchers import CreateAdminVoucherData
from src.modules.admin_actions.schemas.user_management import SetNewBalanceData, IssueBanData

__all__ = [
    "GetServiceNameData",
    "RenameServiceData",
    "GetDataForCategoryData",
    "UpdateNameForCategoryData",
    "UpdateDescriptionForCategoryData",
    "UpdateCategoryOnlyId",
    "ImportAccountsData",
    "GetNewImageData",
    "CreatePromoCodeData",
    "GetNewPersentData",
    "GetAchievementAmountData",
    "CreateRefLevelData",
    "GetTypePaymentNameData",
    "GetTypePaymentCommissionData",
    "CreateAdminVoucherData",
    "SetNewBalanceData",
    "IssueBanData"
]

