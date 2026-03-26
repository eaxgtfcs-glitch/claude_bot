# Запуск Claude Telegram Bot в Docker

## Требования

- Docker Desktop установлен и запущен
- Заполнен файл `.env` (скопируй из `.env.example` если ещё нет)
- Есть аутентификация Claude — подписка claude.ai **или** API ключ

---

## Шаг 1 — Выбери способ аутентификации

### Вариант A: подписка claude.ai (Pro/Max) — без API ключа

Убедись что на этой машине ты залогинен в Claude Code:

```bash
claude auth status
```

Если не залогинен — войди:

```bash
claude auth login
```

Credentials хранятся в `~/.claude/` — они будут смонтированы в контейнер автоматически.
В `.env` строка `ANTHROPIC_API_KEY` должна быть закомментирована или отсутствовать.

---

## Шаг 2 — Собери и запусти

```bash
docker compose up -d --build
```

Первый запуск занимает 2–5 минут — скачивается Node.js и устанавливается Claude Code CLI.

---

## Шаг 3 — Проверь что бот запустился

```bash
docker compose logs -f
```

Должно быть видно:

```
claude-telegram-bot  | Application started
```

Напиши своему боту в Telegram `/start` — должен ответить.

---

## Шаг 4 — Проверь что Claude работает внутри контейнера

```bash
docker exec claude-telegram-bot claude --print "скажи привет"
```

Если ответил — всё работает.

---

## Управление ботом

```bash
# Посмотреть логи
docker compose logs -f

# Остановить
docker compose down

# Перезапустить
docker compose restart

# Пересобрать после изменений кода
docker compose up -d --build
```

---

## Примечание для Windows

Если запускаешь команды в **CMD или PowerShell** (не WSL/Git Bash), путь `~/.claude` не разворачивается автоматически.
Укажи полный путь явно перед командой:

```powershell
$env:CLAUDE_CREDENTIALS_PATH="C:\Users\ИМЯ_ПОЛЬЗОВАТЕЛЯ\.claude"
docker compose up -d --build
```

Или пропиши `CLAUDE_CREDENTIALS_PATH` прямо в `.env`:

```
CLAUDE_CREDENTIALS_PATH=C:\Users\ИМЯ_ПОЛЬЗОВАТЕЛЯ\.claude
```

---

## Если сессия claude.ai протухла

Просто перелогинься на хосте — перезапускать контейнер не нужно:

```bash
claude auth login
```

Credentials читаются с хоста в реальном времени через volume mount.

---

## Структура проекта

```
claude_bot/
├── bot.py              # код бота
├── config.py           # конфигурация
├── Dockerfile          # образ Docker
├── docker-compose.yml  # оркестрация
├── requirements.txt    # Python зависимости
├── .env                # секреты (не в git!)
├── .env.example        # шаблон для .env
├── workspace/          # папка где Claude работает с кодом
└── logs/               # логи бота
```
