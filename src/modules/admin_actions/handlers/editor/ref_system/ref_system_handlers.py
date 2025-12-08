from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.exceptions.service_exceptions import InvalidAmountOfAchievement, InvalidSelectedLevel
from src.modules.admin_actions.keyboards.editors.ref_system_kb import lvl_list_ref_system_kb, ref_lvl_editor_kb, \
    back_in_lvl_list_ref_system_kb, back_in_ref_lvl_editor_kb, confirm_del_lvl_kb
from src.modules.admin_actions.schemas import GetNewPersentData, GetAchievementAmountData, \
    CreateRefLevelData
from src.modules.admin_actions.state import GetNewPersent, GetAchievementAmount, CreateRefLevel
from src.services.database.referrals.actions import get_referral_lvl, update_referral_lvl
from src.services.database.referrals.actions.actions_ref_lvls import get_levels_nearby, delete_referral_lvl, \
    add_referral_lvl
from src.services.database.users.models import Users
from src.utils.converter import safe_float_conversion, safe_int_conversion
from src.utils.i18n import get_text

router = Router()


async def show_ref_lvl_editor_func(ref_lvl_id: int, user: Users, new_message: bool = True, callback: CallbackQuery = None):
    _, ref_lvl, next_lvl = await get_levels_nearby(ref_lvl_id)

    if not ref_lvl:
        error_message = get_text(user.language, "admins_editor", "Level not found")
        if callback:
            await callback.answer(error_message, show_alert=True)
            return

        await send_message(user.user_id, error_message, reply_markup=back_in_lvl_list_ref_system_kb(user.language))
        return


    if next_lvl:
        amount_of_achievement = get_text(
            user.language, "admins_editor", "from {from_sum}₽ to {to_sum}₽"
        ).format(from_sum=ref_lvl.amount_of_achievement, to_sum=next_lvl.amount_of_achievement)
    else:
        amount_of_achievement = get_text(
            user.language, "admins_editor", "from {from_sum}₽"
        ).format(from_sum=ref_lvl.amount_of_achievement)

    message = get_text(
        user.language,
        "admins_editor",
        "Level: {lvl} \nPercentage of referral's replenishment: {percent} \nLevel achievement amount: {amount_of_achievement}"
    ).format(lvl=ref_lvl.level, percent=ref_lvl.percent, amount_of_achievement=amount_of_achievement)
    reply_markup = ref_lvl_editor_kb(
        user.language,
        ref_lvl_id,
        is_first_lvl= True if ref_lvl.level == 1 else False
    )

    if new_message:
        await send_message(user.user_id, message, image_key="admin_panel", reply_markup=reply_markup)
        return

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message,
        image_key="admin_panel",
        reply_markup=reply_markup
    )


@router.callback_query(F.data == "lvl_list_ref_system")
async def lvl_list_ref_system(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        image_key="admin_panel",
        reply_markup=await lvl_list_ref_system_kb(user.language)
    )


@router.callback_query(F.data == "add_ref_lvl")
async def add_ref_lvl(callback: CallbackQuery, state: FSMContext, user: Users):
    referral_lvls  = await get_referral_lvl()
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor",
            "Enter the achievement amount for the new level \n\nThe amount must be at least {min_amount}₽"
        ).format(min_amount=referral_lvls[-1].amount_of_achievement if referral_lvls else 0),
        reply_markup=back_in_lvl_list_ref_system_kb(user.language)
    )
    await state.set_state(CreateRefLevel.get_achievement_amount)


@router.message(CreateRefLevel.get_achievement_amount)
async def get_achievement_amount_for_new(message: Message, state: FSMContext, user: Users):
    amount_of_achievement = safe_int_conversion(message.text, positive=True)

    if not amount_of_achievement:
        await send_message(
            user.user_id,
            get_text(user.language, 'miscellaneous', "Incorrect value entered"),
            reply_markup=back_in_lvl_list_ref_system_kb(user.language)
        )
        return

    await send_message(
        user.user_id,
        get_text(user.language, 'admins_editor', "Enter the percentage of deduction"),
        reply_markup=back_in_lvl_list_ref_system_kb(user.language)
    )
    await state.update_data(achievement_amount=amount_of_achievement)
    await state.set_state(CreateRefLevel.get_persent)


@router.message(CreateRefLevel.get_persent)
async def get_get_persent_for_new(message: Message, state: FSMContext, user: Users):
    persent = safe_float_conversion(message.text, positive=True)

    if not persent:
        await send_message(
            user.user_id,
            get_text(user.language, 'miscellaneous', "Incorrect value entered"),
            reply_markup=back_in_lvl_list_ref_system_kb(user.language)
        )
        return

    data = CreateRefLevelData( **(await state.get_data()))

    try:
        new_lvl = await add_referral_lvl(amount_of_achievement=data.achievement_amount, percent=persent)
        message = get_text(
            user.language,
            "admins_editor",
            "Level successfully created!"
        )
        reply_markup = back_in_ref_lvl_editor_kb(user.language, new_lvl.referral_level_id, i18n_key="In level")
    except InvalidAmountOfAchievement as e:
        message = get_text(
            user.language,
            "admins_editor",
            "Incorrect value entered \n\n{condition}"
        ).format(
            condition=get_text(
                user.language,
                "admins_editor",
                "The new amount must be more than {more}₽ {less}"
            ).format(
                more=e.amount_of_achievement_previous_lvl if e.amount_of_achievement_previous_lvl else 0,
                less=""
            )
        )
        reply_markup = back_in_lvl_list_ref_system_kb(user.language)

    await state.clear()
    await send_message(
        chat_id=user.user_id,
        message=message,
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("show_ref_lvl_editor:"))
async def show_ref_lvl_editor(callback: CallbackQuery, user: Users):
    ref_lvl_id = int(callback.data.split(":")[1])
    await show_ref_lvl_editor_func(ref_lvl_id=ref_lvl_id, user=user, new_message=False, callback=callback)


