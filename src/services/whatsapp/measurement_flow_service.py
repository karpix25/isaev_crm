from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Lead, LeadStatus, MessageStatus, MessageTransport
from src.schemas.quiz import MeasurementBookingRequest, QuizContact
from src.services.cal_pro_service import cal_pro_service
from src.services.chat_service import chat_service
from src.services.quiz_service import quiz_service
from src.services.whatsapp.phone import normalize_phone
from src.services.whatsapp.transport_service import WhatsAppTransportError, whatsapp_transport_service

logger = logging.getLogger(__name__)

MAX_WHATSAPP_SLOTS = 5


class WhatsAppMeasurementFlowService:
    async def prepare_slot_offer_text(self, db: AsyncSession, lead: Lead) -> str:
        slots = await cal_pro_service.get_slots(days_ahead=7, limit=80)
        if not slots:
            self._store_measurement_state(
                lead,
                {
                    "status": "awaiting_whatsapp_manual_slot",
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                    "source": "whatsapp",
                },
            )
            await db.commit()
            return "Свободные окна сейчас не загрузились. Напишите удобный день и время — подберу ближайший вариант вручную."

        offered = [
            {"index": index, "start": slot.start, "label": self._slot_label(slot)}
            for index, slot in enumerate(slots[:MAX_WHATSAPP_SLOTS], start=1)
        ]
        self._store_measurement_state(
            lead,
            {
                "status": "awaiting_whatsapp_slot_choice",
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "source": "whatsapp",
                "offered_slots": offered,
            },
        )
        if lead.status in quiz_service.AUTO_QUIZ_STATUSES:
            lead.status = LeadStatus.MEASUREMENT_PENDING.value
        await db.commit()

        lines = ["Ближайшие окна:"]
        lines.extend(f"{item['index']}. {item['label']}" for item in offered)
        lines.append("")
        lines.append("Ответьте цифрой, например 1. Если не подходит — напишите удобный день и время.")
        return "\n".join(lines)

    async def handle_message(self, db: AsyncSession, lead: Lead, text: str | None, chat_id: str) -> bool:
        clean_text = (text or "").strip()
        if not clean_text:
            return False

        data = self._parse_data(lead.extracted_data)
        measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
        status = str(measurement.get("status") or "")

        if status == "awaiting_whatsapp_slot_choice":
            return await self._handle_slot_choice(db, lead, data, measurement, clean_text, chat_id)
        if status == "awaiting_whatsapp_measurement_address":
            return await self._handle_address(db, lead, data, measurement, clean_text, chat_id)
        return False

    async def _handle_slot_choice(
        self,
        db: AsyncSession,
        lead: Lead,
        data: dict[str, Any],
        measurement: dict[str, Any],
        text: str,
        chat_id: str,
    ) -> bool:
        selected = self._selected_slot(measurement, text)
        if not selected:
            if self._looks_like_manual_time_preference(text):
                measurement.update(
                    {
                        "status": "awaiting_manager_manual_slot",
                        "preferred_time_text": text,
                        "manual_slot_requested_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                data["measurement"] = measurement
                lead.extracted_data = json.dumps(data, ensure_ascii=False)
                await db.commit()
                await self._send_and_store(
                    db,
                    lead,
                    chat_id,
                    "Принял. Проверю свободное окно под это время и подтвержу запись здесь.",
                    "whatsapp_measurement_manual_time_received",
                )
                return True

            await self._send_and_store(
                db,
                lead,
                chat_id,
                "Не увидел номер окна. Ответьте цифрой из списка, например 1, или напишите удобный день и время.",
                "whatsapp_measurement_slot_choice_retry",
            )
            return True

        measurement.update(
            {
                "status": "awaiting_whatsapp_measurement_address",
                "pending_start": selected["start"],
                "selected_slot_label": selected["label"],
                "selected_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        data["measurement"] = measurement
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        await db.commit()

        address = self._measurement_address(data, measurement)
        if address:
            return await self._book_selected_slot(db, lead, data, measurement, chat_id, address)

        await self._send_and_store(
            db,
            lead,
            chat_id,
            f"Отлично, держу окно {selected['label']}.\n\nНапишите адрес объекта: город, улицу, дом и квартиру/офис.",
            "whatsapp_measurement_address_request",
        )
        return True

    async def _handle_address(
        self,
        db: AsyncSession,
        lead: Lead,
        data: dict[str, Any],
        measurement: dict[str, Any],
        text: str,
        chat_id: str,
    ) -> bool:
        address = text.strip()
        if len(address) < 5:
            await self._send_and_store(
                db,
                lead,
                chat_id,
                "Напишите адрес чуть подробнее: город, улицу, дом и квартиру/офис.",
                "whatsapp_measurement_address_retry",
            )
            return True
        return await self._book_selected_slot(db, lead, data, measurement, chat_id, address)

    async def _book_selected_slot(
        self,
        db: AsyncSession,
        lead: Lead,
        data: dict[str, Any],
        measurement: dict[str, Any],
        chat_id: str,
        address: str,
    ) -> bool:
        start = str(measurement.get("pending_start") or "").strip()
        session_token = str(data.get("quiz_session_token") or "").strip()
        if not start or not session_token:
            measurement["status"] = "awaiting_manager_measurement_booking"
            measurement["address"] = address
            data["measurement"] = measurement
            lead.extracted_data = json.dumps(data, ensure_ascii=False)
            await db.commit()
            await self._send_and_store(
                db,
                lead,
                chat_id,
                "Адрес записал. Передам менеджеру, чтобы он закрепил удобное окно вручную.",
                "whatsapp_measurement_manual_booking_required",
            )
            return True

        phone = lead.phone or normalize_phone(chat_id)
        contact = QuizContact(name=lead.full_name or "Клиент WhatsApp", phone=phone)
        booking, _ = await quiz_service.book_measurement(
            db=db,
            payload=MeasurementBookingRequest(
                session_token=session_token,
                lead_id=lead.id,
                start=start,
                address=address,
                contact=contact,
                metadata={
                    "source": "whatsapp_slot_choice",
                    "selected_messenger": "whatsapp",
                    "selected_slot_label": measurement.get("selected_slot_label"),
                },
            ),
        )
        booking_uid = quiz_service.extract_booking_uid(booking)
        status_line = "Бронь закреплена в календаре." if booking_uid else "Заявку на замер сохранил, менеджер проверит бронь."
        await self._send_and_store(
            db,
            lead,
            chat_id,
            (
                "Готово, записали вас на бесплатный осмотр.\n\n"
                f"Дата: {measurement.get('selected_slot_label') or start}\n"
                f"Адрес: {address}\n\n"
                f"{status_line} За сутки до даты напомним вам."
            ),
            "whatsapp_measurement_booked",
        )
        return True

    async def _send_and_store(self, db: AsyncSession, lead: Lead, chat_id: str, text: str, message_type: str) -> None:
        try:
            result = await whatsapp_transport_service.send_text(chat_id=chat_id, text=text)
        except WhatsAppTransportError:
            logger.warning("Failed to send WhatsApp measurement reply for lead %s", lead.id, exc_info=True)
            return

        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            sender_name="Bot",
            ai_metadata={
                "source": "whatsapp_measurement_flow",
                "type": message_type,
                "provider": result.provider,
                "external_message_id": result.message_id,
                "external_chat_id": result.chat_id,
            },
            status=MessageStatus.SENT,
            transport=MessageTransport.WHATSAPP,
        )

    def _selected_slot(self, measurement: dict[str, Any], text: str) -> dict[str, Any] | None:
        match = re.search(r"\b([1-5])\b", text)
        if not match:
            return None
        index = int(match.group(1))
        slots = measurement.get("offered_slots") if isinstance(measurement.get("offered_slots"), list) else []
        for slot in slots:
            if isinstance(slot, dict) and int(slot.get("index") or 0) == index:
                return slot
        return None

    def _looks_like_manual_time_preference(self, text: str) -> bool:
        normalized = text.casefold()
        return bool(
            re.search(r"\b\d{1,2}[:.]\d{2}\b", normalized)
            or re.search(r"\b\d{1,2}\s*(янв|фев|мар|апр|мая|май|июн|июл|авг|сен|окт|ноя|дек)", normalized)
            or any(word in normalized for word in ("сегодня", "завтра", "послезавтра", "понедельник", "вторник", "сред", "четверг", "пятниц", "суббот", "воскрес"))
        )

    def _store_measurement_state(self, lead: Lead, patch: dict[str, Any]) -> None:
        data = self._parse_data(lead.extracted_data)
        measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
        data["measurement"] = {**measurement, **patch}
        lead.extracted_data = json.dumps(data, ensure_ascii=False)

    def _measurement_address(self, data: dict[str, Any], measurement: dict[str, Any]) -> str:
        candidates = [
            measurement.get("address"),
            data.get("measurement_address"),
            data.get("address"),
            data.get("object_address"),
        ]
        return next((str(value).strip() for value in candidates if str(value or "").strip()), "")

    def _slot_label(self, slot: Any) -> str:
        date_label = str(getattr(slot, "date_label", "") or "").strip()
        time_label = str(getattr(slot, "label", "") or "").strip()
        return " ".join(part for part in (date_label, time_label) if part) or str(getattr(slot, "start", ""))

    def _parse_data(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


whatsapp_measurement_flow_service = WhatsAppMeasurementFlowService()
