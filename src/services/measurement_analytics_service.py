import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.analytics_service import analytics_service
from src.services.posthog_service import posthog_service

logger = logging.getLogger(__name__)


class MeasurementAnalyticsService:
    async def record_event(
        self,
        db: AsyncSession,
        lead,
        event_type: str,
        *,
        source: str,
        event_data: dict[str, Any] | None = None,
    ) -> None:
        data = self._lead_data(lead)
        session_token = str(data.get("quiz_session_token") or "").strip()
        payload = self._build_payload(lead=lead, source=source, data=data, event_data=event_data or {})

        try:
            if session_token:
                await analytics_service.record_event(
                    db=db,
                    session_token=session_token,
                    event_type=event_type,
                    step_id="measurement",
                    event_data=payload,
                )
                return

            await posthog_service.capture(
                distinct_id=f"lead_{lead.id}",
                event=event_type,
                properties=payload,
            )
        except Exception:
            logger.warning(
                "Failed to record measurement analytics event: lead_id=%s event=%s",
                getattr(lead, "id", None),
                event_type,
                exc_info=True,
            )

    def _build_payload(self, *, lead, source: str, data: dict[str, Any], event_data: dict[str, Any]) -> dict[str, Any]:
        measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
        utm = data.get("utm") if isinstance(data.get("utm"), dict) else {}
        return {
            "lead_id": str(lead.id),
            "source": source,
            "booking_source": "messenger",
            "messenger": self._messenger_from_source(source),
            "status": measurement.get("status"),
            "utm_source": utm.get("source"),
            "utm_medium": utm.get("medium"),
            "utm_campaign": utm.get("campaign"),
            "utm_content": utm.get("content"),
            "utm_term": utm.get("term"),
            **event_data,
        }

    def _lead_data(self, lead) -> dict[str, Any]:
        raw = getattr(lead, "extracted_data", None)
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _messenger_from_source(self, source: str) -> str:
        normalized = str(source or "").lower()
        if "whatsapp" in normalized:
            return "whatsapp"
        if "telegram" in normalized:
            return "telegram"
        return "messenger"


measurement_analytics_service = MeasurementAnalyticsService()
