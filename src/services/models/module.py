from src.config import Config
from src.services.models.users import WalletTransactionService, UserService, MoneyTransferService
from src.services.models.users.permission_service import PermissionService


class ProfileModule:

    def __init__(
        self,
        conf: Config,
        user_service: UserService,
        permission_service: PermissionService,
        wallet_transaction_service: WalletTransactionService,
        money_transfer_service: MoneyTransferService,
    ):
        self.conf = conf
        self.user_service = user_service
        self.permission_service = permission_service
        self.wallet_transaction_service = wallet_transaction_service
        self.money_transfer_service = money_transfer_service
