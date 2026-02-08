# RepairCRM MVP

CRM система для управления ремонтами квартир с AI-агентом, интеграцией Авито и Telegram Mini App.

## Возможности

- 🤖 **AI-квалификация лидов** из Авито через OpenRouter
- 💬 **TG Userbot** с RAG (память компании) для общения с клиентами
- 📊 **Kanban-доска** с 5 статусами (Новый → Квалифицирован → Консультация → Договор → Ремонт)
- 📱 **Telegram Mini App** для мобильного управления
- 🎙️ **Транскрипция аудио** через OpenRouter Whisper
- 🔍 **Semantic search** по документам компании (pgvector)

## Технологии

- **Frontend**: Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui
- **Backend**: Prisma ORM + PostgreSQL + pgvector
- **Auth**: Telegram WebApp initData → JWT
- **AI**: OpenRouter (GPT-4 + Whisper) + n8n workflows
- **TG**: Telegram Bot API + Userbot (Telethon)

## Быстрый старт

### 1. Установка зависимостей

```bash
npm install
cd userbot && pip install -r requirements.txt && cd ..
```

### 2. Настройка окружения

Скопируйте `.env.example` в `.env` и заполните:

```bash
cp .env.example .env
```

Необходимые ключи:
- `TELEGRAM_BOT_TOKEN` - от @BotFather
- `OPENROUTER_API_KEY` - с openrouter.ai
- `JWT_SECRET` - случайная строка
- `TG_API_ID`, `TG_API_HASH` - с my.telegram.org (для userbot)

### 3. Запуск базы данных

```bash
docker-compose up -d
npx prisma migrate dev
```

### 4. Запуск приложения

```bash
# Frontend + API
npm run dev

# Userbot (в отдельном терминале)
cd userbot
python bot.py
```

Приложение доступно на `http://localhost:3000`

## Структура проекта

```
├── app/
│   ├── api/
│   │   ├── auth/verify/      # TG auth
│   │   ├── leads/            # CRUD лидов
│   │   ├── rag/              # RAG embeddings/query
│   │   └── avito/webhook/    # Авито интеграция
│   ├── dashboard/            # Kanban доска
│   ├── lead/[id]/            # Карточка лида
│   └── login/                # TG авторизация
├── prisma/
│   └── schema.prisma         # DB схема
├── userbot/
│   └── bot.py                # TG userbot с AI
├── n8n/
│   └── avito-to-lead.json    # Workflow для n8n
└── docker-compose.yml        # Postgres + pgvector
```

## Использование

### Добавление документов в RAG

```bash
curl -X POST http://localhost:3000/api/rag/embed \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {
        "content": "Наша компания делает ремонты под ключ. Цены от 5000₽/м². Гарантия 2 года."
      }
    ]
  }'
```

### Импорт n8n workflow

1. Откройте n8n (локально или Railway)
2. Import → `n8n/avito-to-lead.json`
3. Настройте credentials:
   - OpenRouter API
   - Telegram Bot
   - Environment variables (REPAIRCRM_API_URL, JWT_TOKEN)

### Тестирование Avito webhook

```bash
curl -X POST http://localhost:3000/api/avito/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Здравствуйте! Хочу сделать ремонт квартиры 50м², бюджет 300000₽",
    "link": "https://avito.ru/..."
  }'
```

## Deployment

### Vercel + Neon (Production)

1. Push to GitHub
2. Import в Vercel
3. Добавьте environment variables
4. Замените `DATABASE_URL` на Neon Postgres

### Userbot на VPS

```bash
# На сервере
git clone <repo>
cd userbot
pip install -r requirements.txt
# Настройте .env
nohup python bot.py &
```

## Roadmap

- [ ] Drag-and-drop для kanban (react-dnd)
- [ ] Realtime updates (Socket.io)
- [ ] Трекинг этапов ремонта
- [ ] Фото/видео в чатах
- [ ] Аналитика и отчеты

## Лицензия

MIT
