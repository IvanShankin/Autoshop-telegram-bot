from aiogram import Router, F
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.application.bot import Messages
from src.application.models.modules import AdminModule, ProfileModule
from src.database.models.users import Users
from src.exceptions import VoucherInvalidActivateOwner
from src.exceptions.business import InvalidVoucher, VoucherAlreadyActivate
from src.exceptions.domain import UserNotFound, VoucherNotFound
from src.infrastructure.translations import get_text
from src.models.create_models.users import CreateUserDTO
from src.models.read_models import UsersDTO
from src.models.update_models import UpdateUserDTO
from src.modules.keyboard_main import main_kb, selecting_language

router = Router()


def _parse_start_args(args: str | None) -> tuple[str | None, str | None]:
    if not args:
        return None, None

    command, *rest = args.split("_", 1)
    payload = rest[0] if rest else None
    return command, payload


async def _activate_voucher(
    profile_module: ProfileModule,
    user: UsersDTO,
    voucher_code: str,
    language: str,
) -> tuple[str | None, bool]:
    try:
        voucher = await profile_module.voucher_service.activate_voucher(user, voucher_code)
        refreshed_user = await profile_module.user_service.get_user(user.user_id)
        if not refreshed_user:
            return get_text(language, "discount", "voucher_not_found"), False

        return (
            get_text(language, "discount", "voucher_successfully_activated").format(
                amount=voucher.amount,
                new_balance=refreshed_user.balance,
            ),
            True,
        )
    except (VoucherNotFound, UserNotFound):
        return get_text(language, "discount", "voucher_not_found"), False
    except VoucherInvalidActivateOwner:
        return get_text(language, "discount", "cannot_activate_own_voucher"), False
    except InvalidVoucher as error:
        return (
            get_text(language, "discount", "voucher_expired_due_to_time").format(
                id=error.voucher.voucher_id,
                code=error.voucher.activation_code,
            ),
            False,
        )
    except VoucherAlreadyActivate:
        return get_text(language, "discount", "voucher_already_activated"), False


async def _send_voucher_result(
    messages_service: Messages,
    message: Message,
    text: str | None,
    success: bool,
) -> None:
    if not text:
        return

    await messages_service.send_msg.send(
        chat_id=message.from_user.id,
        message=text,
        event_message_key="successfully_activate_voucher" if success else "unsuccessfully_activate_voucher",
    )


async def _send_welcome(
    messages_service: Messages,
    message: Message,
    language: str,
    user_id: int,
    profile_module: ProfileModule,
    admin_module: AdminModule,
) -> None:
    settings = await profile_module.settings_service.get_settings()
    text = get_text(language, "start_message", "welcome_message").format(
        shop_name=settings.shop_name,
        channel_name=settings.channel_name,
    )
    await messages_service.send_msg.send(
        chat_id=message.from_user.id,
        message=text,
        event_message_key="welcome_message",
        reply_markup=await main_kb(language, user_id, admin_module),
    )


async def _send_language_selection(messages_service: Messages, message: Message) -> None:
    await messages_service.send_msg.send(
        chat_id=message.from_user.id,
        message="Выберите язык\n\nSelect language",
        event_message_key="selecting_language",
        reply_markup=selecting_language,
    )


async def _handle_referral_from_voucher(
    profile_module: ProfileModule,
    admin_module: AdminModule,
    messages_service: Messages,
    language: str,
    user: UsersDTO,
    voucher_code: str,
    create_new_ref: bool,
) -> None:
    voucher = await profile_module.voucher_service.get_valid_voucher_by_code(voucher_code)
    if not voucher:
        return

    if await admin_module.admin_service.check_admin(voucher.creator_id):
        return

    owner_user = await profile_module.user_service.get_user(voucher.creator_id)
    if not owner_user or voucher.is_created_admin:
        return

    if create_new_ref:
        await profile_module.referral_service.add_referral(
            referral_id=user.user_id,
            owner_id=owner_user.user_id,
        )

        text = get_text(language, "referral_messages", "new_referral_invited").format(
            username=f"@{user.username}" if user.username else "None",
        )
        await messages_service.send_msg.send(
            chat_id=owner_user.user_id,
            message=text,
            event_message_key="new_referral",
        )


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    user: UsersDTO,
    profile_module: ProfileModule,
    messages_service: Messages,
    admin_module: AdminModule,
):
    await state.clear()

    existing_user = user is not None
    language = user.language if user else "ru"
    command_name, payload = _parse_start_args(command.args)

    if not user:
        user = await profile_module.user_service.create_user(
            data=CreateUserDTO(
                user_id=message.from_user.id,
                username=message.from_user.username,
            )
        )

    if command_name == "voucher" and payload:
        if user:
            result_message, success = await _activate_voucher(
                profile_module=profile_module,
                user=user,
                voucher_code=payload,
                language=language,
            )
            await _send_voucher_result(messages_service, message, result_message, success)

            if success:
                await _handle_referral_from_voucher(
                    profile_module=profile_module,
                    admin_module=admin_module,
                    messages_service=messages_service,
                    language=language,
                    user=user,
                    voucher_code=payload,
                    create_new_ref=False if existing_user else True # если пользователь ранее не был в боте, то создаём рефералла
                )
            if not existing_user:
                await _send_language_selection(messages_service, message)
            return

        await _send_language_selection(messages_service, message)
        return

    if command_name == "ref" and payload:
        owner_user = await profile_module.user_service.get_user_by_ref_code(payload)
        if (owner_user and user) and (owner_user.user_id != user.user_id) and not existing_user:
            await profile_module.referral_service.add_referral(
                referral_id=user.user_id,
                owner_id=owner_user.user_id,
            )

            text = get_text(language, "referral_messages", "new_referral_invited").format(
                username=f"@{user.username}" if user.username else "None",
            )
            await messages_service.send_msg.send(
                chat_id=owner_user.user_id,
                message=text,
                event_message_key="new_referral",
            )

        if existing_user:
            await _send_welcome(
                messages_service=messages_service,
                message=message,
                language=language,
                user_id=user.user_id,
                profile_module=profile_module,
                admin_module=admin_module,
            )
        else:
            await _send_language_selection(messages_service, message)
        return

    if user:
        await _send_welcome(
            messages_service=messages_service,
            message=message,
            language=language,
            user_id=user.user_id,
            profile_module=profile_module,
            admin_module=admin_module,
        )
        return

    await _send_language_selection(messages_service, message)


@router.callback_query(F.data.startswith("set_language_after_start"))
async def select_language(
    callback: CallbackQuery,
    user: Users,
    profile_module: ProfileModule,
    messages_service: Messages,
    admin_module: AdminModule,
):
    selected_lang = callback.data.split(":")[1]
    settings = await profile_module.settings_service.get_settings()

    await profile_module.user_service.update_user(
        user_id=user.user_id,
        data=UpdateUserDTO(language=selected_lang),
        make_commit=True,
        filling_redis=True,
    )

    text = get_text(
        selected_lang,
        "start_message",
        "welcome_message",
    ).format(shop_name=settings.shop_name, channel_name=settings.channel_name)
    await messages_service.send_msg.send(
        chat_id=callback.from_user.id,
        message=text,
        event_message_key="welcome_message",
        reply_markup=await main_kb(selected_lang, user.user_id, admin_module),
    )
