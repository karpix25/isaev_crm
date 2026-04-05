from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional, List
import uuid
import json

from src.models import Lead, LeadStatus
from src.schemas.lead import LeadCreate, LeadUpdate


class LeadService:
    """Service for managing leads"""
    
    @staticmethod
    async def create_or_get_lead(
        db: AsyncSession,
        org_id: uuid.UUID,
        telegram_id: int,
        full_name: Optional[str] = None,
        username: Optional[str] = None,
        avatar_url: Optional[str] = None,
        source: str = "telegram"
    ) -> Lead:
        """
        Find existing lead by telegram_id or create new one.
        Returns the lead instance.
        """
        # Try to find existing lead
        result = await db.execute(
            select(Lead).where(Lead.telegram_id == telegram_id)
        )
        lead = result.scalar_one_or_none()
        
        if lead:
            # Update info if provided and different
            updated = False
            if full_name and lead.full_name != full_name:
                lead.full_name = full_name
                updated = True
            if username and lead.username != username:
                lead.username = username
                updated = True
            if avatar_url and lead.avatar_url != avatar_url:
                lead.avatar_url = avatar_url
                updated = True
            
            # If lead exists but source is different (e.g. was website, now telegram), 
            # we generally keep original source or update logic? 
            # For now, let's keep original source to know where they FIRST came from.
            
            if updated:
                await db.commit()
                await db.refresh(lead)
            return lead
        
        # Create new lead
        lead = Lead(
            org_id=org_id,
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            status=LeadStatus.NEW,
            source=source,
            avatar_url=avatar_url
        )
        
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        
        return lead
        
    @staticmethod
    async def create_manual_lead(
        db: AsyncSession,
        org_id: uuid.UUID,
        full_name: Optional[str] = None,
        phone: Optional[str] = None,
        username: Optional[str] = None,
        source: str = "CRM"
    ) -> Lead:
        """Create a new manual lead from CRM, resolving Telegram by username and/or phone when possible."""
        resolved_telegram_id = None
        clean_username = None
        resolved_full_name = full_name
        messenger_presence: dict[str, bool] = {}
        whatsapp_wa_id: Optional[str] = None

        from src.services.user_bot_service import user_bot_service
        import logging
        logger = logging.getLogger(__name__)
        source_upper = (source or "").strip().upper()
        allow_messenger_lookup = "IMPORT" not in source_upper and "BULK" not in source_upper

        # 1) Resolve by username first (explicit user input has priority)
        if username and allow_messenger_lookup:
            clean_username = username.strip()
            if clean_username.startswith('@'):
                clean_username = clean_username[1:]

            try:
                resolved_telegram_id = await user_bot_service.resolve_username(db, org_id, clean_username)
            except Exception as e:
                logger.error(f"Failed to resolve username {clean_username} during manual creation: {e}")

        # 2) Resolve by phone (requested behavior for manual lead creation)
        #    Fill missing telegram_id/username/full_name if found.
        if phone and allow_messenger_lookup:
            try:
                phone_lookup = await user_bot_service.resolve_phone(db, org_id, phone)
                if phone_lookup:
                    telegram_active = phone_lookup.get("active")
                    if telegram_active is not None:
                        messenger_presence["telegram"] = bool(telegram_active)

                    phone_tg_id = phone_lookup.get("telegram_id")
                    if resolved_telegram_id and phone_tg_id and str(resolved_telegram_id) != str(phone_tg_id):
                        logger.warning(
                            "Manual lead resolve mismatch for org %s: username->%s, phone->%s",
                            org_id,
                            resolved_telegram_id,
                            phone_tg_id,
                        )
                    elif not resolved_telegram_id and phone_tg_id:
                        resolved_telegram_id = phone_tg_id

                    if not clean_username and phone_lookup.get("username"):
                        clean_username = phone_lookup.get("username")

                    if not resolved_full_name and phone_lookup.get("full_name"):
                        resolved_full_name = phone_lookup.get("full_name")
            except Exception as e:
                logger.error(f"Failed to resolve phone {phone} during manual creation: {e}")

            try:
                whatsapp_lookup = await user_bot_service.resolve_whatsapp(org_id, phone)
                if whatsapp_lookup and whatsapp_lookup.get("active") is not None:
                    messenger_presence["whatsapp"] = bool(whatsapp_lookup.get("active"))
                    whatsapp_wa_id = whatsapp_lookup.get("wa_id")
            except Exception as e:
                logger.error(f"Failed to resolve WhatsApp for phone {phone} during manual creation: {e}")

        extracted_data = {}
        if messenger_presence:
            extracted_data["messengers"] = messenger_presence
        if whatsapp_wa_id:
            extracted_data["whatsapp_wa_id"] = whatsapp_wa_id

        lead = Lead(
            org_id=org_id,
            telegram_id=resolved_telegram_id,
            username=clean_username,
            full_name=resolved_full_name,
            phone=phone,
            status=LeadStatus.NEW,
            source=source,
            extracted_data=json.dumps(extracted_data, ensure_ascii=False) if extracted_data else None
        )
        
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        
        return lead
    
    @staticmethod
    async def update_lead_status(
        db: AsyncSession,
        lead_id: uuid.UUID,
        status: LeadStatus
    ) -> Lead:
        """Update lead status"""
        result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        lead = result.scalar_one()
        
        lead.status = status
        await db.commit()
        await db.refresh(lead)
        
        return lead
    
    @staticmethod
    async def update_lead(
        db: AsyncSession,
        lead_id: uuid.UUID,
        **kwargs
    ) -> Lead:
        """
        Update lead with arbitrary fields.
        Supports: status, ai_qualification_status, extracted_data, ai_summary, etc.
        """
        result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        lead = result.scalar_one()
        
        # Update provided fields
        for key, value in kwargs.items():
            if hasattr(lead, key) and value is not None:
                setattr(lead, key, value)
        
        await db.commit()
        await db.refresh(lead)
        
        return lead
    
    @staticmethod
    async def get_leads_by_org(
        db: AsyncSession,
        org_id: uuid.UUID,
        status: Optional[LeadStatus] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[Lead], int]:
        """
        Get paginated leads for an organization with optional filters.
        Returns (leads, total_count).
        """
        # Build query
        query = select(Lead).where(Lead.org_id == org_id)
        
        # Apply filters
        if status:
            query = query.where(Lead.status == status)
            
        if source:
            query = query.where(Lead.source == source)        
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Lead.full_name.ilike(search_pattern),
                    Lead.phone.ilike(search_pattern),
                    Lead.username.ilike(search_pattern)
                )
            )
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()
        
        # Get paginated results (ordered by last_message_at DESC)
        offset = (page - 1) * page_size
        query = query.order_by(Lead.last_message_at.desc().nullslast()).offset(offset).limit(page_size)
        
        result = await db.execute(query)
        leads = result.scalars().all()
        
        return list(leads), total
    
    @staticmethod
    async def get_lead_by_id(
        db: AsyncSession,
        lead_id: uuid.UUID
    ) -> Optional[Lead]:
        """Get lead by ID"""
        result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def delete_lead(
        db: AsyncSession,
        lead_id: uuid.UUID
    ) -> bool:
        """Delete lead and all associated chat messages"""
        result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        lead = result.scalar_one_or_none()
        
        if not lead:
            return False
        
        await db.delete(lead)
        await db.commit()
        
        return True

    @staticmethod
    async def bulk_delete_leads(
        db: AsyncSession,
        org_id: uuid.UUID,
        lead_ids: List[uuid.UUID]
    ) -> int:
        """
        Bulk delete leads by IDs within an organization.
        Returns number of deleted leads.
        """
        if not lead_ids:
            return 0

        unique_ids = list(dict.fromkeys(lead_ids))
        result = await db.execute(
            select(Lead).where(
                Lead.org_id == org_id,
                Lead.id.in_(unique_ids)
            )
        )
        leads_to_delete = result.scalars().all()
        deleted = 0
        for lead in leads_to_delete:
            await db.delete(lead)
            deleted += 1

        await db.commit()
        return deleted


# Global instance
lead_service = LeadService()
