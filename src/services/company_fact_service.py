from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.company_fact import CompanyFact


class CompanyFactService:
    async def list_facts(
        self,
        db: AsyncSession,
        org_id: UUID,
        *,
        active_only: bool = False,
    ) -> list[CompanyFact]:
        query = select(CompanyFact).where(CompanyFact.org_id == org_id)
        if active_only:
            query = query.where(CompanyFact.is_active == True)
        query = query.order_by(CompanyFact.category, CompanyFact.display_order, CompanyFact.created_at)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_fact(self, db: AsyncSession, org_id: UUID, fact_id: UUID) -> CompanyFact | None:
        result = await db.execute(
            select(CompanyFact).where(CompanyFact.org_id == org_id, CompanyFact.id == fact_id)
        )
        return result.scalar_one_or_none()

    async def build_prompt_section(
        self,
        db: AsyncSession,
        org_id: UUID,
        *,
        stage: str | None = None,
        message: str | None = None,
        limit: int = 18,
    ) -> str:
        facts = await self.list_facts(db, org_id, active_only=True)
        selected = self.select_relevant(facts, stage=stage, message=message, limit=limit)
        if not selected:
            return ""

        lines = ["\n\nСТРУКТУРИРОВАННЫЕ ФАКТЫ КОМПАНИИ (точный источник правды):"]
        for fact in selected:
            suffix = f" [{fact.hint.strip()}]" if fact.hint else ""
            lines.append(f"- {fact.title} (`{fact.key}`): {fact.value}{suffix}")
        lines.append(
            "Правило: если факт выше противоречит RAG или общему промпту, используй структурированный факт."
        )
        return "\n".join(lines)

    def select_relevant(
        self,
        facts: Iterable[CompanyFact],
        *,
        stage: str | None,
        message: str | None,
        limit: int,
    ) -> list[CompanyFact]:
        message_lc = (message or "").lower()
        stage_value = (stage or "").strip()
        scored: list[tuple[int, CompanyFact]] = []

        for fact in facts:
            score = 100 if fact.priority == "core" else 0
            if stage_value and stage_value in (fact.stages or []):
                score += 40
            if self._matches(message_lc, fact.tags):
                score += 25
            if self._matches(message_lc, fact.questions):
                score += 35
            if score > 0:
                scored.append((score, fact))

        scored.sort(key=lambda item: (-item[0], item[1].display_order, item[1].title))
        return [fact for _, fact in scored[:limit]]

    def _matches(self, message: str, values: list[str] | None) -> bool:
        if not message or not values:
            return False
        return any(str(value).lower().strip() and str(value).lower().strip() in message for value in values)


company_fact_service = CompanyFactService()
