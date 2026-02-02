from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


MAIN_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔢 Получить код")],
        [KeyboardButton(text="📤 Экспорт"), KeyboardButton(text="📥 Импорт")],
        [KeyboardButton(text="🧹 Очистить")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
)

CONFIRM_CLEAR = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, очистить", callback_data="confirm_clear"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel_clear"),
        ]
    ]
)
