import React, { useMemo, useState } from 'react'
import { BarChart3, CheckCircle2, Link2, MessageCircle, MousePointerClick, RefreshCw, TrendingUp, Users } from 'lucide-react'
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts'
import { useAnalyticsSummary } from '@/hooks/useAnalytics'
import { formatTimeAgo } from '@/lib/utils'
import type { AnalyticsEventItem, BreakdownItem, FunnelStepMetric, MessengerMetric, QuizAnswerBreakdown } from '@/types'

const periodOptions = [
    { value: '7d', label: '7 дней' },
    { value: '30d', label: '30 дней' },
    { value: '90d', label: '90 дней' },
    { value: 'all', label: 'Все' },
]

const eventLabels: Record<string, string> = {
    quiz_opened: 'Открыл квиз',
    quiz_started: 'Начал квиз',
    answer_selected: 'Ответил',
    contact_viewed: 'Контакты',
    contact_submitted: 'Оставил контакты',
    lead_created: 'Лид создан',
    telegram_clicked: 'Telegram',
    telegram_bot_started: 'Запустил Telegram-бота',
    whatsapp_clicked: 'WhatsApp',
    telegram_message_received: 'Telegram с кодом квиза',
    whatsapp_message_received: 'WhatsApp с кодом квиза',
    telegram_linked: 'Telegram связан',
    whatsapp_linked: 'WhatsApp связан',
    design_file_uploaded: 'Проект загружен',
    design_upload_skipped: 'Проект пришлю позже',
    cal_slot_selected: 'Нажал слот',
    measurement_booked: 'Замер забронирован',
    quiz_completed: 'Квиз завершен',
    quiz_abandoned: 'Покинул квиз',
}

