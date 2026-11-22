import asyncio
import logging
import os
import re
from collections import defaultdict, deque

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()

MAIN_BOT_URL = "https://t.me/GenScoreAi_bot"
HISTORY_LIMIT = 6
MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """Ты — вежливый, краткий и полезный ассистент поддержки IT-проекта GenScore AI (команда разработчика Арсена из Якутии).
Твоя задача: отвечать на вопросы пользователей о работе сервиса, помогать разобраться с интерфейсом и направлять в основного бота @GenScoreAi_bot (https://t.me/GenScoreAi_bot).
О продукте GenScore AI:
- Это умный спортивный справочник и ИИ-помощник в Telegram Mini App.
- Как пользоваться: зайти в @GenScoreAi_bot, открыть Mini App, загрузить обычный скриншот предстоящего матча (из расписания или афиши) — через 5 секунд нейросеть распознает команды и выдаст сводку (составы, травмы, форму команд, статистику).
- Условия доступа: первый пробный разбор доступен бесплатно сразу после запуска. Дополнительные +10 запросов открываются после активации партнерского аккаунта внутри Mini App (после регистрации система начисляет запросы автоматически).
Правила общения:
- Никогда не используй слова «ставки», «букмекер», «казино», «рулетка», «выигрыш», «коэффициенты» или названия партнерских площадок. Позиционируй сервис строго как информационную IT-утилиту и спортивный справочник.
- Отвечай коротко (2–4 предложения), по делу, без воды.
- Если пользователь спрашивает, где попробовать или куда кидать скриншот — давай ссылку https://t.me/GenScoreAi_bot.
- Если пользователь пишет про рекламу, покупку/продажу трафика, сотрудничество, баг с начислением +10 запросов или просит связаться с менеджером/админом — вежливо напиши, что передал обращение менеджеру, и попроси прикрепить детали (например, скриншот или ID), если нужно.
"""

WELCOME_TEXT = (
    "Здравствуйте! На связи поддержка команды GenScore AI.\n\n"
    "Проект разрабатывает Арсен из Якутии. Здесь можно задать вопрос "
    "по работе сервиса или написать о сотрудничестве.\n\n"
    "Опишите ситуацию обычным сообщением — я отвечу в этом чате. "
    "Открыть GenScore AI можно кнопкой ниже."
)

OPEN_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🚀 Открыть GenScore AI",
                url=MAIN_BOT_URL,
            )
        ]
    ]
)

USER_ID_RE = re.compile(r"\(ID:\s*(\d+)\)")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("genscore-support")

histories: dict[int, deque[dict[str, str]]] = defaultdict(
    lambda: deque(maxlen=HISTORY_LIMIT)
)
history_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def require_settings() -> int:
    missing = [
        name
        for name, value in (
            ("BOT_TOKEN", BOT_TOKEN),
            ("OPENAI_API_KEY", OPENAI_API_KEY),
            ("ADMIN_ID", ADMIN_ID_RAW),
        )
        if not value
    ]
    if missing:
        raise SystemExit(
            "Заполните в файле .env: " + ", ".join(missing) + ". Образец — .env.example."
        )
    if not ADMIN_ID_RAW.isdigit():
        raise SystemExit("ADMIN_ID в .env должен быть числовым Telegram ID.")
    return int(ADMIN_ID_RAW)


ADMIN_ID = require_settings()

try:
    bot = Bot(token=BOT_TOKEN)
except Exception as exc:
    raise SystemExit(f"Проверьте BOT_TOKEN в .env: {exc}") from exc

dp = Dispatcher()
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


def clip(text: str, limit: int = 3500) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def sender_label(message: Message) -> str:
    user = message.from_user
    if user is None:
        return "неизвестный пользователь"
    if user.username:
        return f"@{user.username}"
    full_name = " ".join(
        part for part in (user.first_name, user.last_name) if part
    ).strip()
    return full_name or "без username"


async def ask_model(user_id: int, text: str) -> str:
    async with history_locks[user_id]:
        history = histories[user_id]
        history.append({"role": "user", "content": text})
        try:
            response = await openai_client.chat.completions.create(
                model=MODEL,
                temperature=0.4,
                max_tokens=400,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    *history,
                ],
            )
        except Exception:
            history.pop()
            raise
        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            answer = (
                "Не удалось сформулировать ответ. Напишите вопрос ещё раз "
                "или дождитесь менеджера."
            )
        history.append({"role": "assistant", "content": answer})
        return answer


async def notify_admin(message: Message) -> None:
    user = message.from_user
    if user is None:
        return
    body = message.text or message.caption or "[сообщение без текста]"
    text = (
        "📩 Новое обращение\n"
        f"От: {sender_label(message)} (ID: {user.id})\n"
        f"Текст: {clip(body)}"
    )
    try:
        await message.bot.send_message(ADMIN_ID, text)
        if message.content_type != "text":
            await message.copy_to(ADMIN_ID)
    except Exception:
        logger.exception("Не удалось переслать обращение %s менеджеру", user.id)


@dp.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME_TEXT, reply_markup=OPEN_KEYBOARD)


@dp.message(F.reply_to_message, F.from_user.id == ADMIN_ID)
async def admin_reply(message: Message) -> None:
    replied = message.reply_to_message
    raw = (replied.text or replied.caption or "") if replied else ""
    match = USER_ID_RE.search(raw)
    if not match:
        await message.answer(
            "Не вижу ID клиента. Нажмите «Ответить» на сообщении "
            "«📩 Новое обращение»."
        )
        return

    user_id = int(match.group(1))
    try:
        if message.text:
            await message.bot.send_message(user_id, message.text)
            async with history_locks[user_id]:
                histories[user_id].append(
                    {"role": "assistant", "content": message.text}
                )
        else:
            await message.copy_to(user_id)
    except Exception:
        logger.exception("Не удалось доставить ответ клиенту %s", user_id)
        await message.answer(
            "Не удалось отправить. Клиент мог заблокировать бота "
            "или ещё не открывал этот чат."
        )
        return

    await message.answer("✅ Отправлено")


@dp.message(F.from_user.id == ADMIN_ID, F.chat.type == "private")
async def admin_note(message: Message) -> None:
    await message.answer(
        "Чтобы ответить клиенту, нажмите «Ответить» на сообщении "
        "«📩 Новое обращение» и отправьте текст."
    )


@dp.message(F.chat.type == "private")
async def user_message(message: Message) -> None:
    user = message.from_user
    if user is None or user.is_bot:
        return

    await notify_admin(message)

    if not message.text:
        await message.answer(
            "Передал сообщение менеджеру. Если нужно пояснение, "
            "допишите его обычным текстом."
        )
        return

    await message.bot.send_chat_action(message.chat.id, "typing")
    try:
        answer = await ask_model(user.id, message.text)
    except Exception:
        logger.exception("Ошибка OpenAI для пользователя %s", user.id)
        answer = (
            "Сейчас не получилось подготовить ответ. "
            "Я передал обращение менеджеру, он посмотрит сообщение."
        )
    await message.answer(answer)


async def main() -> None:
    logger.info("Бот поддержки GenScore AI запущен. Админ: %s", ADMIN_ID)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
