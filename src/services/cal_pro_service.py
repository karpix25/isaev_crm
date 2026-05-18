from datetime import datetime, timedelta, timezone
from typing import Any
import logging

import httpx

from src.config import settings
from src.schemas.quiz import MeasurementSlot, QuizContact

logger = logging.getLogger(__name__)


class CalProService:
    def is_configured(self) -> bool:
        return bool(
            settings.cal_pro_enabled
            and (
                settings.cal_pro_event_type_id
                or (settings.cal_pro_event_type_slug and (settings.cal_pro_username or settings.cal_pro_team_slug))
            )
        )

    def missing_reason(self) -> str | None:
        if not settings.cal_pro_enabled:
            return "cal_pro_disabled"
        if not settings.cal_pro_event_type_id and not settings.cal_pro_event_type_slug:
            return "cal_pro_event_type_not_configured"
        if settings.cal_pro_event_type_slug and not (settings.cal_pro_username or settings.cal_pro_team_slug):
            return "cal_pro_owner_not_configured"
        return None

    async def get_slots(self, days_ahead: int | None = None, limit: int | None = None) -> list[MeasurementSlot]:
        if not self.is_configured():
            return []

        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead or settings.cal_pro_slot_days_ahead)
        params: dict[str, Any] = {
            "start": now.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "timeZone": settings.cal_pro_time_zone,
            "duration": settings.cal_pro_duration_minutes,
            "format": "range",
        }
        params.update(self._event_type_params())

        headers = {"cal-api-version": settings.cal_pro_slots_api_version}
        if settings.cal_pro_api_key:
            headers["Authorization"] = f"Bearer {settings.cal_pro_api_key}"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=5.0)) as client:
                response = await client.get(
                    f"{settings.cal_pro_api_base_url.rstrip('/')}/v2/slots",
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch Cal Pro slots: %s", exc)
            return []

        return self._flatten_slots(payload.get("data") or {}, limit or settings.cal_pro_max_slots)

    async def create_booking(
        self,
        start: str,
        contact: QuizContact,
        answers: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured():
            raise ValueError(self.missing_reason() or "cal_pro_not_configured")

        body: dict[str, Any] = {
            "start": start,
            "attendee": {
                "name": contact.name,
                "timeZone": settings.cal_pro_time_zone,
                "language": "ru",
            },
            "metadata": {
                "source": "isaev_crm_quiz",
                **(metadata or {}),
            },
        }
        if contact.email:
            body["attendee"]["email"] = str(contact.email)
        if contact.phone:
            body["attendee"]["phoneNumber"] = contact.phone
        body.update(self._event_type_params())
        if settings.cal_pro_duration_minutes:
            body["lengthInMinutes"] = settings.cal_pro_duration_minutes
        if answers:
            body["bookingFieldsResponses"] = {
                key: str(value)[:500]
                for key, value in answers.items()
                if value is not None
            }

        headers = {
            "Content-Type": "application/json",
            "cal-api-version": settings.cal_pro_bookings_api_version,
        }
        if settings.cal_pro_api_key:
            headers["Authorization"] = f"Bearer {settings.cal_pro_api_key}"

        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = await client.post(
                f"{settings.cal_pro_api_base_url.rstrip('/')}/v2/bookings",
                json=body,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    def _event_type_params(self) -> dict[str, Any]:
        if settings.cal_pro_event_type_id:
            return {"eventTypeId": settings.cal_pro_event_type_id}

        params: dict[str, Any] = {"eventTypeSlug": settings.cal_pro_event_type_slug}
        if settings.cal_pro_username:
            params["username"] = settings.cal_pro_username
        if settings.cal_pro_team_slug:
            params["teamSlug"] = settings.cal_pro_team_slug
        if settings.cal_pro_organization_slug:
            params["organizationSlug"] = settings.cal_pro_organization_slug
        return params

    def _flatten_slots(self, data: dict[str, Any], limit: int) -> list[MeasurementSlot]:
        slots: list[MeasurementSlot] = []
        for date_key in sorted(data.keys()):
            for item in data.get(date_key) or []:
                if isinstance(item, str):
                    start = item
                    end = None
                else:
                    start = item.get("start")
                    end = item.get("end")
                if not start:
                    continue
                slots.append(
                    MeasurementSlot(
                        start=start,
                        end=end,
                        label=self._format_slot_label(start),
                        date_label=self._format_date_label(start),
                    )
                )
                if len(slots) >= limit:
                    return slots
        return slots

    def _format_slot_label(self, value: str) -> str:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime("%H:%M")
        except ValueError:
            return value

    def _format_date_label(self, value: str) -> str:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime("%d.%m")
        except ValueError:
            return value[:10]


cal_pro_service = CalProService()
