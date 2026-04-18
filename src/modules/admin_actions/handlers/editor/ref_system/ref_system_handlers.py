from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.exceptions import InvalidAmountOfAchievement, InvalidSelectedLevel
from src.models.create_models.referrals import CreateReferralLevelDTO
from src.models.read_models import UsersDTO
from src.models.update_models import UpdateReferralLevelDTO
from src.modules.admin_actions.keyboards.editors.ref_system_kb import lvl_list_ref_system_kb, ref_lvl_editor_kb, \
    back_in_lvl_list_ref_system_kb, back_in_ref_lvl_editor_kb, confirm_del_lvl_kb
from src.modules.admin_actions.schemas import GetNewPersentData, GetAchievementAmountData, \
    CreateRefLevelData
from src.modules.admin_actions.state import GetNewPersent, GetAchievementAmount, CreateRefLevel

from src.utils.converter import safe_float_conversion, safe_int_conversion
from src.infrastructure.translations import get_text

router = Router()


async def show_ref_lvl_editor_func(
    ref_lvl_id: int,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
    new_message: bool = True,
    callback: CallbackQuery = None,
):
    _, ref_lvl, next_lvl = await admin_module.referral_levels_service.get_levels_nearby(ref_lvl_id)

    if not ref_lvl:
        error_message = get_text(user.language, "admins_editor_ref_system", "level_not_found")
        if callback:
            await callback.answer(error_message, show_alert=True)
            return

        await messages_service.send_msg.send(user.user_id, error_message, reply_markup=back_in_lvl_list_ref_system_kb(user.language))
        return


    if next_lvl:
        amount_of_achievement = get_text(
            user.language, "admins_editor_ref_system", "from_to_sum_formatted"
        ).format(from_sum=ref_lvl.amount_of_achievement, to_sum=next_lvl.amount_of_achievement)
    else:
        amount_of_achievement = get_text(
            user.language, "admins_editor_ref_system", "from_sum_formatted"
        ).format(from_sum=ref_lvl.amount_of_achievement)

    message = get_text(
        user.language,
        "admins_editor_ref_system",
        "ref_level_info"
    ).format(lvl=ref_lvl.level, percent=ref_lvl.percent, amount_of_achievement=amount_of_achievement)
    reply_markup = ref_lvl_editor_kb(
        user.language,
        ref_lvl_id,
        is_first_lvl= True if ref_lvl.level == 1 else False
    )

    if new_message:
        await messages_service.send_msg.send(user.user_id, message, event_message_key="admin_panel", reply_markup=reply_markup)
        return

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message,
        event_message_key="admin_panel",
        reply_markup=reply_markup
    )


@router.callback_query(F.data == "lvl_list_ref_system")
async def lvl_list_ref_system(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    await state.clear()
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        event_message_key="admin_panel",
        reply_markup=await lvl_list_ref_system_kb(user.language, admin_module=admin_module)
    )


@router.callback_query(F.data == "add_ref_lvl")
async def add_ref_lvl(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    referral_lvls  = await admin_module.referral_levels_service.get_referral_levels()
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_ref_system",
            "enter_achievement_amount_for_new_level"
        ).format(min_amount=referral_lvls[-1].amount_of_achievement if referral_lvls else 0),
        reply_markup=back_in_lvl_list_ref_system_kb(user.language)
    )
    await state.set_state(CreateRefLevel.get_achievement_amount)


