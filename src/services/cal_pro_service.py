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
            logger.info("Cal Pro slots skipped: %s", self.missing_reason())
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
            logger.info(
                "Fetching Cal Pro slots: event_type=%s start=%s end=%s timezone=%s",
                self._event_type_log_label(),
                params["start"],
                params["end"],
                settings.cal_pro_time_zone,
            )
            async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=5.0)) as client:
                response = await client.get(
                    f"{settings.cal_pro_api_base_url.rstrip('/')}/v2/slots",
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:1000] if exc.response is not None else ""
            logger.error(
                "Failed to fetch Cal Pro slots: status=%s body=%s",
                exc.response.status_code if exc.response is not None else "unknown",
                body,
            )
            return []
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch Cal Pro slots: %s", exc)
            return []

        slots = self._flatten_slots(payload.get("data") or {}, limit or settings.cal_pro_max_slots)
        logger.info("Fetched Cal Pro slots: count=%s", len(slots))
        return slots

    async def create_booking(
        self,
        start: str,
        contact: QuizContact,
        answers: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured():
            raise ValueError(self.missing_reason() or "cal_pro_not_configured")
        if not settings.cal_pro_api_key:
            raise ValueError("cal_pro_api_key_missing")

        address = str((metadata or {}).get("measurement_address") or "").strip()
        booking_metadata = self._clean_metadata({
            "source": "isaev_crm_quiz",
            "quiz_summary": self._build_quiz_summary(answers),
            **(metadata or {}),
        })
        body: dict[str, Any] = {
            "start": self._to_utc_iso(start),
            "attendee": {
                "name": contact.name,
                "timeZone": settings.cal_pro_time_zone,
                "language": "ru",
            },
            "metadata": booking_metadata,
        }
        if contact.email:
            body["attendee"]["email"] = str(contact.email)
        else:
            body["attendee"]["email"] = self._fallback_email(metadata)
        if contact.phone:
            body["attendee"]["phoneNumber"] = self._format_phone_number(contact.phone)
        body.update(self._event_type_params())

        headers = {
            "Content-Type": "application/json",
            "cal-api-version": settings.cal_pro_bookings_api_version,
        }
        if settings.cal_pro_api_key:
            headers["Authorization"] = f"Bearer {settings.cal_pro_api_key}"

        logger.info(
            "Creating Cal Pro booking: event_type=%s start=%s name=%s phone_present=%s address_present=%s",
            self._event_type_log_label(),
            body["start"],
            contact.name,
            bool(contact.phone),
            bool(address),
        )
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = await client.post(
                f"{settings.cal_pro_api_base_url.rstrip('/')}/v2/bookings",
                json=body,
                headers=headers,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Cal Pro booking failed: status=%s body=%s",
                    response.status_code,
                    response.text[:2000],
                )
                raise exc
            payload = response.json()
            booking_uid = self._extract_booking_uid(payload)
            if payload.get("status") != "success" or not booking_uid:
                logger.error(
                    "Cal Pro booking returned unexpected payload: status=%s uid=%s body=%s",
                    payload.get("status"),
                    booking_uid,
                    response.text[:2000],
                )
                raise ValueError("cal_pro_booking_not_confirmed")
            logger.info(
                "Cal Pro booking created: status=%s uid=%s",
                payload.get("status"),
                booking_uid,
            )
            return payload

    async def reschedule_booking(
        self,
        booking_uid: str,
        start: str,
        rescheduled_by: str | None = None,
        reason: str = "Client requested reschedule",
    ) -> dict[str, Any]:
        if not self.is_configured():
            raise ValueError(self.missing_reason() or "cal_pro_not_configured")
        if not settings.cal_pro_api_key:
            raise ValueError("cal_pro_api_key_missing")
        clean_uid = str(booking_uid or "").strip()
        if not clean_uid:
            raise ValueError("booking_uid_missing")

        body: dict[str, Any] = {
            "start": self._to_utc_iso(start),
            "reschedulingReason": reason,
        }
        if rescheduled_by:
            body["rescheduledBy"] = str(rescheduled_by)

        headers = {
            "Content-Type": "application/json",
            "cal-api-version": settings.cal_pro_bookings_api_version,
            "Authorization": f"Bearer {settings.cal_pro_api_key}",
        }

        logger.info("Rescheduling Cal Pro booking: uid=%s start=%s", clean_uid, body["start"])
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = await client.post(
                f"{settings.cal_pro_api_base_url.rstrip('/')}/v2/bookings/{clean_uid}/reschedule",
                json=body,
                headers=headers,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Cal Pro reschedule failed: status=%s body=%s",
                    response.status_code,
                    response.text[:2000],
                )
                raise exc
            payload = response.json()
            booking_uid = self._extract_booking_uid(payload)
            if payload.get("status") != "success" or not booking_uid:
                logger.error(
                    "Cal Pro reschedule returned unexpected payload: status=%s uid=%s body=%s",
                    payload.get("status"),
                    booking_uid,
                    response.text[:2000],
                )
                raise ValueError("cal_pro_reschedule_not_confirmed")
            logger.info("Cal Pro booking rescheduled: status=%s uid=%s", payload.get("status"), booking_uid)
            return payload

    async def cancel_booking(
        self,
        booking_uid: str,
        reason: str = "Client requested cancellation",
        cancel_subsequent_bookings: bool = True,
    ) -> dict[str, Any]:
        if not self.is_configured():
            raise ValueError(self.missing_reason() or "cal_pro_not_configured")
        if not settings.cal_pro_api_key:
            raise ValueError("cal_pro_api_key_missing")
        clean_uid = str(booking_uid or "").strip()
        if not clean_uid:
            raise ValueError("booking_uid_missing")

        body: dict[str, Any] = {
            "cancellationReason": reason,
            "cancelSubsequentBookings": cancel_subsequent_bookings,
        }
        headers = {
            "Content-Type": "application/json",
            "cal-api-version": settings.cal_pro_bookings_api_version,
            "Authorization": f"Bearer {settings.cal_pro_api_key}",
        }

        logger.info("Cancelling Cal Pro booking: uid=%s", clean_uid)
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = await client.post(
                f"{settings.cal_pro_api_base_url.rstrip('/')}/v2/bookings/{clean_uid}/cancel",
                json=body,
                headers=headers,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Cal Pro cancel failed: status=%s body=%s",
                    response.status_code,
                    response.text[:2000],
                )
                raise exc
            payload = response.json()
            if payload.get("status") != "success":
                logger.error(
                    "Cal Pro cancel returned unexpected payload: status=%s body=%s",
                    payload.get("status"),
                    response.text[:2000],
                )
                raise ValueError("cal_pro_cancel_not_confirmed")
            logger.info("Cal Pro booking cancelled: status=%s uid=%s", payload.get("status"), clean_uid)
            return payload

    def _to_utc_iso(self, value: str) -> str:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def _format_phone_number(self, value: str) -> str:
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())
        if not digits:
            return str(value or "")
        return f"+{digits}"

    def _build_quiz_summary(self, answers: dict[str, Any] | None) -> str:
        if not answers:
            return ""
        pairs = [f"{key}: {value}" for key, value in answers.items() if value is not None]
        return "; ".join(pairs)[:500]

    def _clean_metadata(self, metadata: dict[str, Any]) -> dict[str, str]:
        clean: dict[str, str] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            clean_key = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(key))[:40]
            if not clean_key:
                continue
            clean[clean_key] = str(value)[:500]
            if len(clean) >= 50:
                break
        return clean

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

    def _event_type_log_label(self) -> str:
        if settings.cal_pro_event_type_id:
            return f"id:{settings.cal_pro_event_type_id}"
        owner = settings.cal_pro_team_slug or settings.cal_pro_username or "unknown-owner"
        return f"slug:{settings.cal_pro_event_type_slug}@{owner}"

    def _extract_booking_uid(self, payload: dict[str, Any]) -> str | None:
        data = payload.get("data") if isinstance(payload, dict) else None
        source = data if isinstance(data, dict) else payload
        value = source.get("uid") or source.get("bookingUid") or source.get("id")
        return str(value) if value else None

    def _fallback_email(self, metadata: dict[str, Any] | None = None) -> str:
        source = str((metadata or {}).get("lead_id") or (metadata or {}).get("session_token") or "quiz")
        safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in source).strip("-")[:64] or "quiz"
        return f"lead-{safe}@isaev-crm.local"

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
