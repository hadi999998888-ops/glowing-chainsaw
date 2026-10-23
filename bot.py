import json
import os
import secrets
import logging
import html

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ==================================================
# НАСТРОЙКИ — ВСТАВЬ СВОЙ ТОКЕН
# ==================================================

TOKEN = "8757046363:AAH_sxbGCELk5divmluJVWCIrWuiTygmGzo"

ADMIN_ID = 7608889836

CHANNEL_ID = -1003957801744
CHANNEL_URL = "https://t.me/ExtraCheatStanddof2"

# ID группы, в которой находятся комментарии канала.
# Сюда нужно вставить ID привязанного чата обсуждений.
DISCUSSION_CHAT_ID = 0

BOT_USERNAME = "ExtraCheatbot"

DB_FILE = "posts.json"

DISCUSSION_TEXT = (
    "🐍Получай читы переходя\n"
    f"в бот @{BOT_USERNAME} по ссылке в посте\n\n"
    "• не какого скама\n"
    "• чистые читы\n"
    "• проверенные"
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)


# ==================================================
# ХРАНЕНИЕ ПОСТОВ
# ==================================================

def load_posts():
    if not os.path.exists(DB_FILE):
        return {}

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        log.exception("Не удалось прочитать базу постов")
        return {}


posts = load_posts()
states = {}


def save_posts():
    temp_file = DB_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    os.replace(temp_file, DB_FILE)


# ==================================================
# КЛАВИАТУРЫ
# ==================================================

def admin_keyboard():
    return ReplyKeyboardMarkup(
        [["⚙️ Админ-панель"]],
        resize_keyboard=True,
    )


def panel_keyboard():
    return ReplyKeyboardMarkup(
        [["Создать Пост"], ["Выйти"]],
        resize_keyboard=True,
    )


def channel_keyboard(post_id=None):
    buttons = [
        [
            InlineKeyboardButton(
                "🐍 Наш канал",
                url=CHANNEL_URL,
            )
        ]
    ]

    if post_id:
        buttons.append(
            [
                InlineKeyboardButton(
                    "✅ Проверить подписку",
                    callback_data=f"check:{post_id}",
                )
            ]
        )

    return InlineKeyboardMarkup(buttons)


# ==================================================
# ПРОВЕРКА ПОДПИСКИ
# ==================================================

async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL_ID,
            user_id=user_id,
        )

        if member.status in ("creator", "administrator", "member"):
            return True

        if member.status == "restricted":
            return bool(getattr(member, "is_member", False))

        return False

    except Exception:
        log.exception("Ошибка проверки подписки")
        return False


# ==================================================
# СОЗДАНИЕ ПОСТА
# ==================================================

def get_material_type(message):
    if message.photo:
        return "photo"
    if message.video:
        return "video"
    if message.document:
        return "document"
    if message.animation:
        return "animation"
    if message.audio:
        return "audio"
    if message.voice:
        return "voice"
    if message.video_note:
        return "video_note"
    if message.sticker:
        return "sticker"
    if message.text is not None:
        return "text"

    return "other"


async def send_material_with_description(
    bot,
    chat_id,
    post,
    include_description=True,
):
    material_type = post["type"]
    source_chat_id = post["source_chat_id"]
    source_message_id = post["source_message_id"]

    description = post.get("description", "")

    # Стикеры и видеокружки не поддерживают подпись.
    # Для них Telegram требует отдельное сообщение с описанием.
    if material_type in ("sticker", "video_note", "other"):
        await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=source_chat_id,
            message_id=source_message_id,
        )

        if include_description:
            await bot.send_message(
                chat_id=chat_id,
                text=description,
                reply_markup=channel_keyboard(),
            )
        return

    # Текстовый материал и описание отправляем одним сообщением.
    if material_type == "text":
        combined_text = post.get("original_text", "")

        if include_description and description:
            combined_text += "\n\n" + description

        await bot.send_message(
            chat_id=chat_id,
            text=combined_text or "Материал",
            reply_markup=channel_keyboard(),
        )
        return

    # Для фото, видео, файлов и других медиа используем подпись.
    caption = post.get("original_caption", "")

    if include_description and description:
        caption = (
            caption + "\n\n" + description
            if caption
            else description
        )

    await bot.copy_message(
        chat_id=chat_id,
        from_chat_id=source_chat_id,
        message_id=source_message_id,
        caption=caption or None,
        reply_markup=channel_keyboard(),
    )


