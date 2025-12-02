from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton


def pagination_keyboard(
        records: list,
        current_page: int,
        total_pages: int,
        item_button_func,
        left_prefix: str,
        right_prefix: str,
        back_text: str,
        back_callback: str,
):
    """
    Универсальный конструктор пагинационных клавиатур.

    :param records: список записей для текущей страницы
    :param current_page: текущая страница
    :param total_pages: общее кол-во страниц
    :param item_button_func: функция(record) → InlineKeyboardButton
    :param left_prefix: callback prefix для кнопки 'влево'
    :param right_prefix: callback prefix для кнопки 'вправо'
    :param back_text: текст кнопки Назад
    :param back_callback: callback кнопки Назад
    """

    keyboard = InlineKeyboardBuilder()

    # --- Кнопки элементов ---
    for record in records:
        keyboard.row(item_button_func(record))

    # --- Кнопки пагинации ---
    if records and total_pages > 1:
        # значения по умолчанию (когда переход невозможен)
        left_button = f"{left_prefix}_none"
        right_button = f"{right_prefix}_none"

        if current_page > 1 and total_pages > current_page:
            left_button = f"{left_prefix}:{current_page - 1}"
            right_button = f"{right_prefix}:{current_page + 1}"
        elif current_page == 1:
            right_button = f"{right_prefix}:{current_page + 1}"
        elif current_page > 1:
            left_button = f"{left_prefix}:{current_page - 1}"

        keyboard.row(
            InlineKeyboardButton(text="⬅️", callback_data=left_button),
            InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="none"),
            InlineKeyboardButton(text="➡️", callback_data=right_button),
        )

    # --- Кнопка Назад ---
    keyboard.row(
        InlineKeyboardButton(text=back_text, callback_data=back_callback)
    )

    return keyboard.as_markup()
