import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Lead, LeadChangeLog


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "value"):
        return getattr(value, "value")
    return value


class LeadAuditService:
    @staticmethod
    async def log_change(
        db: AsyncSession,
        lead: Lead,
        action: str,
        source: str,
        user_id: Optional[uuid.UUID] = None,
        changes: Optional[dict[str, dict[str, Any]]] = None,
    ) -> None:
        payload = changes or {}
        log = LeadChangeLog(
            org_id=lead.org_id,
            lead_id=lead.id,
            user_id=user_id,
            action=action,
            source=source,
            changes_json=json.dumps(payload, ensure_ascii=False),
        )
        db.add(log)

    @staticmethod
    def build_field_changes(
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        keys = set(before.keys()) | set(after.keys())
        changes: dict[str, dict[str, Any]] = {}
        for key in keys:
            old_value = _normalize_value(before.get(key))
            new_value = _normalize_value(after.get(key))
            if old_value != new_value:
                changes[key] = {"old": old_value, "new": new_value}
        return changes


lead_audit_service = LeadAuditService()
