"""
API route modules.
"""

from fastapi import APIRouter
from src.api import auth, organizations, chat, leads, webhook, dashboard, projects, ai_management, custom_fields

# Main API router
api_router = APIRouter(prefix="/api")

# Include sub-routers
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(chat.router)
api_router.include_router(leads.router)
api_router.include_router(webhook.router, prefix="/webhook", tags=["Webhook"])
api_router.include_router(dashboard.router)
api_router.include_router(projects.router)
api_router.include_router(ai_management.router)
api_router.include_router(custom_fields.router)

__all__ = ["api_router"]
