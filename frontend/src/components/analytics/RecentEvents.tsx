import { useState } from 'react'
import { formatTimeAgo } from '@/lib/utils'
import type { AnalyticsEventItem } from '@/types'

const eventLabels: Record<string, string> = {
    quiz_opened: 'Открыл квиз',
    quiz_started: 'Начал квиз',
    quiz_step_viewed: 'Увидел вопрос',
    quiz_step_hesitated: 'Долго думал',
    quiz_step_answered: 'Ответил на шаг',
    quiz_step_back_clicked: 'Назад в квизе',
    answer_selected: 'Ответил',
    contact_gate_viewed: 'Увидел сохранение',
    contact_gate_submitted: 'Сохранил контакт',
    contact_viewed: 'Контакты',
    contact_submitted: 'Оставил контакты',
    messenger_selected: 'Выбрал мессенджер',
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

export function RecentEvents({ events }: { events: AnalyticsEventItem[] }) {
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
