import os

# Токен получаем из переменной окружения, чтобы не коммитить его в репозиторий
BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")

# ID администратора клуба (может назначать хостов)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Путь к файлу базы данных
DB_PATH = os.getenv("DB_PATH", "club.db")