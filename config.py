import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Список Telegram user ID которым разрешён доступ
ALLOWED_USER_IDS = [
    int(uid.strip())
    for uid in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if uid.strip()
]

# Рабочая директория где Claude будет работать с кодом
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", os.path.expanduser("~/claude_telegram_bot/workspace"))

# Таймаут выполнения команды Claude (секунды)
CLAUDE_TIMEOUT = int(os.getenv("CLAUDE_TIMEOUT", "300"))

# Максимальная длина сообщения Telegram
TELEGRAM_MAX_MESSAGE_LENGTH = 4000
