from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AgentToolCall, Lead


class AgentToolLogService:
    async def create_call(
        self,
        db: AsyncSession,
        *,
        lead: Lead,
        user_message: str,
        action: str,
        confidence: int,
        reason: str,
        args: dict[str, Any],
        strict_schema: bool,
    ) -> AgentToolCall:
        call = AgentToolCall(
            org_id=lead.org_id,
            lead_id=lead.id,
            user_message=user_message[:4000],
            action=action,
            confidence=confidence,
            reason=reason[:1000] if reason else None,
            args=args or {},
            strict_schema=strict_schema,
            executed=False,
            result="selected",
        )
        db.add(call)
        await db.commit()
        await db.refresh(call)
        return call

    async def mark_result(
        self,
        db: AsyncSession,
        call: AgentToolCall,
        *,
        executed: bool,
        result: str,
        error: str | None = None,
    ) -> AgentToolCall:
        call.executed = executed
        call.result = result[:80]
        call.error = error[:1000] if error else None
        await db.commit()
        await db.refresh(call)
        return call


agent_tool_log_service = AgentToolLogService()
