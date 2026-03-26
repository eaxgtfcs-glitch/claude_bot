FROM python:3.12-slim

# Устанавливаем Node.js 20 (нужен для Claude Code CLI)
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Создаём непривилегированного пользователя
# Claude Code запрещает --dangerously-skip-permissions от root
RUN useradd -m -s /bin/bash botuser

# Устанавливаем Claude Code CLI глобально (от root, чтобы было в PATH)
RUN npm install -g @anthropic-ai/claude-code

# Рабочая директория приложения
WORKDIR /app

# Устанавливаем Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бота
COPY bot.py config.py ./

# Создаём нужные папки и передаём владение пользователю
RUN mkdir -p workspace logs && chown -R botuser:botuser /app

# Переключаемся на непривилегированного пользователя
USER botuser

# Запуск
CMD ["python", "bot.py"]
