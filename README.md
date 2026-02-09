# Renovation CRM - Multi-Tenant Construction Management System

A modern CRM system for construction companies (apartment renovation) with deep Telegram integration.

## 🎯 Key Features

- **Multi-Tenant SaaS Architecture**: Complete data isolation per organization
- **Telegram Integration**: Clients and workers use only Telegram, managers use web admin
- **AI Sales Agent**: Automated lead qualification using Claude 3.5 Sonnet
- **Project Management**: Kanban boards, budget tracking, stage management
- **Worker Reports**: Daily progress reports via Telegram bot with media uploads
- **Client Portal**: Telegram Mini App for project progress tracking

## 🏗️ Tech Stack

### Backend
- **FastAPI** - Modern async Python web framework
- **PostgreSQL 16** - Primary database
- **SQLAlchemy 2.0** - Async ORM
- **Alembic** - Database migrations
- **Redis** - Task queue and caching
- **Celery** - Background task processing
- **Aiogram 3.x** - Telegram bot framework

### Frontend
- **React + Vite** - Admin dashboard
- **Shadcn/UI + Tailwind** - UI components
- **TanStack Query** - Data fetching
- **Zustand** - State management

### Infrastructure
- **Docker + Docker Compose** - Containerization
- **MinIO** - S3-compatible object storage
- **Nginx** - Reverse proxy

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+
- Node.js 18+ (for frontend)

### 1. Clone and Setup

```bash
# Copy environment variables
cp .env.example .env

# Edit .env and fill in required values:
# - TELEGRAM_BOT_TOKEN (from @BotFather)
# - JWT_SECRET_KEY (generate with: openssl rand -hex 32)
# - OPENROUTER_API_KEY (for AI features)
```

### 2. Start Services

```bash
# Start PostgreSQL, Redis, and MinIO
docker-compose up -d

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Migrations

```bash
# Create initial migration
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head
```

### 4. Start API Server

```bash
# Development mode with auto-reload
uvicorn src.main:app --reload

# Or use the main.py directly
python -m src.main
```

### 5. Access the Application

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

## 📁 Project Structure

```
renovation-crm/
├── src/
│   ├── api/              # API endpoints
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   ├── dependencies/     # FastAPI dependencies
│   ├── config.py         # Configuration
│   ├── database.py       # Database setup
│   └── main.py           # FastAPI app
├── alembic/              # Database migrations
├── docker-compose.yml    # Docker services
├── requirements.txt      # Python dependencies
└── .env.example          # Environment template
```

## 🗄️ Database Schema

### Core Entities

1. **Organization** - Multi-tenant isolation
2. **User** - Admin, Manager, Worker, Client roles
3. **Lead** - Potential clients with AI qualification
4. **ChatMessage** - Conversation history
5. **Project** - Active renovation projects
6. **Stage** - Project phases (Demolition, Electrical, etc.)
7. **DailyReport** - Worker progress updates
8. **Transaction** - Financial tracking
9. **ChangeRequest** - Scope change approvals

## 🔐 Authentication

### Admin/Manager Login
```bash
POST /api/auth/login
{
  "email": "admin@example.com",
  "password": "password"
}
```

### Telegram Authentication
```bash
POST /api/auth/telegram
{
  "id": 123456789,
  "first_name": "John",
  "auth_date": 1234567890,
  "hash": "..."
}
```

## 📝 Development Roadmap

- [x] **Phase 1**: Foundation (Backend) ✅
- [ ] **Phase 2**: Chat Engine (Backend Logic)
- [ ] **Phase 3**: Admin Frontend (React)
- [ ] **Phase 4**: Worker Bot & Reporting
- [ ] **Phase 5**: AI Integration
- [ ] **Phase 6**: Client Mini App & Deployment

## 🧪 Testing

```bash
# Run tests (coming soon)
pytest

# Check code quality
ruff check src/
black src/
```

## 📚 API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🤝 Contributing

This is a private project. For questions, contact the development team.

## 📄 License

Proprietary - All rights reserved
