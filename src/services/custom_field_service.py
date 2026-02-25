"""
Service for dynamically building AI prompts with custom fields.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, List
from uuid import UUID

from src.models import CustomField


async def get_custom_fields_for_org(db: AsyncSession, org_id: UUID) -> List[CustomField]:
    """
    Fetch all active custom fields for an organization.
    """
    result = await db.execute(
        select(CustomField)
        .where(CustomField.org_id == org_id)
        .where(CustomField.is_active == True)
        .order_by(CustomField.display_order, CustomField.created_at)
    )
    return result.scalars().all()


def build_custom_fields_section(custom_fields: List[CustomField]) -> str:
    """
    Build the custom fields section for the AI prompt.
    
    Returns a formatted string describing custom fields to collect.
    """
    if not custom_fields:
        return ""
    
    lines = ["\n\nДОПОЛНИТЕЛЬНЫЕ ПОЛЯ ДЛЯ СБОРА (СПРАШИВАЙ ПО КОНТЕКСТУ):"]
    
    for idx, field in enumerate(custom_fields, start=1):
        field_desc = f"{idx}. **{field.field_label}** (`{field.field_name}`)"
        
        if field.field_type == "select" and field.options:
            field_desc += f" [Варианты: {', '.join(field.options)}]"
        elif field.field_type == "boolean":
            field_desc += " [Тип: да/нет]"
        elif field.field_type == "number":
            field_desc += " [Тип: число]"
        
        if field.description:
            # Explicitly highlight the purpose/logic for the AI
            field_desc += f"\n   - ЦЕЛЬ/ПОДСКАЗКА: {field.description}"
        
        lines.append(field_desc)
    
    lines.append("\nИнструкция для AI: Не спрашивай всё сразу. Вплетай эти вопросы в диалог, когда это логично (например, после обсуждения площади или типа объекта).")
    
    return "\n".join(lines)


def build_custom_fields_json_schema(custom_fields: List[CustomField]) -> str:
    """
    Build the JSON schema section for custom fields.
    
    Returns a formatted string with JSON field definitions.
    """
    if not custom_fields:
        return ""
    
    lines = []
    for field in custom_fields:
        if field.field_type == "boolean":
            lines.append(f'  "{field.field_name}": boolean или null,')
        elif field.field_type == "number":
            lines.append(f'  "{field.field_name}": "число или null",')
        else:
            lines.append(f'  "{field.field_name}": "значение или null",')
    
    return "\n".join(lines)


async def enrich_system_prompt(
    db: AsyncSession,
    org_id: str,
    base_prompt: str
) -> str:
    """
    Enrich the system prompt with current CRM statuses and custom fields.
    
    This function:
    1. Fetches current LeadStatus enum values.
    2. Fetches active custom fields for the organization.
    3. Injects both into the base_prompt using {crm_statuses} and {custom_fields} placeholders.
    """
    from src.models.lead import LeadStatus
    import uuid
    
    # 1. Prepare CRM Statuses section
    status_descriptions = {
        "NEW": "(Новый)",
        "CONSULTING": "(Консультация)",
        "FOLLOW_UP": "(Думает/дорого)",
        "QUALIFIED": "(Есть телефон/проект)",
        "MEASUREMENT": "(Договорились о замере)",
        "ESTIMATE": "(Подготовка сметы)",
        "CONTRACT": "(Подписание договора)",
        "WON": "(Успешно)",
        "LOST": "(Отказ)",
        "SPAM": "(Реклама/спам)"
    }
    
    statuses_lines = []
    for status in LeadStatus:
        desc = status_descriptions.get(status.value, "")
        statuses_lines.append(f"- {status.value} {desc}")
    
    crm_statuses_text = "\n".join(statuses_lines)
    
    # 2. Prepare Custom Fields section
    try:
        org_uuid = uuid.UUID(str(org_id))
        custom_fields = await get_custom_fields_for_org(db, org_uuid)
    except Exception:
        custom_fields = []
        
    custom_fields_text = ""
    json_schema_text = ""
    
    if custom_fields:
        custom_fields_text = build_custom_fields_section(custom_fields)
        json_schema_text = build_custom_fields_json_schema(custom_fields)
    
    # 3. Inject into prompt
    enhanced_prompt = base_prompt.replace("{crm_statuses}", crm_statuses_text)
    
    # Custom fields injection
    if custom_fields_text:
        enhanced_prompt = enhanced_prompt.replace("{custom_fields}", custom_fields_text)
        
        # Also inject into technical JSON format if we can find it
        placeholder = 'ТЕХНИЧЕСКИЙ ВЫВОД: Always respond in VALID JSON format.'
        if placeholder in enhanced_prompt:
            enhanced_prompt = enhanced_prompt.replace(
                placeholder,
                f"В ДОПОЛНЕНИЕ К СТАНДАРТНЫМ ПОЛЯМ, ОБЯЗАТЕЛЬНО ВКЛЮЧИ В JSON:\n{json_schema_text}\n\n{placeholder}"
            )
    else:
        enhanced_prompt = enhanced_prompt.replace("{custom_fields}", "")
        
    return enhanced_prompt
