from __future__ import annotations

import base64
import mimetypes
import os
import uuid

from src.services.whatsapp.types import WhatsAppAttachment


class WhatsAppMediaStorage:
    def save_base64_attachment(self, attachment: WhatsAppAttachment) -> str | None:
        if not attachment.data_base64:
            return None

        payload = attachment.data_base64
        if "," in payload and payload.strip().startswith("data:"):
            payload = payload.split(",", 1)[1]

        try:
            content = base64.b64decode(payload, validate=True)
        except Exception:
            return None

        extension = self._extension(attachment)
        media_dir = os.path.join(os.getcwd(), "media", "whatsapp")
        os.makedirs(media_dir, exist_ok=True)
        stored_name = f"{uuid.uuid4()}{extension}"
        full_path = os.path.join(media_dir, stored_name)
        with open(full_path, "wb") as out:
            out.write(content)
        return f"/media/whatsapp/{stored_name}"

    def _extension(self, attachment: WhatsAppAttachment) -> str:
        if attachment.filename:
            _, ext = os.path.splitext(attachment.filename)
            if ext:
                return ext.lower()
        if attachment.mimetype:
            guessed = mimetypes.guess_extension(attachment.mimetype)
            if guessed:
                return guessed
        return ".bin"


whatsapp_media_storage = WhatsAppMediaStorage()
