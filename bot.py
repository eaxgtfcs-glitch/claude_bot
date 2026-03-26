import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode, ChatAction

import config

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler(open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)),
    ],
)
logger = logging.getLogger(__name__)

# Текущая рабочая директория для Claude (можно менять командой /cd)
current_workdir: dict[int, str] = {}

# Активные задачи (chat_id -> subprocess)
active_tasks: dict[int, asyncio.subprocess.Process] = {}


def check_access(user_id: int) -> bool:
    """Проверяет есть ли доступ у пользователя."""
    if not config.ALLOWED_USER_IDS:
        logger.warning("ALLOWED_USER_IDS не задан — доступ открыт для всех!")
        return True
    return user_id in config.ALLOWED_USER_IDS


def get_workdir(chat_id: int) -> str:
    """Возвращает текущую рабочую директорию для чата."""
    return current_workdir.get(chat_id, config.WORKSPACE_DIR)


def split_message(text: str, max_length: int = config.TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """Разбивает длинный текст на части для Telegram."""
    if len(text) <= max_length:
        return [text]

    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break
        # Ищем ближайший перенос строки для красивого разбиения
        split_at = text.rfind("\n", 0, max_length)
        if split_at == -1:
            split_at = max_length
        parts.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return parts


async def send_long_message(update: Update, text: str, parse_mode: str = None):
    """Отправляет сообщение, разбивая его если оно слишком длинное."""
    parts = split_message(text)
    for i, part in enumerate(parts):
        if not part.strip():
            continue
        try:
            await update.message.reply_text(
                part,
                parse_mode=parse_mode,
            )
        except Exception:
            # Если не получилось с разметкой — отправить plain text
            await update.message.reply_text(part)


async def run_claude(prompt: str, workdir: str, timeout: int = config.CLAUDE_TIMEOUT) -> tuple[str, bool]:
    """
    Запускает Claude Code и возвращает (output, success).
    Использует --print для неинтерактивного режима.
    """
    env = os.environ.copy()
    if config.ANTHROPIC_API_KEY:
        env["ANTHROPIC_API_KEY"] = config.ANTHROPIC_API_KEY
    # Если API ключа нет — Claude использует credentials из ~/.claude/.credentials.json (подписка)
    # Отключаем интерактивные подсказки
    env["CLAUDE_CODE_AUTO_APPROVE"] = "true"

    cmd = [
        "claude",
        "--print",               # неинтерактивный режим, вывод в stdout
        "--dangerously-skip-permissions",  # auto-approve всех действий
        prompt,
    ]

    logger.info(f"Запуск Claude в {workdir}: {prompt[:100]}...")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
            env=env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            return f"Превышено время ожидания ({timeout}s). Задача отменена.", False

        output = stdout.decode("utf-8", errors="replace").strip()
        error = stderr.decode("utf-8", errors="replace").strip()

        if process.returncode == 0:
            return output or "Задача выполнена (нет вывода).", True
        else:
            result = output
            if error:
                result += f"\n\nSTDERR:\n{error}"
            return result or f"Ошибка (код {process.returncode})", False

    except FileNotFoundError:
        return "Ошибка: команда `claude` не найдена. Проверьте установку Claude Code.", False
    except Exception as e:
        logger.error(f"Ошибка запуска Claude: {e}", exc_info=True)
        return f"Внутренняя ошибка: {e}", False


# ─── Handlers ───────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие."""
    user = update.effective_user
    if not check_access(user.id):
        await update.message.reply_text("Доступ запрещён.")
        return

    workdir = get_workdir(update.effective_chat.id)
    text = (
        f"Привет, {user.first_name}!\n\n"
        f"Я — интерфейс к Claude Code.\n"
        f"Рабочая папка: `{workdir}`\n\n"
        f"Просто напиши задачу и я её выполню.\n\n"
        f"Команды:\n"
        f"/start — это сообщение\n"
        f"/pwd — текущая директория\n"
        f"/cd <path> — сменить директорию\n"
        f"/ls — список файлов\n"
        f"/git <args> — выполнить git команду\n"
        f"/shell <cmd> — выполнить shell команду\n"
        f"/cancel — отменить текущую задачу\n"
        f"/help — помощь"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь."""
    if not check_access(update.effective_user.id):
        return

    text = (
        "*Примеры команд:*\n\n"
        "• `создай FastAPI приложение с эндпоинтом /health`\n"
        "• `добавь тесты для модуля auth.py`\n"
        "• `найди все баги в app.py и исправь их`\n"
        "• `задеплой приложение через docker-compose`\n"
        "• `закоммить все изменения с сообщением 'fix: auth bug'`\n"
        "• `запусти тесты и покажи результат`\n\n"
        "*Системные команды:*\n"
        "• `/cd /path/to/project` — сменить рабочую папку\n"
        "• `/shell docker ps` — выполнить shell команду\n"
        "• `/git log --oneline -5` — git команды\n"
        "• `/cancel` — отменить задачу\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def pwd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать текущую директорию."""
    if not check_access(update.effective_user.id):
        return
    workdir = get_workdir(update.effective_chat.id)
    await update.message.reply_text(f"Текущая директория:\n`{workdir}`", parse_mode=ParseMode.MARKDOWN)


async def cd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сменить рабочую директорию."""
    if not check_access(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Использование: `/cd /path/to/dir`", parse_mode=ParseMode.MARKDOWN)
        return

    new_path = " ".join(context.args)
    expanded = os.path.expanduser(new_path)

    if not os.path.isdir(expanded):
        await update.message.reply_text(f"Директория не существует: `{expanded}`", parse_mode=ParseMode.MARKDOWN)
        return

    current_workdir[update.effective_chat.id] = expanded
    await update.message.reply_text(f"Рабочая директория изменена:\n`{expanded}`", parse_mode=ParseMode.MARKDOWN)


async def ls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список файлов."""
    if not check_access(update.effective_user.id):
        return

    workdir = get_workdir(update.effective_chat.id)
    try:
        result = subprocess.run(
            ["ls", "-la"],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout or result.stderr or "Пусто"
        await send_long_message(update, f"```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


async def shell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполнить произвольную shell команду."""
    if not check_access(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Использование: `/shell <команда>`", parse_mode=ParseMode.MARKDOWN)
        return

    cmd = " ".join(context.args)
    workdir = get_workdir(update.effective_chat.id)

    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout + result.stderr
        if not output.strip():
            output = f"Выполнено (код {result.returncode})"
        await send_long_message(update, f"```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)
    except subprocess.TimeoutExpired:
        await update.message.reply_text("Таймаут команды (60s)")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


async def git_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполнить git команду."""
    if not check_access(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Использование: `/git <args>`", parse_mode=ParseMode.MARKDOWN)
        return

    args = context.args
    workdir = get_workdir(update.effective_chat.id)

    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        if not output.strip():
            output = "Выполнено."
        await send_long_message(update, f"```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменить текущую задачу."""
    if not check_access(update.effective_user.id):
        return

    chat_id = update.effective_chat.id
    if chat_id in active_tasks:
        active_tasks[chat_id].kill()
        del active_tasks[chat_id]
        await update.message.reply_text("Задача отменена.")
    else:
        await update.message.reply_text("Нет активных задач.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основной обработчик сообщений — отправляет задачу в Claude."""
    user = update.effective_user
    if not check_access(user.id):
        await update.message.reply_text("Доступ запрещён.")
        return

    prompt = update.message.text.strip()
    if not prompt:
        return

    chat_id = update.effective_chat.id
    workdir = get_workdir(chat_id)

    # Показываем что работаем
    await update.message.chat.send_action(ChatAction.TYPING)
    status_msg = await update.message.reply_text(
        f"Выполняю задачу...\nДиректория: `{workdir}`",
        parse_mode=ParseMode.MARKDOWN,
    )

    start_time = datetime.now()

    # Запускаем Claude
    output, success = await run_claude(prompt, workdir)

    elapsed = (datetime.now() - start_time).seconds

    # Удаляем статус-сообщение
    try:
        await status_msg.delete()
    except Exception:
        pass

    # Формируем заголовок ответа
    status_icon = "✅" if success else "❌"
    header = f"{status_icon} Готово за {elapsed}s\n\n"

    # Отправляем результат
    full_output = header + output
    await send_long_message(update, full_output)

    logger.info(
        f"User {user.id} (@{user.username}): '{prompt[:60]}' → "
        f"{'OK' if success else 'FAIL'} ({elapsed}s)"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок."""
    logger.error("Исключение при обработке обновления:", exc_info=context.error)


def main():
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN не задан в .env файле!")
        sys.exit(1)

    if not config.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY не задан — ожидается аутентификация через claude.ai подписку")

    # Убедиться что workspace существует
    Path(config.WORKSPACE_DIR).mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(exist_ok=True)

    logger.info("Запуск бота...")
    logger.info(f"Разрешённые пользователи: {config.ALLOWED_USER_IDS}")
    logger.info(f"Workspace: {config.WORKSPACE_DIR}")

    app = Application.builder().token(config.BOT_TOKEN).build()

    # Регистрация handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("pwd", pwd_command))
    app.add_handler(CommandHandler("cd", cd_command))
    app.add_handler(CommandHandler("ls", ls_command))
    app.add_handler(CommandHandler("shell", shell_command))
    app.add_handler(CommandHandler("git", git_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    logger.info("Бот запущен. Ожидаю сообщения...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
