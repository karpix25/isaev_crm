import { Info } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { CompanyFact, CompanyFactPayload } from '@/types'
import { CompanyFactsList } from './companyFacts/CompanyFactsList'
import { FactsSectionForm } from './companyFacts/FactsSectionForm'
import { FACT_SECTIONS, type FactSection } from './companyFacts/factTemplates'

export function CompanyFactsManager({
    facts,
    isLoading,
    isSaving,
    onCreate,
    onUpdate,
    onDelete,
}: {
    facts: CompanyFact[]
    isLoading: boolean
    isSaving: boolean
    onCreate: (payload: CompanyFactPayload) => void
    onUpdate: (id: string, payload: Partial<CompanyFactPayload>) => void
    onDelete: (id: string) => void
}) {
    const [activeSection, setActiveSection] = useState<FactSection>(FACT_SECTIONS[0])
    const sectionFacts = useMemo(
        () => facts.filter((fact) => fact.category === activeSection.category),
        [facts, activeSection.category]
    )

    return (
        <div className="space-y-6">
            <div>
                <h3 className="text-xl font-bold">Факты компании</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                    Широкие смысловые блоки для ИИ: цены, сметы, портфолио, замер, услуги и компания.
                    Пишите обычным языком, а технические ключи создаются автоматически.
                </p>
            </div>

            <div className="rounded-2xl border bg-blue-50 p-4 text-sm text-blue-900">
                <div className="flex items-start gap-2">
                    <Info className="mt-0.5 h-4 w-4 shrink-0" />
                    <div>
                        <div className="font-bold">Как пользоваться</div>
                        <p className="mt-1">
                            Выберите раздел и опишите правила свободным текстом: ссылки, исключения, сроки, что можно обещать,
                            а что нельзя. Это не анкета, а управляемая память компании для точных ответов.
                        </p>
                    </div>
                </div>
            </div>

            <FactsSectionForm
                activeSection={activeSection}
                facts={facts}
                isSaving={isSaving}
                onSectionChange={setActiveSection}
                onCreate={onCreate}
                onUpdate={onUpdate}
            />

            <div>
                <h4 className="mb-3 text-base font-bold">Сохранено в разделе “{activeSection.label}”</h4>
                <CompanyFactsList
                    facts={sectionFacts}
                    isLoading={isLoading}
                    isSaving={isSaving}
                    onUpdate={onUpdate}
                    onDelete={onDelete}
                />
            </div>
        </div>
    )
}
