
import json
import os
import secrets
import html

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ========== НАСТРОЙКИ ==========

TOKEN = "8757046363:AAH_sxbGCELk5divmluJVWCIrWuiTygmGzo"

ADMIN_ID = 7608889836
CHANNEL_ID = -1003957801744
CHANNEL_URL = "https://t.me/ExtraCheatStanddof2"

DB_FILE = "posts.json"

# ========== ХРАНИЛИЩЕ ==========

def load_posts():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

def save_posts():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

posts = load_posts()
states = {}

# ========== КЛАВИАТУРЫ ==========

def admin_keyboard():
    return ReplyKeyboardMarkup(
        [["⚙️ Админ-панель"]],
        resize_keyboard=True
    )

def panel_keyboard():
    return ReplyKeyboardMarkup(
        [["Создать Пост"], ["Выйти"]],
        resize_keyboard=True
    )

def channel_keyboard(post_id=None):
    buttons = [
        [InlineKeyboardButton(
            "🐍 Наш канал",
            url=CHANNEL_URL
        )]
    ]

    if post_id:
        buttons.append([
            InlineKeyboardButton(
                "✅ Проверить подписку",
                callback_data=f"check_{post_id}"
            )
        ])

    return InlineKeyboardMarkup(buttons)

# ========== ПРОВЕРКА ПОДПИСКИ ==========

async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL_ID,
            user_id=user_id
        )
        return (
            member.status in ("creator", "administrator", "member")
            or (
                member.status == "restricted"
                and getattr(member, "is_member", False)
            )
        )
    except Exception as e:
        print("Ошибка проверки подписки:", e)
        return False

# ========== START ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    if user.id == ADMIN_ID:
        if not args:
            states.pop(user.id, None)
            await update.message.reply_text(
                "⚙️ Админ-панель доступна ниже.",
                reply_markup=admin_keyboard()
            )
            return

    if not args:
        await update.message.reply_text(
            "🐍Этот бот предназначен\n"
            "для того чтобы получать читы\n"
            "прошу перейти в наш канал\n\n"
            f'🐍 <a href="{CHANNEL_URL}">Наш канал</a>',
            parse_mode="HTML",
            reply_markup=(
                admin_keyboard() if user.id == ADMIN_ID
                else None
            ),
            disable_web_page_preview=True
        )
        return

    post_id = args[0].removeprefix("post_")

    if post_id not in posts:
        await update.message.reply_text(
            "❌ Этот пост не найден или ссылка неправильная."
        )
        return

    if not await is_subscribed(context.bot, user.id):
        await update.message.reply_text(
            "🐍 Для получения файла сначала подпишись на наш канал!\n\n"
            f'<a href="{CHANNEL_URL}">🐍 Наш канал</a>\n\n'
            "После подписки нажми кнопку проверки.",
            parse_mode="HTML",
            reply_markup=channel_keyboard(post_id),
            disable_web_page_preview=True
        )
        return

    await deliver_post(
        context.bot,
        update.effective_chat.id,
        post_id
    )

# ========== ВЫДАЧА ПОСТА ==========

async def deliver_post(bot, chat_id, post_id):
    post = posts.get(post_id)

    if not post:
        await bot.send_message(
            chat_id,
            "❌ Пост больше не найден."
        )
        return

    try:
        # Копируем исходное сообщение администратора.
        await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=post["admin_chat_id"],
            message_id=post["message_id"]
        )

        description = html.escape(post["description"])

        text = (
            f"{description}\n\n"
            f'<a href="{CHANNEL_URL}">🐍наш канал</a>'
        )

        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=channel_keyboard(),
            disable_web_page_preview=True
        )

    except Exception as e:
        print("Ошибка выдачи поста:", e)
        await bot.send_message(
            chat_id,
            "❌ Не удалось отправить файл. "
            "Попробуй позже или сообщи администратору."
        )

# ========== АДМИНСКИЕ СООБЩЕНИЯ ==========

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    message = update.effective_message

    if not user or not message:
        return

    # Обычным пользователям меню администратора недоступно.
    if user.id != ADMIN_ID:
        return

    text = message.text or ""

    if text == "⚙️ Админ-панель":
        states.pop(user.id, None)
        await message.reply_text(
            "⚙️ Панель администратора",
            reply_markup=panel_keyboard()
        )
        return

    if text == "Выйти":
        states.pop(user.id, None)
        await message.reply_text(
            "Ты вышел из админ-панели.",
            reply_markup=admin_keyboard()
        )
        return

    if text == "Создать Пост":
        states[user.id] = {"step": "media"}
        await message.reply_text(
            "📦 Отправь сообщение для поста.\n\n"
            "Можно отправить фото, видео, файл, аудио, "
            "анимацию или обычный текст."
        )
        return

    state = states.get(user.id)

    if not state:
        return

    if state["step"] == "media":
        if message.text and message.text.startswith("/"):
            return

        state["admin_chat_id"] = message.chat_id
        state["message_id"] = message.message_id
        state["step"] = "description"

        await message.reply_text(
            "✅ Материал принят!\n\n"
            "Теперь отправь описание, которое будет "
            "показано под материалом."
        )
        return

    if state["step"] == "description":
        if not message.text:
            await message.reply_text(
                "❌ Отправь описание обычным текстовым сообщением."
            )
            return

        state["description"] = message.text
        state["step"] = "generate"

        await message.reply_text(
            "📝 Описание сохранено.\n\n"
            "Нажми кнопку, чтобы создать ссылку.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "🔗 Сгенерировать",
                    callback_data="generate_post"
                )
            ]])
        )

# ========== КНОПКИ ==========

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    data = query.data

    if data == "generate_post":
        if user.id != ADMIN_ID:
            await query.answer("Нет доступа.", show_alert=True)
            return

        state = states.get(user.id)

        if not state or state.get("step") != "generate":
            await query.message.reply_text(
                "❌ Сначала создай пост заново."
            )
            return

        post_id = secrets.token_urlsafe(8)

        posts[post_id] = {
            "admin_chat_id": state["admin_chat_id"],
            "message_id": state["message_id"],
            "description": state["description"]
        }
        save_posts()

        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start=post_{post_id}"

        states.pop(user.id, None)

        await query.message.reply_text(
            "✅ Пост создан!\n\n"
            "🔗 Ссылка для игроков:\n"
            f"{link}\n\n"
            "Отправляй эту ссылку пользователям.",
            reply_markup=panel_keyboard()
        )
        return

    if data.startswith("check_"):
        post_id = data[len("check_"):]

        if post_id not in posts:
            await query.message.reply_text(
                "❌ Пост не найден."
            )
            return

        if not await is_subscribed(context.bot, user.id):
            await query.answer(
                "Сначала подпишись на канал!",
                show_alert=True
            )
            return

        await query.message.reply_text(
            "✅ Подписка подтверждена! Отправляю материал..."
        )

        await deliver_post(
            context.bot,
            query.message.chat_id,
            post_id
        )

# ========== ЗАПУСК ==========

def main():
    if not TOKEN or TOKEN == "ВСТАВЬ_СЮДА_ТОКЕН_БОТА":
        print("❌ Сначала вставь токен бота в TOKEN!")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            handle_message
        )
    )

    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