@router.message(CreateRefLevel.get_achievement_amount)
async def get_achievement_amount_for_new(
    message: Message, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    amount_of_achievement = safe_int_conversion(message.text, positive=True)

    if not amount_of_achievement:
        await messages_service.send_msg.send(
            user.user_id,
            get_text(user.language, "miscellaneous", "incorrect_value_entered"),
            reply_markup=back_in_lvl_list_ref_system_kb(user.language)
        )
        return

    await messages_service.send_msg.send(
        user.user_id,
        get_text(user.language, "admins_editor_ref_system", "enter_deduction_percentage"),
        reply_markup=back_in_lvl_list_ref_system_kb(user.language)
    )
    await state.update_data(achievement_amount=amount_of_achievement)
    await state.set_state(CreateRefLevel.get_persent)


@router.message(CreateRefLevel.get_persent)
async def get_get_persent_for_new(
    message: Message, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    persent = safe_float_conversion(message.text, positive=True)

    if not persent:
        await messages_service.send_msg.send(
            user.user_id,
            get_text(user.language, "miscellaneous", "incorrect_value_entered"),
            reply_markup=back_in_lvl_list_ref_system_kb(user.language)
        )
        return

    data = CreateRefLevelData( **(await state.get_data()))

    try:
        new_lvl = await admin_module.referral_levels_service.add_referral_lvl(
            data=CreateReferralLevelDTO(
                amount_of_achievement=data.achievement_amount,
                percent=persent
            ),
        )
        message = get_text(
            user.language,
            "admins_editor_ref_system",
            "level_successfully_created"
        )
        reply_markup = back_in_ref_lvl_editor_kb(user.language, new_lvl.referral_level_id, i18n_key="in_level")
    except InvalidAmountOfAchievement as e:
        message = get_text(
            user.language,
            "admins_editor_ref_system",
            "incorrect_value_entered"
        ).format(
            condition=get_text(
                user.language,
                "admins_editor_ref_system",
                "new_amount_condition"
            ).format(
                more=e.amount_of_achievement_previous_lvl if e.amount_of_achievement_previous_lvl else 0,
                less=""
            )
        )
        reply_markup = back_in_lvl_list_ref_system_kb(user.language)

    await state.clear()
    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=message,
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("show_ref_lvl_editor:"))
async def show_ref_lvl_editor(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    ref_lvl_id = int(callback.data.split(":")[1])
    await show_ref_lvl_editor_func(
        ref_lvl_id=ref_lvl_id,
        user=user,
        new_message=False,
        callback=callback,
        admin_module=admin_module,
        messages_service=messages_service
    )


@router.callback_query(F.data.startswith("change_persent_ref_lvl:"))
async def change_persent_ref_lvl(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    ref_lvl_id = int(callback.data.split(":")[1])

    await messages_service.edit_msg.edit(
        user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "admins_editor_ref_system", "enter_new_percentage"),
        reply_markup=back_in_ref_lvl_editor_kb(user.language, ref_lvl_id)
    )

    await state.update_data(ref_lvl_id=ref_lvl_id)
    await state.set_state(GetNewPersent.get_new_persent)


@router.message(GetNewPersent.get_new_persent)
async def get_persent_for_update(
    message: Message, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    data = GetNewPersentData( **(await state.get_data()))
    persent = safe_float_conversion(message.text, positive=True)
    if not persent:
        await messages_service.send_msg.send(
            user.user_id,
            get_text(user.language, "miscellaneous","incorrect_value_entered"),
            reply_markup=back_in_ref_lvl_editor_kb(user.language, data.ref_lvl_id)
        )
        return

    await admin_module.referral_levels_service.update_referral_lvl(
        ref_lvl_id=data.ref_lvl_id,
        data=UpdateReferralLevelDTO(percent=persent)
    )

    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=get_text(user.language, "miscellaneous","data_updated_successfully"),
        reply_markup=back_in_ref_lvl_editor_kb(user.language, data.ref_lvl_id, i18n_key="in_level")
    )


@router.callback_query(F.data.startswith("change_achievement_amount:"))
async def change_achievement_amount(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    ref_lvl_id = int(callback.data.split(":")[1])
    previous_lvl, ref_lvl, next_lvl = await admin_module.referral_levels_service.get_levels_nearby(ref_lvl_id)

    await messages_service.edit_msg.edit(
        user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_ref_system",
            "enter_new_level_achievement_amount"
        ).format(
            condition=get_text(
                user.language,
        "admins_editor_ref_system",
            "new_amount_condition"
            ).format(
                more=previous_lvl.amount_of_achievement if previous_lvl else '0',
                less=get_text(
                    user.language,
                    "admins_editor_ref_system",
                    "and_less_formatted"
                ).format(less=next_lvl.amount_of_achievement) if next_lvl else "",
            )
        ),
        reply_markup=back_in_ref_lvl_editor_kb(user.language, ref_lvl_id)
    )

    await state.update_data(ref_lvl_id=ref_lvl_id)
    await state.set_state(GetAchievementAmount.get_new_achievement_amount)


@router.message(GetAchievementAmount.get_new_achievement_amount)
async def get_achievement_amount(
    message: Message, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    data = GetAchievementAmountData( **(await state.get_data()))
    amount_of_achievement = safe_int_conversion(message.text, positive=True)
    if not amount_of_achievement:
        await messages_service.send_msg.send(
            user.user_id,
            get_text(user.language, "miscellaneous","incorrect_value_entered"),
            reply_markup=back_in_ref_lvl_editor_kb(user.language, data.ref_lvl_id)
        )
        return

    try:
        await admin_module.referral_levels_service.update_referral_lvl(
            ref_lvl_id=data.ref_lvl_id,
            data=UpdateReferralLevelDTO(amount_of_achievement=amount_of_achievement),
        )
        message = get_text(user.language, "miscellaneous", "data_updated_successfully")
    except InvalidAmountOfAchievement as e:
        message = get_text(
            user.language,
            "admins_editor_ref_system",
            "incorrect_value_entered"
        ).format(
            condition=get_text(
                user.language,
        "admins_editor_ref_system",
            "new_amount_condition"
            ).format(
                more=e.amount_of_achievement_previous_lvl if e.amount_of_achievement_previous_lvl else 0,
                less=get_text(
                    user.language,
                    "admins_editor_ref_system",
                    "and_less_formatted"
                ).format(less=e.amount_of_achievement_next_lvl) if e.amount_of_achievement_next_lvl else "",
            )
        )
    except InvalidSelectedLevel:
        message = get_text(
            user.language,
            "admins_editor_ref_system",
            "unable_change_first_level_achievement"
        )


    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=message,
        reply_markup=back_in_ref_lvl_editor_kb(user.language, data.ref_lvl_id, i18n_key="in_level")
    )


@router.callback_query(F.data.startswith("confirm_delete_ref_lvl:"))
async def confirm_delete_ref_lvl(
    callback: CallbackQuery, user: UsersDTO, messages_service: Messages,
):
    ref_lvl_id = int(callback.data.split(":")[1])
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "admins_editor_ref_system", "confirmation_delete_level"),
        event_message_key="admin_panel",
        reply_markup=confirm_del_lvl_kb(user.language, referral_level_id=ref_lvl_id)
    )


@router.callback_query(F.data.startswith("delete_ref_lvl:"))
async def delete_ref_lvl(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    ref_lvl_id = int(callback.data.split(":")[1])
    try:
        await admin_module.referral_levels_service.delete_referral_lvl(ref_lvl_id)
        message = get_text(user.language, "admins_editor_ref_system", "level_successfully_removed")
    except InvalidSelectedLevel:
        message = get_text(user.language, "admins_editor_ref_system", "first_level_cannot_be_deleted")

    await callback.answer(message, show_alert=True)

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        event_message_key="admin_panel",
        reply_markup=await lvl_list_ref_system_kb(user.language, admin_module)
    )
