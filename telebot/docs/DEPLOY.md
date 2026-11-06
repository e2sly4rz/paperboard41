
---

## `docs/DEPLOY.md` — развёртывание

```markdown
# Развёртывание

## Требования

- Ubuntu 22.04 / 24.04
- Python 3.13
- systemd
- SQLite

## Установка

### 1. Система

```bash
sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-dev git sqlite3
sudo locale-gen ru_RU.UTF-8
```

### 2. Пользователь и код

```bash
sudo adduser bot
su - bot
git clone <репозиторий> /home/bot/telebot
cd /home/bot/telebot
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Конфигурация

```bash
cp .env.example .env
nano .env
```

### 4. Systemd

/etc/systemd/system/club-bot.service:

```
[Unit]
Description=Telegram Club Bot
After=network.target

[Service]
Type=simple
User=bot
Group=bot
WorkingDirectory=/home/bot/telebot
Environment="LANG=ru_RU.UTF-8" "LC_ALL=ru_RU.UTF-8"
EnvironmentFile=/home/bot/telebot/.env
ExecStart=/home/bot/telebot/venv/bin/python /home/bot/telebot/main.py
Restart=always
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Критично: строка Environment="LANG=..." обязательна, иначе SimpleCalendar упадёт с locale.Error.

sudo systemctl daemon-reload
sudo systemctl enable club-bot
sudo systemctl start club-bot
sudo journalctl -u club-bot -f

Обновление

cd /home/bot/telebot
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart club-bot

Резервное копирование

sqlite3 /home/bot/telebot/club.db ".backup '/home/bot/backups/club_$(date +%F).db'"
gzip /home/bot/backups/club_*.db

Настроить в cron:

0 3 * * * /home/bot/backup.sh

Диагностика

```
# Логи
sudo journalctl -u club-bot -n 50

# Локаль в процессе
PID=$(systemctl show club-bot -p MainPID --value)
sudo cat /proc/$PID/environ | tr '\0' '\n' | grep -E 'LANG|LC_'

# Проверка кода
python -m pyflakes handlers/ database/ keyboards/ states/ middleware/ scheduler.py utils.py notifications.py main.py
python -m py_compile $(find . -name "*.py" -not -path "./venv/*" -not -path "*/__pycache__/*")

# Состояние БД
sqlite3 club.db ".tables"
sqlite3 club.db "PRAGMA table_info(game_sessions);"
sqlite3 club.db "SELECT DISTINCT subscriber_level FROM users;"
```

