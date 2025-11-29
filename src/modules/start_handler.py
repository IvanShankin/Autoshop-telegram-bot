from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.modules.keyboard_main import main_kb, selecting_language
from src.bot_actions.messages import send_message
from src.services.database.admins.actions import check_admin
from src.services.database.discounts.actions import get_valid_voucher_by_code, activate_voucher
from src.services.database.discounts.models import Vouchers
from src.services.database.referrals.actions.actions_ref import add_referral
from src.services.database.system.actions import get_settings
from src.services.database.users.actions import get_user
from src.services.database.users.actions.action_other_with_user import add_new_user
from src.services.database.users.actions.action_user import get_user_by_ref_code, update_user
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()

    user = await get_user(message.from_user.id, username=message.from_user.username)
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
            voucher = await get_valid_voucher_by_code(params[1]) # ваучера может не быть
            if voucher and user:
                result_message_voucher, success_activate_voucher = await activate_voucher(user, voucher_code, language)
        elif params[0] == 'ref':
            owner_user = await get_user_by_ref_code(params[1])

    if user: # если пользователь уже есть

        if result_message_voucher: # если необходимо вернуть результат активации ваучера
            image_key = 'successfully_activate_voucher' if success_activate_voucher else 'unsuccessfully_activate_voucher'
            await send_message(
                chat_id=message.from_user.id,
                message=result_message_voucher,
                image_key=image_key,
            )
        else: # простое приветственное сообщение
            setting = await get_settings()
            text = get_text(
                language,
                'start_message',
                'Welcome to {shop_name} SHOP! \nOur news channel: @{channel_name} \nHappy shopping!'
            ).format(shop_name=setting.shop_name, channel_name=setting.channel_name)
            await send_message(
                chat_id=message.from_user.id,
                message=text,
                image_key='welcome_message',
                reply_markup=await main_kb(language, user.user_id)
            )

    else: # если пользователя нет
        user = await add_new_user(user_id = message.from_user.id, username = message.from_user.username)

        if voucher and user:# если необходимо вернуть результат активации ваучера
            result_message_voucher, success_activate_voucher = await activate_voucher(user, voucher_code, language)

            image_key = 'successfully_activate_voucher' if success_activate_voucher else 'unsuccessfully_activate_voucher'
            await send_message(
                chat_id=message.from_user.id,
                message=result_message_voucher,
                image_key=image_key,
            )
            if success_activate_voucher:
                if not await check_admin(voucher.creator_id): # если создатель ваучера это не админ
                    owner_user = await get_user(voucher.creator_id) # далее создастся реферал

        if owner_user: # если пользователь должен стать рефераллом
            await add_referral(referral_id=user.user_id, owner_id=owner_user.user_id)

            text = get_text(
                language,
                'referral_messages',
                "You've invited a new referral!\n"
                "Username: {username}\n\n"
                "Thank you for using our services!"
            ).format(username= f'@{user.username}' if user.username else 'None')
            await send_message(chat_id=owner_user.user_id, message=text, image_key='new_referral')

        # Выбор языка. Именно таким текстом, ибо не знаем какой язык знает пользователь
        await send_message(
            chat_id=message.from_user.id,
            message="Выберите язык \n\nSelect language",
            image_key='selecting_language',
            reply_markup=selecting_language
        )

@router.callback_query(F.data.startswith('set_language_after_start'))
async def select_language(callback: CallbackQuery, user: Users):
    selected_lang = callback.data.split(':')[1]
    setting = await get_settings()

    await update_user(user_id=user.user_id, language=selected_lang)

    text = get_text(
        selected_lang,
        'start_message',
        'Welcome to {shop_name} SHOP! \nOur news channel: @{channel_name} \nHappy shopping!'
    ).format(shop_name=setting.shop_name, channel_name=setting.channel_name)
    await send_message(
        chat_id=callback.from_user.id,
        message=text,
        image_key='welcome_message',
        reply_markup=await main_kb(user.language, user.user_id)
    )




