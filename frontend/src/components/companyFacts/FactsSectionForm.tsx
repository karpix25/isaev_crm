import { useEffect, useMemo, useState } from 'react'
import type { CompanyFact, CompanyFactPayload } from '@/types'
import { FACT_SECTIONS, type FactSection, sectionToPayload } from './factTemplates'

const INPUT_CLASS = "w-full rounded-lg border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"

type Props = {
    activeSection: FactSection
    facts: CompanyFact[]
    isSaving: boolean
    onSectionChange: (section: FactSection) => void
    onCreate: (payload: CompanyFactPayload) => void
    onUpdate: (id: string, payload: Partial<CompanyFactPayload>) => void
}

export function FactsSectionForm({
    activeSection,
    facts,
    isSaving,
    onSectionChange,
    onCreate,
    onUpdate,
}: Props) {
    const sectionFact = useMemo(
        () => facts.find((fact) => fact.key === activeSection.key),
        [facts, activeSection.key]
    )
    const [value, setValue] = useState(sectionFact?.value || '')

    useEffect(() => {
        setValue(sectionFact?.value || '')
    }, [sectionFact?.id, sectionFact?.value])

    const saveSection = () => {
        const trimmed = value.trim()
        if (!trimmed && !sectionFact) return
        if (!trimmed && sectionFact) {
            onUpdate(sectionFact.id, { value: '', is_active: false })
            return
        }

        const payload = sectionToPayload(activeSection, trimmed)
        if (sectionFact) {
            onUpdate(sectionFact.id, { ...payload, is_active: true })
            return
        }
        onCreate(payload)
    }

    return (
        <div className="grid gap-5 lg:grid-cols-[220px_1fr]">
            <aside className="space-y-2">
                {FACT_SECTIONS.map((section) => (
                    <button
                        key={section.category}
                        type="button"
                        onClick={() => onSectionChange(section)}
                        className={`w-full rounded-xl border px-3 py-2 text-left text-sm font-semibold transition-colors ${section.category === activeSection.category
                            ? 'border-primary bg-primary text-primary-foreground'
                            : 'bg-background hover:bg-accent'
                            }`}
                    >
                        {section.label}
                    </button>
                ))}
            </aside>

            <section className="rounded-2xl border bg-card p-5">
                <div>
                    <h4 className="text-lg font-bold">{activeSection.title}</h4>
                    <p className="mt-1 text-sm text-muted-foreground">{activeSection.description}</p>
                </div>

                <div className="mt-4 rounded-xl border bg-blue-50 p-4 text-sm text-blue-900">
                    {activeSection.help}
                </div>

                <textarea
                    value={value}
                    onChange={(event) => setValue(event.target.value)}
                    placeholder={activeSection.placeholder}
                    className={`${INPUT_CLASS} mt-4 min-h-56 leading-6`}
                />

                <div className="mt-4 flex items-center justify-between gap-3">
                    <p className="text-xs text-muted-foreground">
                        Можно писать свободно: ссылки, правила, исключения, тон ответа. Это попадет в ИИ как источник правды.
                    </p>
                    <button
                        type="button"
                        disabled={isSaving}
                        onClick={saveSection}
                        className="shrink-0 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
                    >
                        Сохранить раздел
                    </button>
                </div>
            </section>
        </div>
    )
}
