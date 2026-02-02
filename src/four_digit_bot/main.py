import asyncio
import io
import math
import logging
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from .config import load_settings
from .db import create_repository
from .keyboards import CONFIRM_CLEAR, MAIN_KEYBOARD
from .middleware import AccessMiddleware
from .services import CodeService


class ImportStates(StatesGroup):
    waiting_for_file = State()


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def padded(code: int) -> str:
    return f"{code:04d}"


def cumulative_success_prob(total: int, success_count: int, draws: int) -> float:
    """Probability to hit at least one success when drawing without replacement."""
    if draws <= 0 or success_count <= 0 or total <= 0:
        return 0.0
    draws = min(draws, total)
    success_count = min(success_count, total)
    if draws > total - success_count:
        return 1.0
    return 1 - math.comb(total - success_count, draws) / math.comb(total, draws)


async def handle_start(message: Message, code_service: CodeService):
    remaining = await code_service.remaining()
    await message.answer(
        f"Привет! Я выдам уникальный 4-значный код. Осталось {remaining} из 10000.\n"
        "Используй кнопки ниже.",
        reply_markup=MAIN_KEYBOARD,
    )


async def handle_code(message: Message, code_service: CodeService, settings: Any):
    code = await code_service.take_code()
    if code is None:
        await message.answer("Коды закончились 😞", reply_markup=MAIN_KEYBOARD)
        return
    remaining = await code_service.remaining()
    attempts = settings.total_codes - remaining
    prob = cumulative_success_prob(settings.total_codes, settings.winning_codes, attempts) * 100
    await message.answer(
        (
            f"Ваш код: <b>{padded(code)}</b>\n"
            f"Осталось {remaining} из {settings.total_codes}.\n"
            f"Вероятность, что за {attempts} попыток поймали хотя бы один из "
            f"{settings.winning_codes} целевых: {prob:.2f}%"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_KEYBOARD,
    )


async def handle_export(message: Message, code_service: CodeService):
    buffer = await code_service.export_used_text()
    content = buffer.getvalue()
    filename = "codes.txt"
    await message.answer_document(
        document=BufferedInputFile(content.encode("utf-8"), filename=filename),
        caption=f"Экспортировано {len(content.splitlines())} кодов",
        reply_markup=MAIN_KEYBOARD,
    )


async def handle_import_request(message: Message, state: FSMContext):
    await state.set_state(ImportStates.waiting_for_file)
    await message.answer(
        "Отправьте txt файл с кодами (по одному в строке, 0000-9999).",
        reply_markup=MAIN_KEYBOARD,
    )


async def handle_import_file(message: Message, bot: Bot, state: FSMContext, code_service: CodeService):
    if not message.document:
        await message.answer("Нужен txt файл." , reply_markup=MAIN_KEYBOARD)
        return
    if not (message.document.file_name or "").lower().endswith(".txt"):
        await message.answer("Файл должен быть .txt", reply_markup=MAIN_KEYBOARD)
        return

    buffer = io.BytesIO()
    await bot.download(message.document, destination=buffer)
    buffer.seek(0)
    text = buffer.read().decode("utf-8", errors="ignore")
    codes = CodeService.parse_codes_from_text(text)
    if not codes:
        await message.answer("Не нашёл валидных кодов в файле.", reply_markup=MAIN_KEYBOARD)
        await state.clear()
        return

    marked = await code_service.import_used_codes(codes)
    await message.answer(
        f"Импорт завершён. Отмечено использованными: {marked} из {len(set(codes))} переданных.",
        reply_markup=MAIN_KEYBOARD,
    )
    await state.clear()


async def handle_clear(message: Message, code_service: CodeService):
    # Экспорт перед очисткой
    buffer = await code_service.export_used_text()
    content = buffer.getvalue()
    filename = "codes.txt"
    await message.answer_document(
        document=BufferedInputFile(content.encode("utf-8"), filename=filename),
        caption=f"Экспортировано {len(content.splitlines())} кодов. Очистить список?",
        reply_markup=CONFIRM_CLEAR,
    )


async def confirm_clear(callback: CallbackQuery, code_service: CodeService):
    cleared = await code_service.clear_used()
    await callback.message.edit_caption(
        caption=f"Список очищен. Сброшено {cleared} кодов.",
        reply_markup=None,
    )
    await callback.answer("Очищено")


async def cancel_clear(callback: CallbackQuery):
    await callback.answer("Отменено")
    if callback.message:
        await callback.message.edit_caption(caption="Очистка отменена", reply_markup=None)


async def handle_remaining(message: Message, code_service: CodeService):
    remaining = await code_service.remaining()
    await message.answer(f"Осталось {remaining} кодов из 10000.", reply_markup=MAIN_KEYBOARD)


async def on_startup(bot: Bot, settings: Any):
    logging.info("Bot started with allowed users: %s", settings.allowed_user_ids)


async def main():
    setup_logging()
    settings = load_settings()
    repo = await create_repository(settings.database_path)
    code_service = CodeService(repo)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    allowed_ids = set(settings.allowed_user_ids)
    dp.message.middleware(AccessMiddleware(allowed_ids))
    dp.callback_query.middleware(AccessMiddleware(allowed_ids))

    dp.startup.register(on_startup)

    dp.message.register(handle_start, Command("start"))
    dp.message.register(handle_code, Command("code"))
    dp.message.register(handle_code, F.text == "🔢 Получить код")
    dp.message.register(handle_export, Command("export"))
    dp.message.register(handle_export, F.text == "📤 Экспорт")
    dp.message.register(handle_import_request, Command("import"))
    dp.message.register(handle_import_request, F.text == "📥 Импорт")
    dp.message.register(handle_clear, Command("clear"))
    dp.message.register(handle_clear, F.text == "🧹 Очистить")
    dp.message.register(handle_remaining, Command("remaining"))

    dp.message.register(handle_import_file, ImportStates.waiting_for_file)

    dp.callback_query.register(confirm_clear, F.data == "confirm_clear")
    dp.callback_query.register(cancel_clear, F.data == "cancel_clear")

    try:
        await dp.start_polling(
            bot,
            settings=settings,
            code_service=code_service,
        )
    finally:
        await repo.close()


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
