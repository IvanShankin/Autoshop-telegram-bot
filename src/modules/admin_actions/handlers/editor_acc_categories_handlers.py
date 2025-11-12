import asyncio

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.actions import edit_message, send_message
from src.exceptions.service_exceptions import ServiceTypeBusy, ServiceContainsCategories
from src.modules.admin_actions.keyboard_admin import all_services_account_admin_kb, all_services_types_kb, \
    to_services_kb, show_service_acc_admin_kb, back_in_service_kb, delete_service_kb
from src.modules.admin_actions.schemas.editor_categories import GetServiceNameData, RenameServiceData
from src.modules.admin_actions.state.editor_categories import GetServiceName, RenameService
from src.services.database.selling_accounts.actions import get_account_service, \
    add_account_services, update_account_service, delete_account_service
from src.services.database.users.models import Users
from src.utils.core_logger import logger

router = Router()