@router.callback_query(F.data.startswith("change_persent_ref_lvl:"))
async def change_persent_ref_lvl(callback: CallbackQuery, state: FSMContext, user: Users):
    ref_lvl_id = int(callback.data.split(":")[1])

    await edit_message(
        user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "admins_editor", "Enter a new percentage"),
        reply_markup=back_in_ref_lvl_editor_kb(user.language, ref_lvl_id)
    )

    await state.update_data(ref_lvl_id=ref_lvl_id)
    await state.set_state(GetNewPersent.get_new_persent)


@router.message(GetNewPersent.get_new_persent)
async def get_persent_for_update(message: Message, state: FSMContext, user: Users):
    data = GetNewPersentData( **(await state.get_data()))
    persent = safe_float_conversion(message.text, positive=True)
    if not persent:
        await send_message(
            user.user_id,
            get_text(user.language, 'miscellaneous',"Incorrect value entered"),
            reply_markup=back_in_ref_lvl_editor_kb(user.language, data.ref_lvl_id)
        )
        return

    await update_referral_lvl(ref_lvl_id=data.ref_lvl_id, percent=persent)

    await send_message(
        chat_id=user.user_id,
        message=get_text(user.language, 'miscellaneous',"Data updated successfully"),
        reply_markup=back_in_ref_lvl_editor_kb(user.language, data.ref_lvl_id, i18n_key="In level")
    )


@router.callback_query(F.data.startswith("change_achievement_amount:"))
async def change_achievement_amount(callback: CallbackQuery, state: FSMContext, user: Users):
    ref_lvl_id = int(callback.data.split(":")[1])
    previous_lvl, ref_lvl, next_lvl = await get_levels_nearby(ref_lvl_id)

    await edit_message(
        user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor",
            "Enter a new level achievement amount. \n\n{condition}"
        ).format(
            condition=get_text(
                user.language,
        "admins_editor",
            "The new amount must be more than {more}₽ {less}"
            ).format(
                more=previous_lvl.amount_of_achievement if previous_lvl else '0',
                less=get_text(
                    user.language,
                    "admins_editor",
                    "and less {less}₽"
                ).format(less=next_lvl.amount_of_achievement) if next_lvl else "",
            )
        ),
        reply_markup=back_in_ref_lvl_editor_kb(user.language, ref_lvl_id)
    )

    await state.update_data(ref_lvl_id=ref_lvl_id)
    await state.set_state(GetAchievementAmount.get_new_achievement_amount)


@router.message(GetAchievementAmount.get_new_achievement_amount)
async def get_achievement_amount(message: Message, state: FSMContext, user: Users):
    data = GetAchievementAmountData( **(await state.get_data()))
    amount_of_achievement = safe_int_conversion(message.text, positive=True)
    if not amount_of_achievement:
        await send_message(
            user.user_id,
            get_text(user.language, 'miscellaneous',"Incorrect value entered"),
            reply_markup=back_in_ref_lvl_editor_kb(user.language, data.ref_lvl_id)
        )
        return

    try:
        await update_referral_lvl(ref_lvl_id=data.ref_lvl_id, amount_of_achievement=amount_of_achievement)
        message = get_text(user.language, 'miscellaneous', "Data updated successfully")
    except InvalidAmountOfAchievement as e:
        message = get_text(
            user.language,
            "admins_editor",
            "Incorrect value entered \n\n{condition}"
        ).format(
            condition=get_text(
                user.language,
        "admins_editor",
            "The new amount must be more than {more}₽ {less}"
            ).format(
                more=e.amount_of_achievement_previous_lvl if e.amount_of_achievement_previous_lvl else 0,
                less=get_text(
                    user.language,
                    "admins_editor",
                    "and less {less}₽"
                ).format(less=e.amount_of_achievement_next_lvl) if e.amount_of_achievement_next_lvl else "",
            )
        )
    except InvalidSelectedLevel:
        message = get_text(
            user.language,
            "admins_editor",
            "Unable to change the achievement amount for the first level"
        )


    await send_message(
        chat_id=user.user_id,
        message=message,
        reply_markup=back_in_ref_lvl_editor_kb(user.language, data.ref_lvl_id, i18n_key="In level")
    )


@router.callback_query(F.data.startswith("confirm_delete_ref_lvl:"))
async def confirm_delete_ref_lvl(callback: CallbackQuery, user: Users):
    ref_lvl_id = int(callback.data.split(":")[1])
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "admins_editor", "Are you sure you want to delete this level?"),
        image_key="admin_panel",
        reply_markup=confirm_del_lvl_kb(user.language, referral_level_id=ref_lvl_id)
    )


@router.callback_query(F.data.startswith("delete_ref_lvl:"))
async def delete_ref_lvl(callback: CallbackQuery, user: Users):
    ref_lvl_id = int(callback.data.split(":")[1])
    try:
        await delete_referral_lvl(ref_lvl_id)
        message = get_text(user.language, "admins_editor", "Level successfully removed!")
    except InvalidSelectedLevel:
        message = get_text(user.language, "admins_editor", "The first level cannot be deleted")

    await callback.answer(message, show_alert=True)

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        image_key="admin_panel",
        reply_markup=await lvl_list_ref_system_kb(user.language)
    )
