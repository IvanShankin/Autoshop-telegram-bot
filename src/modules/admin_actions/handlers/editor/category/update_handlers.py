import io

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.exceptions import AccountCategoryNotFound, TheCategoryStorageProducts
from src.infrastructure.telegram.bot_client import TelegramClient
from src.models.read_models import UsersDTO
from src.models.update_models import UpdateUiImageDTO
from src.models.update_models.category import UpdateCategory, UpdateCategoryTranslationsDTO
from src.modules.admin_actions.handlers.editor.category.show_handlers import show_category
from src.modules.admin_actions.keyboards import select_lang_category_kb, back_in_category_update_data_kb
from src.modules.admin_actions.keyboards.editors.category_kb import back_in_category_editor_kb, \
    select_account_service_type, select_product_type, select_universal_media_type
from src.modules.admin_actions.schemas import UpdateNameForCategoryData, \
    UpdateDescriptionForCategoryData, UpdateCategoryOnlyId
from src.modules.admin_actions.services import safe_get_category, update_data, update_message_query_data, upload_category
from src.modules.admin_actions.services.editor.category.category_updater import update_category_storage
from src.modules.admin_actions.services.editor.category.show_message import show_category_update_data
from src.modules.admin_actions.state import UpdateNameForCategory, \
    UpdateDescriptionForCategory, UpdateCategoryImage, UpdateNumberInCategory
from src.database.models.categories import ProductType, AccountServiceType, UniversalMediaType
from src.utils.i18n import get_text


router = Router()


@router.callback_query(F.data.startswith("category_update_storage:"))
async def category_update_storage(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    category_id = int(callback.data.split(':')[1])
    is_storage = bool(int(callback.data.split(':')[2])) # что необходимо установить

    if not is_storage:  # если необходимо убрать возможность хранения
        await update_category_storage(
            category_id=category_id,
            is_storage=is_storage,
            user=user,
            callback=callback,
            admin_module=admin_module,
            messages_service=messages_service,
        )
        return

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_category",
            "select_product_type"
        ),
        reply_markup=select_product_type(user.language, category_id)
    )


