# DEV LOG — gemini-live-service

> Этот файл — главный инструмент координации между агентами.
> Читай с конца. Последняя запись = текущее состояние.

---

## 2026-05-07 ~20:00 — Claude Code (VDS arbitr)

### Контекст
Проект инициирован Борисом. Архитектура разработана Танком (CTO-агент, DeepSeek в OpenClaw).
Исходный дизайн: `/home/shectory/gemini-live-service-design.md`
Утверждённый план: `/home/shectory/.claude/plans/elegant-juggling-torvalds.md`

### Исправленные критические баги дизайна
1. **Сессии в памяти → Redis** (SessionStore с TTL 24h)
2. **Session resumption** (Gemini handle → Redis, авто-восстановление)
3. **History replay → summary в system_prompt** (не turn-by-turn, исключает зависание)
4. **Raw PCM → WAV** (RIFF-заголовок, Telegram совместимость)
5. **HTTP → HTTPS** (nginx + certbot, обязательно для getUserMedia)
6. **Auth** (Bearer-токен на пользователя, изоляция данных)

### Добавленные правила (от Бориса, 2026-05-07)
- Все Google/Gemini API — строго через прокси (GOOGLE_PROXY_URL в .env)
- Расходы в V1 пишем в свою БД, в V2 интегрируем с OurDiary
- Коммитить на GitHub после каждого этапа (org: Shevbo)
- Добавить проект на Shectory Portal как карточку

### Сделано
- [x] Структура директорий создана
- [x] Память агента обновлена (4 файла + MEMORY.md)
- [x] DEV_LOG создан
- [x] Все файлы проекта написаны (см. ниже)

### Файлы проекта
```
docker-compose.yml      — Redis + app
.env.example            — шаблон переменных
prisma/schema.prisma    — модели данных (Prisma Client Python)
requirements.txt        — зависимости
Dockerfile
src/config.py           — настройки (pydantic-settings)
src/auth.py             — Bearer-токен auth
src/main.py             — FastAPI app entry
src/session/audio.py    — pcm_to_wav, save_turn_audio
src/session/store.py    — RedisSessionStore
src/session/manager.py  — GeminiSessionManager (FIX: resume, history-as-summary)
src/services/analyzer.py — пост-сессионный анализ (дневник/расходы)
src/api/voice.py        — /v1/session/*
src/api/dialogs.py      — /v1/dialogs/*
src/api/diary.py        — /v1/diary/*
src/ws/voice_ws.py      — WebSocket bidirectional audio
static/index.html       — голосовой UI
static/history.html     — история диалогов
static/diary.html       — дневник и расходы
static/js/audio.js      — MediaRecorder + AudioContext
static/js/api.js        — REST/WS клиент
static/js/app.js        — основная логика
scripts/add-to-portal.js — добавление карточки на Shectory Portal
```

### Git
- Локальный коммит: `6b1d8f2` (main)
- Нужно: создать GitHub repo `Shevbo/gemini-live-service` и сделать `git remote add origin + push`

### Следующие шаги для агентов
1. **Selfcoder** — проверить и дополнить `src/session/manager.py` (резюмпция сессий — самое сложное место)
2. **QAper** — написать тесты для `audio.py` (WAV-заголовок), `store.py` (Redis TTL)
3. **Tank** — ревью архитектуры WebSocket эндпоинта (`src/ws/voice_ws.py`)
4. **Человек (Борис)** — создать GitHub repo, заполнить `.env` из `.env.example`, запустить `docker compose up -d`

### Блокеры
- Нужен GEMINI_API_KEY (из openclaw.json или нового)
- Нужно создать GitHub repo: `git@github.com:Shevbo/gemini-live-service.git`
- Нужно добавить DNS запись `voice.shectory.ru → 83.69.248.77` (если ещё нет)
- Нужны права для certbot (`sudo certbot certonly --nginx -d voice.shectory.ru`)
- Нужны права для создания БД PostgreSQL (`CREATE DATABASE gemini_live`)

---

---

## 2026-05-08 06:15 UTC — Claude Code (VDS arbitr)

### Сделано
- [x] БД `gemini_live` создана на PostgreSQL :5432, юзер `gemini_live_app`
- [x] `.env` заполнен (Gemini API key, proxy, токены Бориса/Марии/Даниэлы)
- [x] Redis запущен в Docker (127.0.0.1:6379)
- [x] Prisma миграция применена — таблицы созданы
- [x] SSL сертификат Let's Encrypt для voice.shectory.ru
- [x] nginx HTTPS настроен с WebSocket поддержкой
- [x] Приложение запущено: `nohup uvicorn src.main:app --host 127.0.0.1 --port 8080`
- [x] Проверка: https://voice.shectory.ru/ отдаёт страницу Медсестры

### Токены пользователей (хранить в безопасном месте)
Борис:   5769cab495bacaf18f77138515ccea2edf0185d9521ffc11
Мария:   7cebb8cd9924a03fc659d3dcb118785b0a7a63d33c2afc77
Даниэла: 17be8ee521c348d755092fbc196bf19a6e2db47c1ed23982

### Следующие шаги
- [ ] Добавить в PM2 чтобы приложение выживало перезагрузку сервера
- [ ] Протестировать голосовой диалог (требует GEMINI_API_KEY + прокси)
- [ ] Добавить карточку на Shectory Portal
- [ ] QAper — написать тесты
