from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime
import uuid

from src.models import Lead, ChatMessage, MessageDirection, MessageStatus
from src.schemas.chat import ChatMessageCreate


class ChatService:
    """Service for managing chat messages"""
    
    @staticmethod
    async def save_incoming_message(
        db: AsyncSession,
        lead_id: uuid.UUID,
        content: str,
        telegram_message_id: Optional[int] = None,
        media_url: Optional[str] = None,
        sender_name: Optional[str] = None,
        ai_metadata: Optional[dict] = None
    ) -> ChatMessage:
        """
        Save incoming message from Telegram user (lead).
        Also updates lead's last_message_at and unread_count.
        """
        # Create message
        message = ChatMessage(
            lead_id=lead_id,
            direction=MessageDirection.INBOUND,
            content=content,
            telegram_message_id=telegram_message_id,
            media_url=media_url,
            sender_name=sender_name,
            is_read=False,
            ai_metadata=ai_metadata
        )
        
        db.add(message)
        
        # Update lead's last message time, increment unread count, and reset follow-up counter
        await db.execute(
            update(Lead)
            .where(Lead.id == lead_id)
            .values(
                last_message_at=datetime.utcnow(),
                unread_count=Lead.unread_count + 1,
                followup_count=0
            )
        )
        
        await db.commit()
        await db.refresh(message)
        
        return message
    
    @staticmethod
    async def send_outbound_message(
        db: AsyncSession,
        lead_id: uuid.UUID,
        content: str,
        media_url: Optional[str] = None,
        telegram_message_id: Optional[int] = None,
        sender_name: str = "Admin",
        ai_metadata: Optional[dict] = None,
        status: MessageStatus = MessageStatus.PENDING
    ) -> ChatMessage:
        """
        Save outbound message from admin or AI to lead.
        Also updates lead's last_message_at.
        """
        # Create message
        message = ChatMessage(
            lead_id=lead_id,
            direction=MessageDirection.OUTBOUND,
            content=content,
            media_url=media_url,
            telegram_message_id=telegram_message_id,
            is_read=True,  # Outbound messages are always "read"
            sender_name=sender_name,
            ai_metadata=ai_metadata,
            status=status
        )
        
        db.add(message)
        
        # Update lead's last message time
        await db.execute(
            update(Lead)
            .where(Lead.id == lead_id)
            .values(last_message_at=datetime.utcnow())
        )
        
        await db.commit()
        await db.refresh(message)
        
        return message
    
    @staticmethod
    async def get_chat_history(
        db: AsyncSession,
        lead_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50
    ) -> tuple[List[ChatMessage], int]:
        """
        Get paginated chat history for a lead.
        Returns (messages, total_count).
        """
        # Get total count
        count_result = await db.execute(
            select(func.count(ChatMessage.id))
            .where(ChatMessage.lead_id == lead_id)
        )
        total = count_result.scalar_one()
        
        # Get messages (ordered by created_at DESC for latest first)
        offset = (page - 1) * page_size
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.lead_id == lead_id)
            .order_by(ChatMessage.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        messages = result.scalars().all()
        
        return list(messages), total
    
    @staticmethod
    async def mark_messages_as_read(
        db: AsyncSession,
        lead_id: uuid.UUID
    ) -> int:
        """
        Mark all unread messages from a lead as read.
        Returns count of updated messages.
        """
        result = await db.execute(
            update(ChatMessage)
            .where(
                ChatMessage.lead_id == lead_id,
                ChatMessage.direction == MessageDirection.INBOUND,
                ChatMessage.is_read == False
            )
            .values(is_read=True)
        )
        
        # Reset lead's unread count
        await db.execute(
            update(Lead)
            .where(Lead.id == lead_id)
            .values(unread_count=0)
        )
        
        await db.commit()
        
        return result.rowcount
    
    @staticmethod
    async def get_unread_count(
        db: AsyncSession,
        org_id: uuid.UUID
    ) -> int:
        """Get total unread message count for an organization"""
        result = await db.execute(
            select(func.sum(Lead.unread_count))
            .where(Lead.org_id == org_id)
        )
        total = result.scalar_one_or_none()
        return total or 0


# Global instance
chat_service = ChatService()
