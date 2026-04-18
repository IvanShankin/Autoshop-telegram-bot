from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.models.read_models import UsersDTO
from src.modules.profile.keyboards.purchased_universals_kb import confirm_del_universal_kb, universal_kb
from src.modules.profile.services.purchases_universals import show_all_sold_universal, \
    delete_sold_universal_han, check_universal_product, send_media_sold_universal
from src.application.bot import Messages
from src.application.models.modules import ProfileModule
from src.infrastructure.translations import get_text

router = Router()


@router.callback_query(F.data.startswith("all_sold_universal:"))
async def all_sold_universal(
    callback: CallbackQuery, user: UsersDTO, messages_service: Messages, profile_module: ProfileModule,
):
    current_page = int(callback.data.split(':')[1])

    await show_all_sold_universal(
        user=user,
        message_id=callback.message.message_id,
        current_page=current_page,
        messages_service=messages_service,
        profile_module=profile_module,
    )


@router.callback_query(F.data.startswith("sold_universal:"))
async def sold_universal(
    callback: CallbackQuery, user: UsersDTO, profile_module: ProfileModule, messages_service: Messages
):
    sold_universal_id = int(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    universal = await check_universal_product(callback, user, sold_universal_id, profile_module)
    if not universal:
        return

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "profile_messages",
            "universal_product_details"
        ).format(
            product_id=universal.sold_universal_id,
            name=universal.universal_storage.name,
            sold_at=universal.sold_at.strftime(profile_module.conf.different.dt_format),
        ),
        event_message_key='purchased_universal',
        reply_markup=universal_kb(
            language=user.language,
            sold_universal_id=universal.sold_universal_id,
            current_page=current_page,
        )
    )


@router.callback_query(F.data.startswith("confirm_del_universal:"))
async def confirm_del_universal(
    callback: CallbackQuery, user: UsersDTO, profile_module: ProfileModule, messages_service: Messages
):
    sold_universal_id = int(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    universal = await check_universal_product(callback, user, sold_universal_id, profile_module)
    if not universal:
        return

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "profile_messages",
            "confirmation_delete_product"
        ).format(
            sold_universal_id=universal.sold_universal_id,
            name=universal.universal_storage.name,
        ),
        event_message_key='purchased_universal',
        reply_markup=confirm_del_universal_kb(
            language=user.language,
            sold_universal_id=universal.sold_universal_id,
            current_page=current_page,
        )
    )


@router.callback_query(F.data.startswith("get_universal_media:"))
async def get_universal_media(
    callback: CallbackQuery, user: UsersDTO, profile_module: ProfileModule, messages_service: Messages
):
    sold_universal_id = int(callback.data.split(':')[1])

    universal = await check_universal_product(callback, user, sold_universal_id, profile_module)
    if not universal:
        return

    await send_media_sold_universal(user.user_id, user.language, universal, messages_service, profile_module)


@router.callback_query(F.data.startswith("del_universal:"))
async def del_universal(
    callback: CallbackQuery, user: UsersDTO, profile_module: ProfileModule, messages_service: Messages
):
    sold_universal_id = int(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    universal = await check_universal_product(callback, user, sold_universal_id, profile_module)
    if not universal:
        return

    await delete_sold_universal_han(
        callback=callback,
        user=user,
        universal=universal,
        current_page=current_page,
        messages_service=messages_service,
        profile_module=profile_module,
    )