@router.callback_query(F.data.startswith("choice_product_type:"))
async def choice_product_type(
    callback: CallbackQuery,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    category_id = int(callback.data.split(':')[1])
    product_type = callback.data.split(':')[2]

    if not any(product_type == prod_tp.value for prod_tp in ProductType):
        await callback.answer(
            get_text(user.language, "admins_editor_category", "selected_product_type_not_found")
        )
        await show_category(
            user=user,
            category_id=category_id,
            message_id=callback.message.message_id,
            callback=callback,
            admin_module=admin_module,
            messages_service=messages_service,
        )
        return

    message = None
    reply_markup = None
    if product_type == ProductType.ACCOUNT.value:
        message = get_text(
            user.language,
            "admins_editor_category",
            "select_service_account"
        )
        reply_markup = select_account_service_type(user.language, category_id)
    elif product_type == ProductType.UNIVERSAL.value:
        message = get_text(
            user.language,
            "admins_editor_category",
            "select_product_media_type"
        )
        for media in UniversalMediaType:
            message += get_text(
                user.language,
                "admins_editor_category",
                media.value
            )

        reply_markup = select_universal_media_type(user.language, category_id)

    # ПРИ РАСШИРЕНИИ ПРОДУКТОВ ДОБАВИТЬ БОЛЬШЕ УСЛОВИЙ

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message if message else "None",
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("choice_account_service:"))
async def choice_account_service(
    callback: CallbackQuery,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    category_id = int(callback.data.split(':')[1])
    account_service = callback.data.split(':')[2]

    if not any(account_service == acc_ser.value for acc_ser in AccountServiceType):
        await callback.answer(
            get_text(user.language, "admins_editor_category", "selected_service_account_not_found")
        )
        await show_category(
            user=user,
            category_id=category_id,
            message_id=callback.message.message_id,
            callback=callback,
            admin_module=admin_module,
            messages_service=messages_service,
        )
        return

    await update_category_storage(
        category_id=category_id,
        is_storage=True,
        product_type=ProductType.ACCOUNT,
        type_account_service=AccountServiceType(account_service),
        user=user,
        callback=callback,
        admin_module=admin_module,
        messages_service=messages_service,
    )


@router.callback_query(F.data.startswith("choice_universal_media_type:"))
async def choice_universal_media_type(
    callback: CallbackQuery,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    category_id = int(callback.data.split(':')[1])
    universal_media_type = callback.data.split(':')[2]

    if not any(universal_media_type == acc_ser.value for acc_ser in UniversalMediaType):
        await callback.answer(
            get_text(user.language, "admins_editor_category", "selected_type_not_found")
        )
        await show_category(
            user=user,
            category_id=category_id,
            message_id=callback.message.message_id,
            callback=callback,
            admin_module=admin_module,
            messages_service=messages_service,
        )
        return

    await update_category_storage(
        category_id=category_id,
        is_storage=True,
        product_type=ProductType.UNIVERSAL,
        media_type=UniversalMediaType(universal_media_type),
        user=user,
        callback=callback,
        admin_module=admin_module,
        messages_service=messages_service,
    )


@router.callback_query(F.data.startswith("category_update_index:"))
async def service_update_index(
    callback: CallbackQuery,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    category_id = int(callback.data.split(':')[1])
    new_index = int(callback.data.split(':')[2])

    if new_index >= 0:
        await admin_module.category_service.update_category(
            category_id,
            data=UpdateCategory(index=new_index)
        )

    await callback.answer(get_text(user.language, "miscellaneous","successfully_updated"))
    await show_category(
        user=user,
        category_id=category_id,
        message_id=callback.message.message_id,
        callback=callback,
        admin_module=admin_module,
        messages_service=messages_service,
    )


@router.callback_query(F.data.startswith("category_update_show:"))
async def service_update_show(
    callback: CallbackQuery,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    category_id = int(callback.data.split(':')[1])
    show = bool(int(callback.data.split(':')[2]))

    await admin_module.category_service.update_category(category_id, data=UpdateCategory(show=show))
    await callback.answer(get_text(user.language, "miscellaneous","successfully_updated"))
    await show_category(
        user=user,
        category_id=category_id,
        message_id=callback.message.message_id,
        callback=callback,
        admin_module=admin_module,
        messages_service=messages_service,
    )


@router.callback_query(F.data.startswith("category_update_reuse_product:"))
async def service_update_show(
    callback: CallbackQuery,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    category_id = int(callback.data.split(':')[1])
    reuse_product = bool(int(callback.data.split(':')[2]))

    try:
        await admin_module.category_service.update_category(category_id, data=UpdateCategory(reuse_product=reuse_product))
        await show_category(
            user=user,
            category_id=category_id,
            message_id=callback.message.message_id,
            callback=callback,
            admin_module=admin_module,
            messages_service=messages_service,
        )
    except TheCategoryStorageProducts:
        await callback.answer(
            get_text(
                user.language,
                "admins_editor_category",
                "category_should_not_store_products"
            ),
            show_alert=True
        )


@router.callback_query(F.data.startswith("category_update_multiple_purchase:"))
async def service_update_show(
    callback: CallbackQuery,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    category_id = int(callback.data.split(':')[1])
    allow_multiple_purchase = bool(int(callback.data.split(':')[2]))

    await admin_module.category_service.update_category(
        category_id, data=UpdateCategory(allow_multiple_purchase=allow_multiple_purchase)
    )
    await callback.answer(get_text(user.language, "miscellaneous", "successfully_updated"))
    await show_category(
        user=user,
        category_id=category_id,
        message_id=callback.message.message_id,
        callback=callback,
        admin_module=admin_module,
        messages_service=messages_service,
    )


@router.callback_query(F.data.startswith("category_update_data:"))
async def category_update_data(
    callback: CallbackQuery,
    state: FSMContext,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    category_id = int(callback.data.split(':')[1])
    await state.clear()
    await show_category(
        user=user,
        category_id=category_id,
        message_id=callback.message.message_id,
        callback=callback,
        admin_module=admin_module,
        messages_service=messages_service,
    )


@router.callback_query(F.data.startswith("category_update_name_or_des:"))
async def category_update_name_or_des(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    category_id = int(callback.data.split(':')[1])

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_category",
            "select_the_language_for_change"
        ),
        reply_markup=select_lang_category_kb(user.language, category_id, admin_module)
    )


@router.callback_query(F.data.startswith("category_update_name:"))
async def category_update_name(
    callback: CallbackQuery,
    state: FSMContext,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    category_id = int(callback.data.split(':')[1])
    lang = callback.data.split(':')[2]
    category = await safe_get_category(
        category_id, user=user, callback=callback, admin_module=admin_module, messages_service=messages_service
    )
    if not category:
        return

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_category",
            "enter_new_name_category"
        ).format(name=category.name),
        reply_markup=back_in_category_update_data_kb(user.language, category_id)
    )

    await state.update_data(category_id=category_id, language=lang)
    await state.set_state(UpdateNameForCategory.name)


@router.message(UpdateNameForCategory.name)
async def get_name_for_update(
    message: Message,
    state: FSMContext,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    data = UpdateNameForCategoryData( **(await state.get_data()))
    try:
        await admin_module.translations_category_service.update_category_translation(
            data=UpdateCategoryTranslationsDTO(
                category_id=data.category_id,
                language=data.language,
                name=message.text,
            ),
            make_commit=True,
            filling_redis=True,
        )
        message = get_text(user.language, "admins_editor_category", "name_changed_successfully")
        reply_markup = back_in_category_update_data_kb(user.language, data.category_id)
    except AccountCategoryNotFound:
        message = get_text(user.language, "admins_editor_category","category_not_exists")
        reply_markup = back_in_category_editor_kb(user.language)

    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=message,
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("category_update_descr:"))
async def category_update_descr(
    callback: CallbackQuery,
    state: FSMContext,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    category_id = int(callback.data.split(':')[1])
    lang = callback.data.split(':')[2]
    category = await safe_get_category(
        category_id, user=user, callback=callback, admin_module=admin_module, messages_service=messages_service
    )
    if not category:
        return

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_category",
            "enter_new_description_category"
        ).format(description=category.description),
        reply_markup=back_in_category_update_data_kb(user.language, category_id)
    )

    await state.update_data(category_id=category_id, language=lang)
    await state.set_state(UpdateDescriptionForCategory.description)


@router.message(UpdateDescriptionForCategory.description)
async def get_description_for_update(
    message: Message,
    state: FSMContext,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    data = UpdateDescriptionForCategoryData( **(await state.get_data()))
    try:
        await admin_module.translations_category_service.update_category_translation(
            data=UpdateCategoryTranslationsDTO(
                category_id=data.category_id,
                language=data.language,
                description=message.text,
            ),
            make_commit=True,
            filling_redis=True,
        )
        message = get_text(user.language, "admins_editor_category", "description_changed_successfully")
        reply_markup = back_in_category_update_data_kb(user.language, data.category_id)
    except AccountCategoryNotFound:
        message = get_text(user.language, "admins_editor_category","category_not_exists")
        reply_markup=back_in_category_editor_kb(user.language)

    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=message,
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("update_show_ui_default_category:"))
async def update_show_ui_default_category(
    callback: CallbackQuery,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    category_id = int(callback.data.split(':')[1])
    set_show = bool(int(callback.data.split(':')[2]))
    category = await safe_get_category(
        category_id, user=user, callback=callback, admin_module=admin_module, messages_service=messages_service
    )
    if not category:
        return

    await admin_module.ui_images_service.update_ui_image(
        key=category.ui_image_key,
        data=UpdateUiImageDTO(show=set_show),
        make_commit=True,
        filling_redis=True,
    )
    await show_category_update_data(
        user=user,
        category_id=category_id,
        callback=callback,
        admin_module=admin_module,
        messages_service=messages_service
    )


@router.callback_query(F.data.startswith("category_update_image:"))
async def category_update_image(callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,):
    category_id = int(callback.data.split(':')[1])
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_category",
            "send_photo_as_document"
        ),
        reply_markup=back_in_category_update_data_kb(user.language, category_id)
    )
    await state.update_data(category_id=category_id)
    await state.set_state(UpdateCategoryImage.image)


@router.message(UpdateCategoryImage.image, F.document)
async def update_category_image(
    message: Message,
    state: FSMContext,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    doc = message.document
    data = UpdateCategoryOnlyId(**(await state.get_data()))
    category = await safe_get_category(
        data.category_id, user=user, callback=None, admin_module=admin_module, messages_service=messages_service
    )
    if not category:
        return

    reply_markup = None

    if not doc.mime_type.startswith("image/"): # Проверяем, что это действительно изображение
        text = get_text(user.language,"admins_editor_category", "this_is_not_image")
        reply_markup = back_in_category_update_data_kb(user.language, category.category_id)
    elif doc.file_size > admin_module.conf.limits.max_size_bytes: # Проверяем размер, известный Telegram (без скачивания)
        text = get_text(
            user.language,
            "admins_editor_category",
            "file_to_many_long"
        ).format(max_size_mb=admin_module.conf.limits.max_size_mb)
        reply_markup = back_in_category_update_data_kb(user.language, category.category_id)
    else:
        # Получаем объект файла
        file = await message.bot.get_file(doc.file_id)

        # Скачиваем файл в поток
        byte_stream = io.BytesIO()
        await message.bot.download_file(file.file_path, byte_stream)

        # Преобразуем поток  bytes
        file_bytes = byte_stream.getvalue()
        try:
            await admin_module.category_service.update_category(
                data.category_id, data=UpdateCategory(), file_data=file_bytes
            )
            text = get_text(user.language, "admins_editor_category", "image_installed_successfully")
            reply_markup = back_in_category_update_data_kb(user.language, category.category_id)
        except AccountCategoryNotFound:
            text = get_text(user.language, "admins_editor_category", "category_not_exists")

    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=text,
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("category_update_price:"))
async def category_update_price(callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,):
    await update_message_query_data(
        callback, state, user,
        i18n_key="send_integer_the_price_for_one_product",
        set_state=UpdateNumberInCategory.price,
        messages_service=messages_service,
    )


@router.callback_query(F.data.startswith("category_update_cost_price:"))
async def category_update_cost_price(callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,):
    await update_message_query_data(
        callback, state, user,
        i18n_key="send_integer_the_cost_price_for_one_product",
        set_state=UpdateNumberInCategory.cost_price,
        messages_service=messages_service,
    )


@router.callback_query(F.data.startswith("category_update_number_button:"))
async def category_update_number_button(callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,):
    await update_message_query_data(
        callback, state, user,
        i18n_key="send_integer_number_of_buttons_in_one_line",
        set_state=UpdateNumberInCategory.number_button,
        messages_service=messages_service,
    )


@router.message(UpdateNumberInCategory.price)
async def category_update_price(
    message: Message, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    await update_data(message, state, user, admin_module=admin_module, messages_service=messages_service)


@router.message(UpdateNumberInCategory.cost_price)
async def acc_category_cost_price(
    message: Message, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    await update_data(message, state, user, admin_module=admin_module, messages_service=messages_service)


@router.message(UpdateNumberInCategory.number_button)
async def acc_category_number_button(
    message: Message, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    await update_data(message, state, user, admin_module=admin_module, messages_service=messages_service)


@router.callback_query(F.data.startswith("category_upload_products:"))
async def category_upload_products(
    callback: CallbackQuery,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
    tg_client: TelegramClient,
):
    category_id = int(callback.data.split(':')[1])
    category = await safe_get_category(
        category_id,
        user=user,
        callback=None,
        admin_module=admin_module,
        messages_service=messages_service,
    )
    if not category:
        return

    await upload_category(
        category,
        user,
        callback,
        admin_module=admin_module,
        messages_service=messages_service,
        tg_client=tg_client,
    )
