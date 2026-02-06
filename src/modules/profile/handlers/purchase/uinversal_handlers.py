from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message
from src.modules.profile.keyboards.purchased_universals_kb import confirm_del_universal_kb
from src.modules.profile.services.purchases_universals import show_sold_universal, show_all_sold_universal, \
    delete_sold_universal_han, check_universal_product, send_media_sold_universal
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()


@router.callback_query(F.data.startswith("all_sold_universal:"))
async def all_sold_universal(callback: CallbackQuery, user: Users):
    current_page = int(callback.data.split(':')[1])

    await show_all_sold_universal(
        user_id=callback.from_user.id,
        language=user.language,
        message_id=callback.message.message_id,
        current_page=current_page,
    )


@router.callback_query(F.data.startswith("sold_universal:"))
async def sold_universal(callback: CallbackQuery, user: Users):
    sold_universal_id = int(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    universal = await check_universal_product(callback, user, sold_universal_id)
    if not universal:
        return

    await show_sold_universal(
        callback=callback,
        universal=universal,
        language=user.language,
        current_page=current_page,
    )


@router.callback_query(F.data.startswith("confirm_del_universal:"))
async def confirm_del_universal(callback: CallbackQuery, user: Users):
    sold_universal_id = int(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    universal = await check_universal_product(callback, user, sold_universal_id)
    if not universal:
        return

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "profile_messages",
            "confirmation_delete_product"
        ).format(
            sold_universal_id=universal.sold_universal_id,
            name=universal.universal_storage.name,
        ),
        image_key='purchased_universal',
        reply_markup=confirm_del_universal_kb(
            language=user.language,
            sold_universal_id=universal.sold_universal_id,
            current_page=current_page,
        )
    )


@router.callback_query(F.data.startswith("get_universal_media:"))
async def get_universal_media(callback: CallbackQuery, user: Users):
    sold_universal_id = int(callback.data.split(':')[1])

    universal = await check_universal_product(callback, user, sold_universal_id)
    if not universal:
        return

    await send_media_sold_universal(user.user_id, user.language, universal)


@router.callback_query(F.data.startswith("del_universal:"))
async def del_universal(callback: CallbackQuery, user: Users):
    sold_universal_id = int(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    universal = await check_universal_product(callback, user, sold_universal_id)
    if not universal:
        return

    await delete_sold_universal_han(
            callback=callback,
            user=user,
            universal=universal,
            current_page=current_page
        )
