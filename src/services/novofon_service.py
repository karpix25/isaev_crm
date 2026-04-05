import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot import bot as telegram_bot
from src.config import settings
from src.models import Lead, LeadCallEvent, MessageStatus, Organization, User
from src.services.chat_service import chat_service
from src.services.lead_audit_service import lead_audit_service
from src.services.user_bot_service import user_bot_service

logger = logging.getLogger(__name__)


class NovofonApiError(Exception):
    def __init__(self, message: str, mnemonic: Optional[str] = None, code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.mnemonic = mnemonic
        self.code = code


class NovofonService:
    def __init__(self):
        self._session_access_token: Optional[str] = None
        self._session_expire_at: int = 0

    @staticmethod
    def _normalize_phone(raw_phone: Optional[str], with_plus: bool = True) -> Optional[str]:
        digits = re.sub(r"\D", "", raw_phone or "")
        if not digits:
            return None
        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        if len(digits) == 10:
            digits = "7" + digits
        if len(digits) < 10:
            return None
        return f"+{digits}" if with_plus else digits

    @staticmethod
    def _normalize_phone_digits(raw_phone: Optional[str]) -> str:
        return re.sub(r"\D", "", raw_phone or "")

    @staticmethod
    def _safe_json(payload: Any) -> str:
        try:
            return json.dumps(payload, ensure_ascii=False)
        except Exception:
            return "{}"

    def build_dial_url(self, phone: str, template: Optional[str] = None) -> str:
        normalized_phone = self._normalize_phone(phone, with_plus=True) or phone
        digits = self._normalize_phone_digits(normalized_phone)
        dial_template = (template or settings.novofon_dial_url_template or "tel:{phone}").strip() or "tel:{phone}"
        if "{phone}" not in dial_template and "{digits}" not in dial_template:
            if dial_template.endswith(":") or dial_template.endswith("/"):
                return f"{dial_template}{normalized_phone}"
            return f"{dial_template}{normalized_phone}"
        return dial_template.replace("{phone}", normalized_phone).replace("{digits}", digits)

    def render_business_card_message(
        self,
        *,
        company_name: Optional[str] = None,
        manager_name: Optional[str] = None,
        manager_phone: Optional[str] = None,
        template: Optional[str] = None,
        default_operator_phone: Optional[str] = None,
        site_url: Optional[str] = None,
        telegram_username: Optional[str] = None,
    ) -> str:
        company = (company_name or "").strip() or "Наша компания"
        manager = (manager_name or "").strip() or "Ваш менеджер"
        manager_phone_value = (
            self._normalize_phone(manager_phone, with_plus=True)
            or self._normalize_phone(default_operator_phone, with_plus=True)
            or self._normalize_phone(settings.novofon_default_operator_phone, with_plus=True)
            or "—"
        )
        site = (site_url or settings.novofon_business_card_site_url or "").strip()
        telegram = (telegram_username or settings.novofon_business_card_telegram or "").strip().lstrip("@")
        site_line = f"Сайт: {site}" if site else ""
        telegram_line = f"Telegram: @{telegram}" if telegram else ""

        template_value = (
            (template or "").strip()
            or (settings.novofon_business_card_template or "").strip()
            or (settings.novofon_business_card_message or "").strip()
            or "Спасибо за звонок!"
        )
        values = {
            "company_name": company,
            "manager_name": manager,
            "manager_phone": manager_phone_value,
            "site_url": site,
            "telegram": telegram,
            "site_line": site_line,
            "telegram_line": telegram_line,
        }
        try:
            rendered = template_value.format(**values)
        except Exception:
            rendered = template_value

        rendered_lines = [line.rstrip() for line in rendered.splitlines() if line.strip()]
        return "\n".join(rendered_lines).strip() or "Спасибо за звонок!"

    async def get_org_settings(self, db: AsyncSession, org_id: uuid.UUID) -> dict[str, str]:
        result = await db.execute(select(Organization).where(Organization.id == org_id))
        organization = result.scalar_one_or_none()
        return {
            "dial_url_template": (getattr(organization, "novofon_dial_url_template", None) or settings.novofon_dial_url_template or "").strip(),
            "default_operator_phone": (getattr(organization, "novofon_default_operator_phone", None) or settings.novofon_default_operator_phone or "").strip(),
            "business_card_template": (getattr(organization, "novofon_business_card_template", None) or settings.novofon_business_card_template or "").strip(),
            "business_card_site_url": (getattr(organization, "novofon_business_card_site_url", None) or settings.novofon_business_card_site_url or "").strip(),
            "business_card_telegram": (getattr(organization, "novofon_business_card_telegram", None) or settings.novofon_business_card_telegram or "").strip(),
            "organization_name": (getattr(organization, "name", None) or "").strip(),
        }

    def validate_webhook_secret(self, provided_secret: Optional[str]) -> bool:
        expected = (settings.novofon_webhook_secret or "").strip()
        if not expected:
            return True
        return expected == (provided_secret or "").strip()

    def is_configured(self) -> bool:
        has_auth = bool((settings.novofon_access_token or "").strip()) or bool(
            (settings.novofon_login or "").strip() and (settings.novofon_password or "").strip()
        )
        return bool(has_auth and (settings.novofon_virtual_phone_number or "").strip())

    async def _call_jsonrpc(self, method: str, params: dict[str, Any], request_id: Optional[str] = None) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": request_id or f"req_{uuid.uuid4()}",
            "method": method,
            "params": params,
        }
        timeout = max(1, int(settings.novofon_timeout_seconds))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(settings.novofon_api_base_url, json=payload)
            response.raise_for_status()
            data = response.json() if response.content else {}

        error_obj = data.get("error")
        if isinstance(error_obj, dict) and error_obj:
            error_message = str(error_obj.get("message") or "Novofon API error")
            error_code = error_obj.get("code")
            error_data = error_obj.get("data") if isinstance(error_obj.get("data"), dict) else {}
            mnemonic = error_data.get("error_code") or error_data.get("mnemonic")
            raise NovofonApiError(message=error_message, mnemonic=mnemonic, code=error_code)
        return data

    async def _get_access_token(self) -> str:
        static_token = (settings.novofon_access_token or "").strip()
        if static_token:
            return static_token

        login = (settings.novofon_login or "").strip()
        password = (settings.novofon_password or "").strip()
        if not login or not password:
            raise NovofonApiError("Novofon credentials are not configured")

        now_ts = int(time.time())
        if self._session_access_token and self._session_expire_at > now_ts + 30:
            return self._session_access_token

        response = await self._call_jsonrpc(
            method="login.user",
            params={"login": login, "password": password},
            request_id=f"login_{uuid.uuid4()}",
        )
        data = (response.get("result") or {}).get("data") or {}
        token = (data.get("access_token") or "").strip()
        expire_at = int(data.get("expire_at") or 0)
        if not token:
            raise NovofonApiError("Novofon login succeeded but access_token is empty")

        self._session_access_token = token
        self._session_expire_at = expire_at or (now_ts + 3500)
        return token

    async def start_employee_call(
        self,
        *,
        operator_phone: str,
        contact_phone: str,
        external_id: str,
        virtual_phone_number: Optional[str] = None,
    ) -> dict[str, Any]:
        if not self.is_configured():
            raise NovofonApiError("Novofon integration is not configured")

        normalized_operator = self._normalize_phone(operator_phone, with_plus=False)
        normalized_contact = self._normalize_phone(contact_phone, with_plus=False)
        normalized_virtual = self._normalize_phone(virtual_phone_number or settings.novofon_virtual_phone_number, with_plus=False)
        if not normalized_operator:
            raise NovofonApiError("Operator phone is invalid")
        if not normalized_contact:
            raise NovofonApiError("Lead phone is invalid")
        if not normalized_virtual:
            raise NovofonApiError("NOVOFON_VIRTUAL_PHONE_NUMBER is invalid")

        token = await self._get_access_token()
        params = {
            "access_token": token,
            "first_call": "employee",
            "switch_at_once": True,
            "show_virtual_phone_number": False,
            "virtual_phone_number": normalized_virtual,
            "external_id": external_id,
            "contact": normalized_contact,
            "employee": {"phone_number": normalized_operator},
        }
        try:
            response = await self._call_jsonrpc("start.employee_call", params, request_id=external_id)
        except NovofonApiError as exc:
            retry_mnemonics = {"access_token_expired", "access_token_invalid", "access_token_blocked"}
            if exc.mnemonic in retry_mnemonics and not (settings.novofon_access_token or "").strip():
                self._session_access_token = None
                self._session_expire_at = 0
                params["access_token"] = await self._get_access_token()
                response = await self._call_jsonrpc("start.employee_call", params, request_id=f"{external_id}_retry")
            else:
                raise

        response_data = (response.get("result") or {}).get("data") or {}
        call_session_id = response_data.get("call_session_id")
        return {
            "call_session_id": str(call_session_id) if call_session_id is not None else None,
            "response": response,
            "operator_phone": self._normalize_phone(operator_phone, with_plus=True),
            "contact_phone": self._normalize_phone(contact_phone, with_plus=True),
        }

    async def _send_business_card_message(self, db: AsyncSession, lead: Lead, message_text: str) -> tuple[str, Optional[str]]:
        if not lead.telegram_id:
            return "failed", "lead_has_no_telegram_id"

        telegram_message_id: Optional[int] = None
        send_error: Optional[str] = None
        sent = False

        try:
            await user_bot_service.send_message(
                db=db,
                org_id=lead.org_id,
                telegram_id=int(lead.telegram_id),
                text=message_text,
                username=lead.username,
            )
            sent = True
        except Exception as userbot_error:
            send_error = f"userbot_send_failed: {userbot_error}"
            if telegram_bot:
                try:
                    sent_msg = await telegram_bot.send_message(chat_id=int(lead.telegram_id), text=message_text)
                    telegram_message_id = getattr(sent_msg, "message_id", None)
                    sent = True
                    send_error = None
                except Exception as bot_error:
                    send_error = f"{send_error}; official_bot_send_failed: {bot_error}"
            else:
                send_error = f"{send_error}; official_bot_unavailable"

        msg_status = MessageStatus.SENT if sent else MessageStatus.FAILED
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=message_text,
            telegram_message_id=telegram_message_id,
            sender_name="CRM Auto",
            ai_metadata={"source": "novofon", "type": "business_card", "auto": True},
            status=msg_status,
        )
        return ("sent", None) if sent else ("failed", send_error)

    @staticmethod
    def _is_end_event(status: str) -> bool:
        status_upper = (status or "").upper()
        return status_upper.endswith("_END") or status_upper in {"CALL_ENDED", "HANGUP", "COMPLETED"}

    @staticmethod
    def _is_answered(disposition: Optional[str], payload: dict[str, Any]) -> bool:
        disposition_upper = (disposition or "").upper()
        if "ANSWER" in disposition_upper:
            return True
        billsec_raw = payload.get("billsec")
        try:
            if int(billsec_raw or 0) > 0:
                return True
        except Exception:
            pass
        for key in ("is_answered", "answered", "success"):
            value = payload.get(key)
            if isinstance(value, bool) and value:
                return True
            if isinstance(value, str) and value.strip().lower() in {"1", "true", "yes"}:
                return True
        return False

    async def _resolve_org_id_by_operator_phone(self, db: AsyncSession, operator_phone: Optional[str]) -> Optional[uuid.UUID]:
        normalized_operator = self._normalize_phone(operator_phone, with_plus=True)
        if not normalized_operator:
            return None

        result = await db.execute(select(User).where(User.phone.isnot(None)))
        users = result.scalars().all()
        matching_org_ids = []
        for user in users:
            if self._normalize_phone(user.phone, with_plus=True) == normalized_operator:
                matching_org_ids.append(user.org_id)
        unique_org_ids = list(dict.fromkeys(matching_org_ids))
        if len(unique_org_ids) == 1:
            return unique_org_ids[0]
        return None

    async def _find_lead_by_phone(
        self,
        db: AsyncSession,
        destination_phone: Optional[str],
        org_id: Optional[uuid.UUID] = None,
    ) -> Optional[Lead]:
        normalized_destination = self._normalize_phone(destination_phone, with_plus=True)
        if not normalized_destination:
            return None

        destination_digits = self._normalize_phone_digits(normalized_destination)
        destination_tail10 = destination_digits[-10:] if len(destination_digits) >= 10 else destination_digits
        query = select(Lead).where(Lead.phone.isnot(None))
        if org_id:
            query = query.where(Lead.org_id == org_id)
        query = query.order_by(Lead.updated_at.desc()).limit(500)
        result = await db.execute(query)
        leads = result.scalars().all()

        for lead in leads:
            normalized_lead_phone = self._normalize_phone(lead.phone, with_plus=True)
            if normalized_lead_phone == normalized_destination:
                return lead
            lead_digits = self._normalize_phone_digits(lead.phone)
            if destination_tail10 and lead_digits.endswith(destination_tail10):
                return lead
        return None

    async def process_webhook_event(self, db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
        status = str(payload.get("status") or payload.get("event") or payload.get("type") or "").strip()
        disposition = str(payload.get("disposition") or payload.get("result") or "").strip() or None
        external_id = str(payload.get("external_id") or payload.get("externalId") or "").strip() or None
        call_session_id = str(payload.get("call_session_id") or payload.get("callSessionId") or "").strip() or None
        destination = self._normalize_phone(
            str(payload.get("destination") or payload.get("contact") or payload.get("to") or payload.get("phone") or ""),
            with_plus=True,
        )
        operator = self._normalize_phone(
            str(payload.get("internal") or payload.get("employee") or payload.get("from") or payload.get("src") or ""),
            with_plus=True,
        )

        event: Optional[LeadCallEvent] = None
        if external_id:
            result = await db.execute(select(LeadCallEvent).where(LeadCallEvent.external_id == external_id))
            event = result.scalar_one_or_none()

        if event is None and call_session_id:
            result = await db.execute(
                select(LeadCallEvent)
                .where(LeadCallEvent.call_session_id == call_session_id)
                .order_by(LeadCallEvent.created_at.desc())
            )
            event = result.scalars().first()

        if event is None and destination:
            result = await db.execute(
                select(LeadCallEvent)
                .where(
                    LeadCallEvent.contact_phone == destination,
                    LeadCallEvent.call_status.in_(["manual_dial_requested", "starting", "initiated", "ringing", "answered"]),
                )
                .order_by(LeadCallEvent.created_at.desc())
            )
            candidates = result.scalars().all()
            if operator:
                for candidate in candidates:
                    if candidate.operator_phone == operator:
                        event = candidate
                        break
            if event is None and candidates:
                event = candidates[0]

        if event is None and destination:
            resolved_org_id = await self._resolve_org_id_by_operator_phone(db, operator)
            lead = await self._find_lead_by_phone(db, destination, org_id=resolved_org_id)
            if lead:
                org_settings = await self.get_org_settings(db, lead.org_id)
                event = LeadCallEvent(
                    org_id=lead.org_id,
                    lead_id=lead.id,
                    initiated_by_user_id=None,
                    operator_phone=operator or "",
                    contact_phone=destination,
                    external_id=external_id or f"webhook-{uuid.uuid4()}",
                    call_session_id=call_session_id,
                    call_status="webhook_received",
                    business_card_message=self.render_business_card_message(
                        company_name=org_settings.get("organization_name"),
                        manager_name=None,
                        manager_phone=operator,
                        template=org_settings.get("business_card_template"),
                        default_operator_phone=org_settings.get("default_operator_phone"),
                        site_url=org_settings.get("business_card_site_url"),
                        telegram_username=org_settings.get("business_card_telegram"),
                    ),
                    business_card_status="pending",
                    webhook_payload_json=self._safe_json(payload),
                )
                db.add(event)

        if event is None:
            logger.info("[NOVOFON] Webhook received but no matching call event found. payload=%s", payload)
            return {"matched": False}

        previous_status = event.call_status
        now_utc = datetime.now(timezone.utc)
        event.webhook_payload_json = self._safe_json(payload)
        if disposition:
            event.disposition = disposition
        if payload.get("record_link"):
            event.record_link = str(payload.get("record_link"))
        if status:
            normalized_status = status.upper()
            if normalized_status.endswith("_START"):
                event.call_status = "ringing"
                event.call_started_at = event.call_started_at or now_utc
            elif self._is_end_event(normalized_status):
                event.call_status = "answered" if self._is_answered(disposition, payload) else "completed"
                event.call_ended_at = now_utc
            else:
                event.call_status = normalized_status.lower()

        if previous_status != event.call_status:
            lead = await db.get(Lead, event.lead_id)
            if lead:
                await lead_audit_service.log_change(
                    db=db,
                    lead=lead,
                    action="call_status_updated",
                    source="novofon",
                    changes={"call_status": {"old": previous_status, "new": event.call_status}},
                )

        should_send_business_card = self._is_end_event(status) and self._is_answered(disposition, payload)
        if should_send_business_card and event.business_card_status != "sent":
            lead = await db.get(Lead, event.lead_id)
            if lead:
                message_text = (event.business_card_message or settings.novofon_business_card_message or "").strip()
                send_status, send_error = await self._send_business_card_message(db, lead, message_text)
                event.business_card_status = send_status
                event.business_card_error = send_error
                if send_status == "sent":
                    event.business_card_sent_at = now_utc
                    await lead_audit_service.log_change(
                        db=db,
                        lead=lead,
                        action="business_card_sent",
                        source="novofon",
                        changes={"business_card_status": {"old": "pending", "new": "sent"}},
                    )
                else:
                    await lead_audit_service.log_change(
                        db=db,
                        lead=lead,
                        action="business_card_failed",
                        source="novofon",
                        changes={"business_card_error": {"old": None, "new": send_error}},
                    )

        return {
            "matched": True,
            "event_id": str(event.id),
            "call_status": event.call_status,
            "business_card_status": event.business_card_status,
        }


novofon_service = NovofonService()
