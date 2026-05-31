import type { CompanyFact, CompanyFactPayload } from '@/types'
import { useEffect, useState } from 'react'
import type { ChangeEvent } from 'react'
import { FACT_SECTIONS, type FactSection, templateToPayload } from './factTemplates'

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
    const factsByKey = new Map(facts.map((fact) => [fact.key, fact]))

    const saveField = (templateKey: string, value: string) => {
        const template = activeSection.fields.find((field) => field.key === templateKey)
        if (!template) return

        const existing = factsByKey.get(template.key)
        if (!value && !existing) return
        if (!value && existing) {
            onUpdate(existing.id, { value: '', is_active: false })
            return
        }

        const payload = templateToPayload(template, value)
        if (existing) {
            onUpdate(existing.id, { ...payload, is_active: true })
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
                    <h4 className="text-lg font-bold">{activeSection.label}</h4>
                    <p className="mt-1 text-sm text-muted-foreground">{activeSection.description}</p>
                </div>

                <div className="mt-5 grid gap-4">
                    {activeSection.fields.map((template) => (
                        <FactInput
                            key={template.key}
                            label={template.label}
                            help={template.help}
                            placeholder={template.placeholder}
                            multiline={template.multiline}
                            defaultValue={factsByKey.get(template.key)?.value || ''}
                            disabled={isSaving}
                            onSave={(value) => saveField(template.key, value)}
                        />
                    ))}
                </div>
            </section>
        </div>
    )
}

function FactInput({
    label,
    help,
    placeholder,
    multiline,
    defaultValue,
    disabled,
    onSave,
}: {
    label: string
    help: string
    placeholder: string
    multiline?: boolean
    defaultValue: string
    disabled: boolean
    onSave: (value: string) => void
}) {
    const [value, setValue] = useState(defaultValue)

    useEffect(() => {
        setValue(defaultValue)
    }, [defaultValue])

    const inputProps = {
        value,
        onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setValue(event.target.value),
        placeholder,
        className: `${INPUT_CLASS} ${multiline ? 'min-h-24' : ''}`,
    }

    return (
        <label className="block rounded-xl border bg-background/60 p-4">
            <div className="flex items-start justify-between gap-3">
                <div>
                    <div className="text-sm font-bold">{label}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{help}</div>
                </div>
                <button
                    type="button"
                    disabled={disabled}
                    onClick={() => onSave(value.trim())}
                    className="shrink-0 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground disabled:opacity-50"
                >
                    Сохранить
                </button>
            </div>
            <div className="mt-3">
                {multiline ? <textarea {...inputProps} /> : <input {...inputProps} />}
            </div>
        </label>
    )
}
