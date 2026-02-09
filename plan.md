# Master Project Plan: Renovation CRM (SaaS-Ready)

## 1. Project Overview
Разработка CRM-системы для строительных компаний (ремонт квартир) с глубокой интеграцией в Telegram.
**Key USP:** Клиент и Рабочие используют только Telegram. Менеджер использует Web-Admin. Вся переписка и отчеты централизованы.

## 2. Tech Stack

### Backend (API & Logic)
* **Language:** Python 3.11+
* **Framework:** **FastAPI** (Async, Pydantic v2).
* **Database:** **PostgreSQL 16** (via `asyncpg`).
* **ORM:** **SQLAlchemy 2.0 (Async)** + **Alembic** (Migrations).
* **AI Provider:** **OpenRouter API** (Unified interface for Claude 3.5 Sonnet / GPT-4o).
* **Task Queue:** **Redis** + **Celery** (Background tasks, media processing).
* **Bot Framework:** **Aiogram 3.x** (Webhook mode).

### Frontend (Admin Dashboard)
* **Framework:** **React** + **Vite** (TypeScript).
* **UI Kit:** **Shadcn/UI** + **Tailwind CSS**.
* **State:** **TanStack Query** (React Query) + **Zustand**.
* **Real-time:** Polling (MVP) or WebSocket (Future).

### Client Side (Telegram Mini App)
* **Tech:** React (Single Page App within Telegram Webview).
* **Auth:** Telegram `initData` validation.

### Infrastructure
* **Containerization:** Docker + Docker Compose.
* **Storage:** MinIO (S3 compatible) for photos/videos/docs.
* **Reverse Proxy:** Nginx.

---

## 3. Database Schema (Consolidated Models)

**Core Concept:** Multi-tenant (SaaS) architecture from Day 1.

### Entities:
1.  **Organization:** (id, name, owner_id) — Изоляция данных разных фирм.
2.  **User:** (id, org_id, telegram_id, role=[admin, manager, worker, client], phone).
3.  **Lead:** (id, org_id, telegram_id, status, ai_summary, source).
    * *Status Flow:* New -> Qualified -> Measurement -> Estimate -> Contract -> Won/Lost.
4.  **ChatMessage:** (id, lead_id, direction=[inbound, outbound], content, media_url).
    * *Purpose:* Stores chat history between Bot and Lead for the CRM UI.
5.  **Project:** (id, org_id, client_id, address, budget_total, budget_spent).
6.  **Stage:** (id, project_id, name, status, progress_pct).
7.  **DailyReport:** (id, project_id, author_id, content, media_urls[]).
8.  **Transaction:** (id, project_id, amount, type=[expense, income], category, proof_url).
9.  **ChangeRequest:** (id, project_id, title, amount, status=[pending, approved]).

---

## 4. System Modules & Features

### Module A: Omni-Channel Chat (The "Bridge")
* **Telegram Webhook:** Receives messages from users.
* **Routing Logic:**
    * If user is `Lead`: Save msg to `ChatMessage` -> Notify Admin.
    * If user is `Worker`: Trigger Report Flow.
* **Admin Chat UI:** Interface looking like a messenger. Manager replies -> Bot sends to User.

### Module B: AI Sales Agent (OpenRouter)
* **Trigger:** New `Lead` starts a chat.
* **Logic:**
    1.  Fetch conversation history.
    2.  Send to OpenRouter (Model: `anthropic/claude-3.5-sonnet`).
    3.  **System Prompt:** Qualify lead (Ask: Area, Type, Budget).
    4.  **Output:** JSON with lead data -> Update `Lead` table.
* **Handoff:** If lead is "Hot", stop AI and alert Manager.

### Module C: Project Management (The Core)
* **Kanban:** Drag & Drop leads across stages.
* **Finance:**
    * Estimates (Plan).
    * Expenses (Fact) - Logged by workers via bot.
    * Change Orders - Extra costs requiring Client approval.

### Module D: Worker Bot (The Field Tool)
* **Commands:**
    * `/start` -> Auth check via phone number.
    * `Report Button`: Select Project -> Select Stage -> Upload Media -> Voice Note.
* **Media Handling:** Async upload to MinIO/S3.

### Module E: Client Mini App (The View)
* **Dashboard:** Progress bar, Financial summary.
* **Feed:** Instagram-like stories of daily repairs.
* **Action Center:** Approve "Change Requests", View Documents.

---

## 5. Development Roadmap (Phased Execution)

### Phase 1: Foundation (Backend)
1.  **Setup:** Initialize FastAPI project structure, Docker Compose (Postgres, Redis, MinIO).
2.  **DB:** Implement SQLAlchemy models (merged version of Chat + SaaS + Projects).
3.  **Auth:** Implement JWT Auth for Admin and `initData` validation for Telegram.

### Phase 2: The Chat Engine (Backend Logic)
1.  **Webhook:** Create `/webhook/telegram` endpoint using Aiogram.
2.  **Chat Logic:** Implement `save_incoming_message` and `send_outbound_message` services.
3.  **API:** Create endpoints for Admin Frontend to fetch chat history and send replies.

### Phase 3: Admin Frontend (React)
1.  **Scaffold:** Vite + Shadcn/UI.
2.  **Chat Interface:** Build the split-screen UI (Lead List | Chat Window | Lead Details).
3.  **Kanban:** Implement Drag & Drop for Leads.

### Phase 4: Worker Bot & Reporting
1.  **Bot FSM:** Implement Finite State Machine for "Submit Report" flow.
2.  **S3:** Configure media upload to MinIO.
3.  **Backend:** Link reports to Projects and Stages.

### Phase 5: AI Integration
1.  **Service:** Create `OpenRouterService` class.
2.  **Pipeline:** Connect AI to the "New Lead" chat flow.
3.  **Parsing:** Implement JSON extraction for Lead Qualification slots.

### Phase 6: Client Mini App & Polish
1.  **Mini App:** Build simple React view for Clients.
2.  **Deploy:** Nginx configuration and SSL setup.

---

## 6. Instructions for AI Developer

**Role:** You are a Senior Full-Stack Developer specializing in Python/FastAPI and React.

**Objective:** Build the system described above step-by-step.

**Guidelines:**
1.  **Code First:** Always provide the full code for files, do not use placeholders like `...`.
2.  **Type Safety:** Use Pydantic schemas for all API inputs/outputs. Use TypeScript for Frontend.
3.  **Configuration:** Use `.env` files for all secrets (OpenRouter Key, DB URL, Telegram Token).
4.  **Start:** Begin with **Phase 1 (Foundation)**. Generate the directory structure, `docker-compose.yml`, and `models.py`.