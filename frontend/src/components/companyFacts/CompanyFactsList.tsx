import { Save, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { CompanyFact, CompanyFactPayload } from '@/types'

const INPUT_CLASS = "w-full rounded-lg border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"

export function CompanyFactsList({
    facts,
    isLoading,
    isSaving,
    onUpdate,
    onDelete,
}: {
    facts: CompanyFact[]
    isLoading: boolean
    isSaving: boolean
    onUpdate: (id: string, payload: Partial<CompanyFactPayload>) => void
    onDelete: (id: string) => void
}) {
    if (isLoading) {
        return <div className="text-sm text-muted-foreground">Загрузка...</div>
    }

    if (!facts.length) {
        return (
            <div className="rounded-2xl border border-dashed p-5 text-sm text-muted-foreground">
                Пока нет сохраненных фактов. Заполните нужные поля выше, и они появятся здесь.
            </div>
        )
    }

    return (
        <div className="space-y-3">
            {facts.map((fact) => (
                <FactRow key={fact.id} fact={fact} isSaving={isSaving} onUpdate={onUpdate} onDelete={onDelete} />
            ))}
        </div>
    )
}

function FactRow({
    fact,
    isSaving,
    onUpdate,
    onDelete,
}: {
    fact: CompanyFact
    isSaving: boolean
    onUpdate: (id: string, payload: Partial<CompanyFactPayload>) => void
    onDelete: (id: string) => void
}) {
    const [value, setValue] = useState(fact.value)

    useEffect(() => {
        setValue(fact.value)
    }, [fact.value])

    return (
        <div className="rounded-2xl border bg-white p-4">
            <div className="flex items-start justify-between gap-3">
                <div>
                    <div className="font-bold">{fact.title}</div>
                    <div className="text-xs text-muted-foreground">{fact.category} · {fact.priority === 'core' ? 'важный факт' : 'по ситуации'}</div>
                </div>
                <div className="flex gap-2">
                    <button disabled={isSaving} onClick={() => onUpdate(fact.id, { value })} className="rounded-lg border p-2">
                        <Save className="h-4 w-4" />
                    </button>
                    <button disabled={isSaving} onClick={() => onDelete(fact.id)} className="rounded-lg border p-2 text-red-600">
                        <Trash2 className="h-4 w-4" />
                    </button>
                </div>
            </div>
            <textarea value={value} onChange={(event) => setValue(event.target.value)} className={`${INPUT_CLASS} mt-3 min-h-20`} />
            {fact.hint && <div className="mt-2 text-xs text-muted-foreground">{fact.hint}</div>}
        </div>
    )
}
