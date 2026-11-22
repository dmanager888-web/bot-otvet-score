# Бот поддержки GenScore AI

Telegram-бот поддержки на Python: aiogram 3.x и OpenAI (`gpt-4o-mini`). Отвечает пользователям по сервису GenScore AI, дублирует обращения менеджеру и доставляет ответ менеджера клиенту.

## Что нужно

- Python 3.11 или новее. Если в PowerShell команда `python` открывает Microsoft Store, установите Python с [python.org](https://www.python.org/downloads/) и отметьте «Add python.exe to PATH»
- Токен этого бота от [@BotFather](https://t.me/BotFather)
- Ключ OpenAI с доступом к `gpt-4o-mini`
- Ваш числовой Telegram ID (его показывает [@userinfobot](https://t.me/userinfobot))

## Запуск

```bash
python -m venv .venv
```

Windows (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Откройте `.env` и подставьте свои значения:

```env
BOT_TOKEN=токен_от_BotFather
OPENAI_API_KEY=ключ_OpenAI
ADMIN_ID=ваш_числовой_telegram_id
```

Файл `.env` храните только локально. В репозиторий он не попадает: в `.gitignore` он уже исключён.

Запуск:

```bash
python bot.py
```

Перед первым обращением откройте бота поддержки со своего аккаунта менеджера и нажмите `/start`. Иначе Telegram не даст боту написать вам в личку.

## Как устроены ответы

1. `/start` — приветствие поддержки GenScore AI и кнопка «🚀 Открыть GenScore AI» на https://t.me/GenScoreAi_bot.
2. Текстовое сообщение пользователя уходит в `gpt-4o-mini`. Для каждого `user_id` бот помнит последние 6 сообщений диалога.
3. Каждое входящее обращение копируется вам в личку:

```text
📩 Новое обращение
От: @username (ID: user_id)
Текст: ...
```

4. Чтобы ответить клиенту, нажмите «Ответить» на этом сообщении и отправьте текст. Бот доставит его пользователю и пришлёт вам `✅ Отправлено`.

## GitHub + Railway (24/7)

Бот работает через **long polling** — отдельный веб-сервер не нужен. На Railway это один **worker**-процесс: `python bot.py`.

### 1. GitHub

Репозиторий не должен содержать `.env` (он в `.gitignore`).

```bash
cd "/Users/saydex/Desktop/curcor work"
git init -b main
git add .
git commit -m "GenScore AI support bot"
gh auth login
gh repo create genscore-support-bot --private --source=. --remote=origin --push
```

Имя репозитория можно заменить на своё. Если `gh` недоступен: создайте пустой репозиторий на [github.com/new](https://github.com/new), затем:

```bash
git remote add origin https://github.com/ВАШ_ЛОГИН/ИМЯ_РЕПО.git
git push -u origin main
```

### 2. Railway

1. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo** → выберите репозиторий.
2. **Variables** (обязательно, те же имена, что в `.env.example`):

   | Переменная | Значение |
   |------------|----------|
   | `BOT_TOKEN` | токен от @BotFather |
   | `OPENAI_API_KEY` | ключ OpenAI (`sk-...`) |
   | `ADMIN_ID` | только цифры, ваш Telegram ID |

3. У сервиса должна быть команда запуска **`python bot.py`** (уже в `railway.toml` и `Procfile`).
4. **Deploy** → в логах: `Бот поддержки GenScore AI запущен`.

Не поднимайте **второй** экземпляр с тем же `BOT_TOKEN` (локально и на Railway одновременно) — Telegram отдаст конфликт polling.

### 3. Проверка

- Напишите боту в Telegram → должен ответить.
- У менеджера в личку придёт `📩 Новое обращение`.
- Менеджер один раз нажимает `/start` у бота поддержки, иначе уведомления в личку не дойдут.
