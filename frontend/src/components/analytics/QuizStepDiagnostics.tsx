import type { QuizStepMetric } from '@/types'

export function QuizStepDiagnostics({ steps }: { steps: QuizStepMetric[] }) {
    if (steps.length === 0) {
        return (
            <section className="rounded-lg border bg-card p-5">
                <h3 className="text-lg font-semibold">Диагностика вопросов квиза</h3>
                <p className="py-8 text-center text-sm text-muted-foreground">Пока нет данных по вопросам</p>
            </section>
        )
    }

    const worstStep = [...steps].sort((a, b) => b.dropoffs_after_view - a.dropoffs_after_view)[0]

    return (
        <section className="rounded-lg border bg-card p-5">
            <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <h3 className="text-lg font-semibold">Диагностика вопросов квиза</h3>
                    <p className="text-sm text-muted-foreground">Показывает, где человек увидел вопрос, но не дал ответ</p>
                </div>
                {worstStep && worstStep.dropoffs_after_view > 0 && (
                    <div className="rounded-md bg-red-500/10 px-3 py-2 text-sm text-red-700">
                        Больше всего потерь: {worstStep.label} ({worstStep.dropoffs_after_view})
                    </div>
                )}
            </div>

            <div className="overflow-x-auto rounded-md border">
                <table className="w-full min-w-[900px] text-left text-sm">
                    <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
                        <tr>
                            <th className="px-4 py-3 font-medium">Вопрос</th>
                            <th className="px-4 py-3 font-medium">Увидели</th>
                            <th className="px-4 py-3 font-medium">Ответили</th>
                            <th className="px-4 py-3 font-medium">Конверсия</th>
                            <th className="px-4 py-3 font-medium">Потеря</th>
                            <th className="px-4 py-3 font-medium">Думали</th>
                            <th className="px-4 py-3 font-medium">Назад</th>
                            <th className="px-4 py-3 font-medium">Среднее время</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y">
                        {steps.map((step) => (
                            <tr key={step.step_id} className="hover:bg-muted/30">
                                <td className="px-4 py-3">
                                    <div className="font-semibold">{step.index}. {step.label}</div>
                                    <div className="text-xs text-muted-foreground">от открытия: {formatPercent(step.conversion_from_start)}</div>
                                </td>
                                <td className="px-4 py-3 font-medium">{step.viewed}</td>
                                <td className="px-4 py-3 font-medium">{step.answered}</td>
                                <td className="px-4 py-3">
                                    <div className="flex items-center gap-3">
                                        <div className="h-2 w-28 overflow-hidden rounded-full bg-muted">
                                            <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, step.answer_rate)}%` }} />
                                        </div>
                                        <span className="w-12 font-medium">{step.answer_rate}%</span>
                                    </div>
                                </td>
                                <td className="px-4 py-3">
                                    <span className={step.dropoffs_after_view > 0 ? 'font-semibold text-red-700' : 'text-muted-foreground'}>
                                        {step.dropoffs_after_view}
                                    </span>
                                </td>
                                <td className="px-4 py-3 text-muted-foreground">{step.hesitations}</td>
                                <td className="px-4 py-3 text-muted-foreground">{step.back_clicks}</td>
                                <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">
                                    {formatDuration(step.avg_time_on_step_ms)}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
    )
}

function formatPercent(value?: number | null) {
    if (value === null || value === undefined) return '-'
    return `${value}%`
}

function formatDuration(ms?: number | null) {
    if (!ms) return '-'
    if (ms < 1000) return `${ms} мс`
    return `${Math.round(ms / 100) / 10} сек`
}
