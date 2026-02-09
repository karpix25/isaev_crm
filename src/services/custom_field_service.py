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
    
    lines = ["\n\nКАСТОМНЫЕ ПОЛЯ ДЛЯ СБОРА:"]
    
    for idx, field in enumerate(custom_fields, start=1):
        field_desc = f"{idx}. **{field.field_label}** ({field.field_name})"
        
        if field.field_type == "select" and field.options:
            field_desc += f" - варианты: {', '.join(field.options)}"
        elif field.field_type == "boolean":
            field_desc += " - да/нет"
        elif field.field_type == "number":
            field_desc += " - число"
        
        if field.description:
            field_desc += f" - {field.description}"
        
        lines.append(field_desc)
    
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


async def inject_custom_fields_into_prompt(
    db: AsyncSession,
    org_id: UUID,
    base_prompt: str
) -> str:
    """
    Inject custom fields into the system prompt.
    
    This function:
    1. Fetches active custom fields for the organization
    2. Builds the custom fields section
    3. Builds the JSON schema section
    4. Injects both into the base prompt
    
    Args:
        db: Database session
        org_id: Organization ID
        base_prompt: The base system prompt
    
    Returns:
        Enhanced prompt with custom fields injected
    """
    custom_fields = await get_custom_fields_for_org(db, org_id)
    
    if not custom_fields:
        return base_prompt
    
    # Build sections
    fields_section = build_custom_fields_section(custom_fields)
    json_schema = build_custom_fields_json_schema(custom_fields)
    
    # Find injection points
    # 1. After standard fields section (before JSON format)
    if "ФОРМАТ ОТВЕТА" in base_prompt:
        parts = base_prompt.split("ФОРМАТ ОТВЕТА")
        enhanced_prompt = parts[0] + fields_section + "\n\nФОРМАТ ОТВЕТА" + parts[1]
    else:
        # Fallback: append at the end before JSON
        enhanced_prompt = base_prompt + fields_section
    
    # 2. Inject into JSON schema (before closing brace)
    if '"is_hot_lead": boolean' in enhanced_prompt:
        enhanced_prompt = enhanced_prompt.replace(
            '"is_hot_lead": boolean',
            f'"is_hot_lead": boolean,\n{json_schema}'
        )
    
    return enhanced_prompt
