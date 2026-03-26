# Деплой Claude Telegram Bot на сервер

## Что получится в итоге

Telegram бот на VPS, через который ты общаешься с Claude Code.
Пишешь задачу в Telegram → Claude выполняет её на сервере → отвечает результатом.

---

## Требования к серверу

- Ubuntu 22.04 / 24.04 (или Debian 12)
- 1 CPU, 1 GB RAM минимум (рекомендую 2 GB)
- Docker + Docker Compose
- Доступ по SSH

---

## Шаг 1 — Подключись к серверу

```bash
ssh user@IP_СЕРВЕРА
```

---

## Шаг 2 — Установи Docker

```bash
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER
newgrp docker
```

Проверь:

```bash
docker --version
docker compose version
```

---

## Шаг 3 — Скопируй проект на сервер

С локальной машины:

```bash
scp -r /путь/к/claude_bot user@IP_СЕРВЕРА:~/claude_bot
```

Или через git если проект в репозитории:

```bash
git clone https://github.com/ВАШ_РЕПО/claude_bot.git ~/claude_bot
```

---

## Шаг 4 — Создай .env на сервере

```bash
cd ~/claude_bot
cp .env.example .env
nano .env
```

Заполни:

```
BOT_TOKEN=токен_от_BotFather
ALLOWED_USER_IDS=твой_telegram_id
WORKSPACE_DIR=./workspace
CLAUDE_TIMEOUT=300
```

Сохрани: `Ctrl+O`, `Enter`, `Ctrl+X`

Закрой права:

```bash
chmod 600 .env
```

---

## Шаг 5 — Аутентификация Claude

Выбери один вариант.

### Вариант A: API ключ — проще для сервера (рекомендую)

Получи ключ на [console.anthropic.com](https://console.anthropic.com) → API Keys → Create Key.

Добавь в `.env`:

```
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxx
```

В `docker-compose.yml` закомментируй строку с credentials:

```bash
nano docker-compose.yml
```

```yaml
# - ${CLAUDE_CREDENTIALS_PATH:-~/.claude}:/root/.claude:ro
```

---

### Вариант B: подписка claude.ai (Pro/Max)

Сервер headless — браузера нет, поэтому логинимся **локально**, потом копируем credentials.

**На своей локальной машине:**

```bash
claude auth login
# Откроется браузер → войти → разрешить доступ
```

**Скопировать credentials на сервер:**

```bash
scp -r ~/.claude user@IP_СЕРВЕРА:~/.claude
```

**На сервере** убедись что файл на месте:

```bash
cat ~/.claude/.credentials.json
```

В `docker-compose.yml` строка монтирования должна быть активна:

```yaml
- ${CLAUDE_CREDENTIALS_PATH:-~/.claude}:/root/.claude:ro
```

> Если сессия протухнет — повтори `scp` с локальной машины и перезапусти контейнер.

---

## Шаг 6 — Запусти бота

```bash
cd ~/claude_bot
docker compose up -d --build
```

Первый запуск 3–5 минут (устанавливается Node.js и Claude Code CLI).

---

## Шаг 7 — Проверь

```bash
# Логи — должно быть "Application started"
docker compose logs -f

# Проверить что Claude работает внутри контейнера
docker exec claude-telegram-bot claude --print "скажи привет"
```

Напиши боту `/start` в Telegram — должен ответить.

---

## Шаг 8 — Автозапуск при перезагрузке сервера

В `docker-compose.yml` уже прописан `restart: unless-stopped` — контейнер запустится автоматически после ребута сервера.

Проверить:

```bash
sudo reboot
# подождать минуту, потом:
ssh user@IP_СЕРВЕРА
docker ps   # бот должен быть в статусе Up
```

---

## Управление ботом

```bash
# Логи
docker compose logs -f

# Остановить
docker compose down

# Перезапустить
docker compose restart

# Пересобрать после изменений кода
docker compose up -d --build

# Зайти внутрь контейнера
docker exec -it claude-telegram-bot bash
```

---

## Работа с проектами через бота

По умолчанию Claude работает в папке `workspace/` внутри контейнера.
Она смонтирована в `~/claude_bot/workspace/` на сервере.

**Сменить рабочую папку** — если хочешь чтобы Claude работал с конкретным проектом:

```
/cd /app/workspace/my-project
```

Или смонтируй свой проект в `docker-compose.yml`:

```yaml
volumes:
  - /home/user/my-project:/app/workspace/my-project
```

---

## Безопасность

- `ALLOWED_USER_IDS` — обязательно укажи свой ID, иначе бот открыт всем
- `.env` закрыт через `chmod 600`
- Бот не слушает никакие порты — использует polling, не webhook
- Credentials API ключа хранятся только в `.env`, не в образе

---

## Обновление бота

```bash
cd ~/claude_bot

# Если используешь git:
git pull

# Пересобрать и перезапустить:
docker compose up -d --build
```

---

## Диагностика проблем

**Бот не отвечает:**
```bash
docker compose logs --tail=50
```

**Claude не найден внутри контейнера:**
```bash
docker exec claude-telegram-bot which claude
docker exec claude-telegram-bot claude --version
```

**Ошибка аутентификации Claude:**
```bash
docker exec claude-telegram-bot claude auth status
```
При ошибке — обнови credentials (Шаг 5, Вариант B) или проверь API ключ.

**Контейнер падает и перезапускается:**
```bash
docker compose logs --tail=100
```
