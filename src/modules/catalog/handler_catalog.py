from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.bot_actions.actions import send_message, edit_message
from src.middlewares.aiogram_middleware import I18nKeyFilter
from src.modules.catalog.keyboard_catalog import catalog_kb, subscription_prompt_kb
from src.services.database.users.actions import get_user
from src.services.redis.actions import get_subscription_prompt, delete_subscription_prompt
from src.utils.i18n import get_i18n

router_with_repl_kb = Router()
router = Router()

@router_with_repl_kb.message(I18nKeyFilter("Product catalog"))
async def handle_catalog_message(message: Message, state: FSMContext):
    await state.clear()
    user = await get_user(message.from_user.id, message.from_user.username)

    if await get_subscription_prompt(user.user_id): # если пользователю ранее не предлагали подписаться
        i18n = get_i18n(user.language, 'catalog')
        await send_message(
            chat_id=user.user_id,
            message=i18n.gettext(
                'Want to stay up-to-date on all the latest news? \n'
                'Subscribe to our channel where we share news and special offers'
            ),
            image_key='subscription_prompt',
            reply_markup=await subscription_prompt_kb(user.language)
        )
        return

    await send_message(
        chat_id=user.user_id,
        image_key='main_catalog',
        fallback_image_key="default_catalog_account",
        reply_markup=catalog_kb(user.language)
    )

async def edit_message_in_catalog(user_id: int, username: str, old_message_id: int):
    user = await get_user(user_id, username)
    await edit_message(
        message_id=old_message_id,
        chat_id=user.user_id,
        image_key='main_catalog',
        fallback_image_key="default_catalog_account",
        reply_markup=catalog_kb(user.language)
    )

@router.callback_query(F.data == "skip_subscription")
async def skip_subscription(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await delete_subscription_prompt(callback.from_user.id) # больше не просим подписаться

    await edit_message_in_catalog(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        old_message_id=callback.message.message_id
    )


@router.callback_query(F.data == "catalog")
async def handle_catalog_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await edit_message_in_catalog(
        user_id = callback.from_user.id,
        username = callback.from_user.username,
        old_message_id = callback.message.message_id
    )