export function Analytics() {
    const [period, setPeriod] = useState('30d')
    const [source, setSource] = useState('')
    const [campaign, setCampaign] = useState('')

    const params = useMemo(() => {
        const next: Record<string, string> = {}
        if (period !== 'all') {
            const days = Number(period.replace('d', ''))
            const from = new Date()
            from.setDate(from.getDate() - days)
            next.date_from = from.toISOString()
        }
        if (source.trim()) next.source = source.trim()
        if (campaign.trim()) next.campaign = campaign.trim()
        return next
    }, [campaign, period, source])

    const { data, isLoading, isFetching, refetch } = useAnalyticsSummary(params)

    if (isLoading || !data) {
        return <div className="text-sm text-muted-foreground">Загрузка аналитики...</div>
    }

    const started = data.funnel.find((step) => step.key === 'quiz_started')?.count || 0
    const contactSubmitted = data.funnel.find((step) => step.key === 'contact_submitted')?.count || 0
    const measurementSlots = data.funnel.find((step) => step.key === 'cal_slot_selected')?.count || 0
    const measurementBooked = data.funnel.find((step) => step.key === 'measurement_booked')?.count || 0
    const messengerMetrics = data.messenger_metrics || []
    const messengerClicks = messengerMetrics.reduce((sum, item) => sum + item.clicks, 0)
    const messengerInbound = messengerMetrics.reduce((sum, item) => sum + item.inbound, 0)
    const messengerRate = messengerClicks ? Math.round((messengerInbound / messengerClicks) * 1000) / 10 : 0
    const contactRate = started ? Math.round((contactSubmitted / started) * 1000) / 10 : 0
    const leadRate = data.sessions_total ? Math.round((data.leads_linked / data.sessions_total) * 1000) / 10 : 0
    const abandonedRate = data.sessions_total ? Math.round((data.sessions_abandoned / data.sessions_total) * 1000) / 10 : 0

    return (
        <div className="space-y-5 pb-8">
            <section className="rounded-lg border bg-card p-5">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
                    <div>
                        <div className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Дашборд квиза</div>
                        <h2 className="mt-1 text-2xl font-semibold">Сводка по воронке и мессенджерам</h2>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-3 xl:min-w-[620px]">
                        <label className="text-sm">
                            <span className="mb-1 block text-muted-foreground">Период</span>
                            <select
                                value={period}
                                onChange={(event) => setPeriod(event.target.value)}
                                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                            >
                                {periodOptions.map((option) => (
                                    <option key={option.value} value={option.value}>{option.label}</option>
                                ))}
                            </select>
                        </label>
                        <label className="text-sm">
                            <span className="mb-1 block text-muted-foreground">Источник</span>
                            <input
                                value={source}
                                onChange={(event) => setSource(event.target.value)}
                                placeholder="telegram, yandex..."
                                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                            />
                        </label>
                        <label className="text-sm">
                            <span className="mb-1 block text-muted-foreground">Кампания</span>
                            <input
                                value={campaign}
                                onChange={(event) => setCampaign(event.target.value)}
                                placeholder="utm_campaign"
                                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                            />
                        </label>
                    </div>
                    <button
                        type="button"
                        onClick={() => refetch()}
                        className="inline-flex h-10 items-center justify-center gap-2 rounded-md border px-4 text-sm font-medium hover:bg-accent"
                    >
                        <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
                        Обновить
                    </button>
                </div>
            </section>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
                <MetricCard title="Сессии" value={data.sessions_total} hint={`Потерь: ${abandonedRate}%`} icon={MousePointerClick} tone="bg-blue-600" />
                <MetricCard title="Контакты" value={contactSubmitted} hint={`${contactRate}% от старта`} icon={Users} tone="bg-emerald-600" />
                <MetricCard title="Лиды" value={data.leads_linked} hint={`${leadRate}% от сессий`} icon={Link2} tone="bg-sky-700" />
                <MetricCard title="Мессенджеры" value={`${messengerRate}%`} hint={`${messengerInbound}/${messengerClicks} написали`} icon={MessageCircle} tone="bg-amber-600" />
                <MetricCard title="Слоты" value={measurementSlots} hint="Нажали время" icon={CheckCircle2} tone="bg-violet-600" />
                <MetricCard title="Замеры" value={measurementBooked} hint="Забронировано" icon={TrendingUp} tone="bg-emerald-700" />
            </div>

            <div className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(380px,1fr)]">
                <section className="rounded-lg border bg-card p-5">
                    <div className="mb-4 flex items-center justify-between gap-3">
                        <div>
                            <h3 className="text-lg font-semibold">Воронка по шагам</h3>
                            <p className="text-sm text-muted-foreground">Где пользователи доходят, а где отваливаются</p>
                        </div>
                        <div className="text-sm text-muted-foreground">Завершение: {data.completion_rate}%</div>
                    </div>
                    <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={data.funnel}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="label" interval={0} angle={-20} textAnchor="end" height={72} tick={{ fontSize: 11 }} />
                            <YAxis />
                            <Tooltip formatter={(value) => [value, 'Сессий']} />
                            <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                                {data.funnel.map((entry, index) => (
                                    <Cell key={entry.key} fill={index < 3 ? '#2563eb' : index < 6 ? '#059669' : '#7c3aed'} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </section>

                <section className="rounded-lg border bg-card p-5">
                    <h3 className="mb-4 text-lg font-semibold">Список шагов</h3>
                    <div className="space-y-2">
                        {data.funnel.map((step) => <FunnelRow key={step.key} step={step} />)}
                    </div>
                </section>
            </div>

            <section className="rounded-lg border bg-card p-5">
                <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <h3 className="text-lg font-semibold">Мессенджеры после квиза</h3>
                        <p className="text-sm text-muted-foreground">Считаются только сообщения с кодом заявки из квиза</p>
                    </div>
                    <div className="text-sm text-muted-foreground">Клик → сообщение с кодом: {messengerRate}%</div>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                    {messengerMetrics.map((metric) => (
                        <MessengerMetricCard key={metric.messenger} metric={metric} />
                    ))}
                </div>
            </section>

            <div className="grid gap-5 lg:grid-cols-3">
                <BreakdownPanel title="Источники" items={data.sources} />
                <BreakdownPanel title="Кампании" items={data.campaigns} />
                <BreakdownPanel title="Каналы" items={data.channels} />
            </div>

            <section className="rounded-lg border bg-card p-5">
                <h3 className="mb-4 text-lg font-semibold">Ответы в квизе</h3>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    {data.quiz_answers.map((answer) => <AnswerPanel key={answer.step_id} answer={answer} />)}
                </div>
            </section>

            <section className="rounded-lg border bg-card p-5">
                <RecentEvents events={data.recent_events} />
            </section>
        </div>
    )
}

function MetricCard({ title, value, hint, icon: Icon, tone }: { title: string; value: string | number; hint?: string; icon: React.ElementType; tone: string }) {
    return (
        <div className="rounded-lg border bg-card p-5">
            <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                    <p className="text-sm text-muted-foreground">{title}</p>
                    <p className="mt-2 text-3xl font-bold">{value}</p>
                    {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
                </div>
                <div className={`rounded-md ${tone} p-2.5`}>
                    <Icon className="h-5 w-5 text-white" />
                </div>
            </div>
        </div>
    )
}

function MessengerMetricCard({ metric }: { metric: MessengerMetric }) {
    const width = `${Math.min(100, Math.max(0, metric.conversion_rate))}%`

    return (
        <div className="rounded-md border p-4">
            <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                    <div className="rounded-md bg-primary/10 p-2">
                        <MessageCircle className="h-4 w-4 text-primary" />
                    </div>
                    <div className="min-w-0">
                        <div className="truncate text-sm font-semibold">{metric.label}</div>
                        <div className="text-xs text-muted-foreground">Не написали после клика: {metric.lost_after_click}</div>
                    </div>
                </div>
                <div className="text-right">
                    <div className="text-2xl font-bold">{metric.conversion_rate}%</div>
                    <div className="text-xs text-muted-foreground">по квизу</div>
                </div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-md bg-muted/60 p-3">
                    <div className="text-xs text-muted-foreground">Нажали</div>
                    <div className="mt-1 text-xl font-semibold">{metric.clicks}</div>
                </div>
                <div className="rounded-md bg-muted/60 p-3">
                    <div className="text-xs text-muted-foreground">Написали с кодом</div>
                    <div className="mt-1 text-xl font-semibold">{metric.inbound}</div>
                </div>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-primary" style={{ width }} />
            </div>
        </div>
    )
}

function FunnelRow({ step }: { step: FunnelStepMetric }) {
    return (
        <div className="grid grid-cols-[1fr_auto] gap-3 rounded-md border px-3 py-2">
            <div className="min-w-0">
                <div className="truncate text-sm font-medium">{step.label}</div>
                <div className="text-xs text-muted-foreground">
                    от старта: {step.conversion_from_start ?? 0}%
                </div>
            </div>
            <div className="text-right">
                <div className="text-sm font-semibold">{step.count}</div>
                <div className="text-xs text-muted-foreground">
                    {step.conversion_from_previous === null || step.conversion_from_previous === undefined ? '-' : `${step.conversion_from_previous}%`}
                </div>
            </div>
        </div>
    )
}

function BreakdownPanel({ title, items }: { title: string; items: BreakdownItem[] }) {
    const total = items.reduce((sum, item) => sum + item.count, 0)
    return (
        <section className="rounded-lg border bg-card p-6">
            <h3 className="mb-4 text-lg font-semibold">{title}</h3>
            <div className="space-y-3">
                {items.length === 0 ? (
                    <p className="py-6 text-center text-sm text-muted-foreground">Нет данных</p>
                ) : items.map((item) => {
                    const width = total ? `${Math.max(4, Math.round((item.count / total) * 100))}%` : '0%'
                    return (
                        <div key={item.key}>
                            <div className="mb-1 flex items-center justify-between gap-2 text-sm">
                                <span className="truncate">{item.label}</span>
                                <span className="font-medium">{item.count}</span>
                            </div>
                            <div className="h-2 overflow-hidden rounded-full bg-muted">
                                <div className="h-full rounded-full bg-primary" style={{ width }} />
                            </div>
                        </div>
                    )
                })}
            </div>
        </section>
    )
}

function AnswerPanel({ answer }: { answer: QuizAnswerBreakdown }) {
    return (
        <div className="rounded-md border p-4">
            <div className="mb-3 flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
                <h4 className="truncate text-sm font-semibold">{answer.label}</h4>
            </div>
            <div className="space-y-2">
                {answer.options.length === 0 ? (
                    <p className="py-4 text-center text-xs text-muted-foreground">Нет ответов</p>
                ) : answer.options.map((option) => (
                    <div key={option.key} className="flex items-center justify-between gap-3 text-sm">
                        <span className="min-w-0 truncate text-muted-foreground">{option.label}</span>
                        <span className="font-medium">{option.count}</span>
                    </div>
                ))}
            </div>
        </div>
    )
}

function RecentEvents({ events }: { events: AnalyticsEventItem[] }) {
    const [pageSize, setPageSize] = useState(10)
    const [page, setPage] = useState(1)

    if (events.length === 0) {
        return (
            <div>
                <h3 className="mb-4 text-lg font-semibold">Последние события</h3>
                <p className="py-8 text-center text-sm text-muted-foreground">Событий пока нет</p>
            </div>
        )
    }

    const totalPages = Math.max(1, Math.ceil(events.length / pageSize))
    const currentPage = Math.min(page, totalPages)
    const start = (currentPage - 1) * pageSize
    const pagedEvents = events.slice(start, start + pageSize)

    return (
        <div>
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h3 className="text-lg font-semibold">Последние события</h3>
                    <p className="text-sm text-muted-foreground">Показаны последние {events.length} событий по выбранным фильтрам</p>
                </div>
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                    Строк
                    <select
                        value={pageSize}
                        onChange={(event) => {
                            setPageSize(Number(event.target.value))
                            setPage(1)
                        }}
                        className="h-9 rounded-md border bg-background px-2 text-sm text-foreground"
                    >
                        {[10, 20, 40].map((size) => (
                            <option key={size} value={size}>{size}</option>
                        ))}
                    </select>
                </label>
            </div>

            <div className="overflow-x-auto rounded-md border">
                <table className="w-full min-w-[780px] text-left text-sm">
                    <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
                        <tr>
                            <th className="px-4 py-3 font-medium">Событие</th>
                            <th className="px-4 py-3 font-medium">Шаг</th>
                            <th className="px-4 py-3 font-medium">Сессия</th>
                            <th className="px-4 py-3 font-medium">Данные</th>
                            <th className="px-4 py-3 font-medium">Время</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y">
                        {pagedEvents.map((event) => (
                            <tr key={event.id} className="hover:bg-muted/30">
                                <td className="px-4 py-3 font-medium">{eventLabels[event.event_type] || event.event_type}</td>
                                <td className="px-4 py-3 text-muted-foreground">{event.step_id || '-'}</td>
                                <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{event.session_token.slice(0, 14)}...</td>
                                <td className="max-w-[300px] truncate px-4 py-3 text-muted-foreground">
                                    {formatEventData(event)}
                                </td>
                                <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">{formatTimeAgo(event.created_at)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="text-sm text-muted-foreground">
                    {start + 1}-{Math.min(start + pageSize, events.length)} из {events.length}
                </div>
                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        onClick={() => setPage((value) => Math.max(1, value - 1))}
                        disabled={currentPage === 1}
                        className="h-9 rounded-md border px-3 text-sm font-medium hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        Назад
                    </button>
                    <span className="min-w-20 text-center text-sm text-muted-foreground">
                        {currentPage} / {totalPages}
                    </span>
                    <button
                        type="button"
                        onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                        disabled={currentPage === totalPages}
                        className="h-9 rounded-md border px-3 text-sm font-medium hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        Вперед
                    </button>
                </div>
            </div>
        </div>
    )
}

function formatEventData(event: AnalyticsEventItem) {
    if (!event.event_data) return '-'
    if (event.event_data.label) return String(event.event_data.label)
    if (event.event_data.value) return String(event.event_data.value)
    if (event.event_data.lead_id) return `lead ${String(event.event_data.lead_id).slice(0, 8)}`
    return JSON.stringify(event.event_data)
}
