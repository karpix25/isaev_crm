"""
Business logic services.
"""

__all__ = [
    "AuthService",
    "auth_service",
    "ChatService",
    "chat_service",
    "LeadService",
    "lead_service",
    "OpenRouterService",
    "openrouter_service",
    "WazzupService",
    "wazzup_service",
]


def __getattr__(name: str):
    if name in {"AuthService", "auth_service"}:
        from src.services.auth import AuthService, auth_service

        return AuthService if name == "AuthService" else auth_service
    if name in {"ChatService", "chat_service"}:
        from src.services.chat_service import ChatService, chat_service

        return ChatService if name == "ChatService" else chat_service
    if name in {"LeadService", "lead_service"}:
        from src.services.lead_service import LeadService, lead_service

        return LeadService if name == "LeadService" else lead_service
    if name in {"OpenRouterService", "openrouter_service"}:
        from src.services.openrouter_service import OpenRouterService, openrouter_service

        return OpenRouterService if name == "OpenRouterService" else openrouter_service
    if name in {"WazzupService", "wazzup_service"}:
        from src.services.wazzup_service import WazzupService, wazzup_service

        return WazzupService if name == "WazzupService" else wazzup_service
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