# ==================================================
# ВЫДАЧА ПОСТА ПО ССЫЛКЕ
# ==================================================

async def deliver_post(bot, chat_id, post_id):
    post = posts.get(post_id)

    if not post:
        await bot.send_message(
            chat_id,
            "❌ Этот пост не найден.",
        )
        return

    try:
        await send_material_with_description(
            bot,
            chat_id,
            post,
            include_description=True,
        )

    except Exception:
        log.exception("Не удалось выдать пост %s", post_id)

        await bot.send_message(
            chat_id,
            "❌ Не получилось отправить материал. "
            "Попробуй позже.",
        )


# ==================================================
# START
# ==================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message

    if not user or not message:
        return

    args = context.args

    if user.id == ADMIN_ID and not args:
        states.pop(user.id, None)

        await message.reply_text(
            "⚙️ Добро пожаловать в панель администратора.",
            reply_markup=admin_keyboard(),
        )
        return

    if not args:
        keyboard = (
            admin_keyboard()
            if user.id == ADMIN_ID
            else None
        )

        await message.reply_text(
            "🐍Этот бот предназначен\n"
            "для того чтобы получать читы\n"
            "прошу перейти в наш канал",
            reply_markup=keyboard,
        )

        await message.reply_text(
            "🐍 Наш канал",
            reply_markup=InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton(
                        "🐍 Наш канал",
                        url=CHANNEL_URL,
                    )
                ]]
            ),
        )
        return

    post_id = args[0]

    if not post_id.startswith("post_"):
        await message.reply_text("❌ Неверная ссылка.")
        return

    post_id = post_id[5:]

    if post_id not in posts:
        await message.reply_text(
            "❌ Пост не найден или ссылка устарела."
        )
        return

    if not await is_subscribed(context.bot, user.id):
        await message.reply_text(
            "🔒 Для получения материала подпишись на канал.",
            reply_markup=channel_keyboard(post_id),
        )
        return

    await deliver_post(
        context.bot,
        message.chat_id,
        post_id,
    )


# ==================================================
# АДМИН-ПАНЕЛЬ И СОЗДАНИЕ ПОСТА
# ==================================================

async def handle_admin_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message

    if not user or not message:
        return

    # Только администратор может пользоваться панелью.
    if user.id != ADMIN_ID:
        return

    text = message.text or ""

    if text == "⚙️ Админ-панель":
        states.pop(user.id, None)

        await message.reply_text(
            "⚙️ Админ-панель",
            reply_markup=panel_keyboard(),
        )
        return

    if text == "Выйти":
        states.pop(user.id, None)

        await message.reply_text(
            "Ты вышел из панели.",
            reply_markup=admin_keyboard(),
        )
        return

    if text == "Создать Пост":
        states[user.id] = {"step": "material"}

        await message.reply_text(
            "📦 Создание поста\n\n"
            "Отправь фото, видео, документ, аудио, "
            "анимацию или текст.\n\n"
            "Отправленное сообщение станет материалом поста."
        )
        return

    state = states.get(user.id)

    if not state:
        return

    if state["step"] == "material":
        if message.text and message.text.startswith("/"):
            return

        material_type = get_material_type(message)

        state["source_chat_id"] = message.chat_id
        state["source_message_id"] = message.message_id
        state["type"] = material_type
        state["original_caption"] = message.caption or ""
        state["original_text"] = message.text or ""
        state["step"] = "description"

        await message.reply_text(
            "✅ Материал принят.\n\n"
            "Теперь отправь описание.\n"
            "Оно будет добавлено к материалу, "
            "а не отдельным сообщением, если тип материала "
            "поддерживает подпись."
        )
        return

    if state["step"] == "description":
        if message.text is None:
            await message.reply_text(
                "❌ Отправь описание текстовым сообщением."
            )
            return

        state["description"] = message.text
        state["step"] = "confirm"

        await message.reply_text(
            "📝 Описание сохранено.\n\n"
            "Нажми «Сгенерировать», чтобы создать ссылку.",
            reply_markup=InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton(
                        "🔗 Сгенерировать",
                        callback_data="generate",
                    )
                ]]
            ),
        )


