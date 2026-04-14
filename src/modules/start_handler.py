from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.application.bot import Messages
from src.application.models.modules import ProfileModule, AdminModule
from src.models.create_models.users import CreateUserDTO
from src.models.update_models import UpdateUserDTO
from src.modules.keyboard_main import main_kb, selecting_language
from src.database.models.discount import Vouchers
from src.database.models.users import Users
from src.utils.i18n import get_text

router = Router()

@router.message(CommandStart())
async def cmd_start(
    message: Message, command: CommandObject, state: FSMContext,
    profile_module: ProfileModule, messages_service: Messages, admin_modul: AdminModule
):
    await state.clear()

    user = await profile_module.user_service.get_user(message.from_user.id, username=message.from_user.username)
    voucher: Vouchers | None = None
    result_message_voucher: str | None = None
    success_activate_voucher: bool | None = None
    owner_user: Users | None = None
    language = user.language if user  else 'ru'

    args = command.args

    if args:
        params = args.split('_')
        if params[0] == 'voucher': # если активировали ваучер
            voucher_code = params[1]
            voucher = await profile_module.voucher_service.get_valid_voucher_by_code(params[1]) # ваучера может не быть
            if voucher and user:
                result_message_voucher, success_activate_voucher = await profile_module.voucher_service.activate_voucher(
                    user, voucher_code, language
                )
        elif params[0] == 'ref':
            owner_user = await profile_module.user_service.get_user_by_ref_code(params[1])

    if user: # если пользователь уже есть

        if result_message_voucher: # если необходимо вернуть результат активации ваучера
            image_key = 'successfully_activate_voucher' if success_activate_voucher else 'unsuccessfully_activate_voucher'
            await messages_service.send_msg.send(
                chat_id=message.from_user.id,
                message=result_message_voucher,
                event_message_key=image_key,
            )
        else: # простое приветственное сообщение
            setting = await profile_module.settings_service.get_settings()
            text = get_text(
                language,
                "start_message",
                "welcome_message"
            ).format(shop_name=setting.shop_name, channel_name=setting.channel_name)
            await messages_service.send_msg.send(
                chat_id=message.from_user.id,
                message=text,
                event_message_key='welcome_message',
                reply_markup=await main_kb(language, user.user_id, admin_modul)
            )

    else: # если пользователя нет
        user = await profile_module.user_service.create_user(
            data=CreateUserDTO(
                user_id=message.from_user.id,
                username=message.from_user.username
            )
        )

        if voucher and user:# если необходимо вернуть результат активации ваучера
            result_message_voucher, success_activate_voucher = await profile_module.voucher_service.activate_voucher(
                user, voucher_code, language
            )

            image_key = 'successfully_activate_voucher' if success_activate_voucher else 'unsuccessfully_activate_voucher'
            await messages_service.send_msg.send(
                chat_id=message.from_user.id,
                message=result_message_voucher,
                event_message_key=image_key,
            )
            if success_activate_voucher:
                if not await admin_modul.admin_service.check_admin(voucher.creator_id): # если создатель ваучера это не админ
                    owner_user = await profile_module.user_service.get_user(voucher.creator_id) # далее создастся реферал

        if owner_user: # если пользователь должен стать рефераллом
            await profile_module.referral_service.add_referral(referral_id=user.user_id, owner_id=owner_user.user_id)

            text = get_text(
                language,
                "referral_messages",
                "new_referral_invited"
            ).format(username= f'@{user.username}' if user.username else 'None')
            await messages_service.send_msg.send(chat_id=owner_user.user_id, message=text, event_message_key='new_referral')

        # Выбор языка. Именно таким текстом, ибо не знаем какой язык знает пользователь
        await messages_service.send_msg.send(
            chat_id=message.from_user.id,
            message="Выберите язык \n\nSelect language",
            event_message_key='selecting_language',
            reply_markup=selecting_language
        )


@router.callback_query(F.data.startswith('set_language_after_start'))
async def select_language(callback: CallbackQuery, user: Users, profile_module: ProfileModule, messages_service: Messages, admin_modul: AdminModule):
    selected_lang = callback.data.split(':')[1]
    setting = await profile_module.settings_service.get_settings()

    await profile_module.user_service.update_user(
        user_id=user.user_id,
        data=UpdateUserDTO(language=selected_lang),
        make_commit=True,
        filling_redis=True
    )

    text = get_text(
        selected_lang,
        "start_message",
        "welcome_message"
    ).format(shop_name=setting.shop_name, channel_name=setting.channel_name)
    await messages_service.send_msg.send(
        chat_id=callback.from_user.id,
        message=text,
        event_message_key='welcome_message',
        reply_markup=await main_kb(user.language, user.user_id, admin_modul)
    )