# ==================================================
# ОБРАБОТКА КНОПОК
# ==================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    data = query.data or ""

    if data == "generate":
        if user.id != ADMIN_ID:
            await query.answer(
                "Нет доступа.",
                show_alert=True,
            )
            return

        state = states.get(user.id)

        if not state or state.get("step") != "confirm":
            await query.message.reply_text(
                "❌ Создание поста не найдено. Начни заново."
            )
            return

        post_id = secrets.token_urlsafe(8)

        posts[post_id] = {
            "source_chat_id": state["source_chat_id"],
            "source_message_id": state["source_message_id"],
            "type": state["type"],
            "original_caption": state.get("original_caption", ""),
            "original_text": state.get("original_text", ""),
            "description": state.get("description", ""),
        }

        try:
            save_posts()
        except OSError:
            posts.pop(post_id, None)
            log.exception("Ошибка сохранения базы")
            await query.message.reply_text(
                "❌ Не удалось сохранить пост. Проверь память устройства."
            )
            return

        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start=post_{post_id}"

        states.pop(user.id, None)

        await query.message.reply_text(
            "✅ ПОСТ УСПЕШНО СОЗДАН\n\n"
            f"🔗 Ссылка:\n{link}\n\n"
            "Отправь её игрокам.",
            reply_markup=InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton(
                        "📎 Открыть ссылку",
                        url=link,
                    )
                ]]
            ),
        )

        await query.message.reply_text(
            "Что дальше?",
            reply_markup=panel_keyboard(),
        )
        return

    if data.startswith("check:"):
        post_id = data[len("check:"):]

        if post_id not in posts:
            await query.message.reply_text(
                "❌ Пост не найден."
            )
            return

        if not await is_subscribed(context.bot, user.id):
            await query.answer(
                "Сначала подпишись на канал!",
                show_alert=True,
            )
            return

        await query.message.reply_text(
            "✅ Подписка подтверждена!"
        )

        await deliver_post(
            context.bot,
            query.message.chat_id,
            post_id,
        )


# ==================================================
# АВТООТВЕТ НА ПОСТ В ЧАТЕ ОБСУЖДЕНИЙ
# ==================================================

async def discussion_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    if DISCUSSION_CHAT_ID == 0:
        return

    if message.chat_id != DISCUSSION_CHAT_ID:
        return

    # Telegram автоматически пересылает публикации канала
    # в привязанный чат обсуждений.
    if not getattr(message, "is_automatic_forward", False):
        return

    # Не отвечаем на обычные сообщения пользователей.
    if not message.sender_chat:
        return

    if message.sender_chat.id != CHANNEL_ID:
        return

    try:
        await context.bot.send_message(
            chat_id=message.chat_id,
            text=DISCUSSION_TEXT,
            reply_parameters={
                "message_id": message.message_id,
                "allow_sending_without_reply": True,
            },
            disable_web_page_preview=True,
        )

        log.info(
            "Ответ опубликован на пост %s",
            message.message_id,
        )

    except Exception:
        log.exception("Не удалось ответить на пост канала")


# ==================================================
# ОШИБКИ
# ==================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    log.error(
        "Ошибка обработки обновления",
        exc_info=context.error,
    )


# ==================================================
# ЗАПУСК
# ==================================================

def main():
    if TOKEN == "ВСТАВЬ_ТОКЕН_ОТ_BOTFATHER" or not TOKEN.strip():
        print("❌ Вставь токен в настройку TOKEN.")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        CallbackQueryHandler(button_handler)
    )

    # Обсуждения обрабатываем отдельно.
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & ~filters.StatusUpdate.ALL,
            discussion_handler,
        ),
        group=0,
    )

    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            handle_admin_message,
        ),
        group=1,
    )

    app.add_error_handler(error_handler)

    print("🐍 ExtraCheatBot запущен!")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
