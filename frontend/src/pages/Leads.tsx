import React, { useState, useEffect, useRef } from 'react'
import { useLeads, useUpdateLead } from '@/hooks/useLeads'
import { useChatHistory, useSendMessage } from '@/hooks/useChat'
import { useCustomFields } from '@/hooks/useCustomFields'
import { useConvertLeadToProject } from '@/hooks/useProjects'
import { LeadStatus, MessageDirection, type Lead } from '@/types'
import { formatTimeAgo } from '@/lib/utils'
import {
    X, Phone, MapPin, Ruler, Home, Wallet, MessageSquare,
    Clock, ShieldCheck, Settings2, Search, Send,
    Calendar, ClipboardList, Sparkles
} from 'lucide-react'

const API_URL = (import.meta as any).env.VITE_API_URL || 'http://localhost:8001'

const columns = [
    { id: LeadStatus.NEW, title: 'Новые лиды', color: 'bg-blue-500' },
    { id: LeadStatus.CONSULTING, title: 'Консультация', color: 'bg-yellow-500' },
    { id: LeadStatus.FOLLOW_UP, title: 'Follow-up (ИИ)', color: 'bg-orange-500' },
    { id: LeadStatus.QUALIFIED, title: 'Квалифицирован', color: 'bg-emerald-500' },
    { id: LeadStatus.MEASUREMENT, title: 'Замер', color: 'bg-purple-500' },
    { id: LeadStatus.ESTIMATE, title: 'Смета', color: 'bg-pink-500' },
    { id: LeadStatus.CONTRACT, title: 'Контракт', color: 'bg-indigo-500' },
    { id: LeadStatus.WON, title: 'Выигран', color: 'bg-green-500' },
    { id: LeadStatus.LOST, title: 'Проигран', color: 'bg-red-500' },
]

export function Leads() {
    const [search, setSearch] = useState('')
    const [source, setSource] = useState<string>('')
    const [visibleStages, setVisibleStages] = useState<LeadStatus[]>(columns.map(c => c.id))
    const { data } = useLeads({ search: search || undefined, source: source || undefined })
    const { data: customFields } = useCustomFields(true)
    const updateLead = useUpdateLead()
    const convertLead = useConvertLeadToProject()
    const [draggedLead, setDraggedLead] = useState<Lead | null>(null)
    const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
    const [showStageFilters, setShowStageFilters] = useState(false)
    const [notification, setNotification] = useState<{ message: string, type: 'success' | 'error' } | null>(null)

    const leads = data?.leads || []

    const getLeadsByStatus = (status: LeadStatus) => {
        return leads.filter((lead) => lead.status === status)
    }

    const toggleStage = (stage: LeadStatus) => {
        setVisibleStages(prev =>
            prev.includes(stage)
                ? prev.filter(s => s !== stage)
                : [...prev, stage]
        )
    }

    const handleDragStart = (lead: Lead) => {
        setDraggedLead(lead)
    }

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault()
    }

    const handleDrop = (status: LeadStatus) => {
        if (draggedLead && draggedLead.status !== status) {
            updateLead.mutate({
                id: draggedLead.id,
                data: { status },
            })

            // Auto convert to project if moved to CONTRACT or WON
            if (status === LeadStatus.CONTRACT || status === LeadStatus.WON) {
                convertLead.mutate({ leadId: draggedLead.id }, {
                    onSuccess: () => {
                        setNotification({ message: 'Объект успешно создан и связан!', type: 'success' })
                        setTimeout(() => setNotification(null), 5000)
                    },
                    onError: (err: any) => {
                        setNotification({ message: 'Ошибка при создании объекта: ' + (err.response?.data?.detail || err.message), type: 'error' })
                        setTimeout(() => setNotification(null), 5000)
                    }
                })
            }
        }
        setDraggedLead(null)
    }

    const filteredColumns = columns.filter(col => visibleStages.includes(col.id))

    return (
        <div className="h-full relative flex flex-col gap-6">
            <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold">Управление лидами</h2>

                <div className="flex items-center gap-4">
                    {/* Stage visibility toggle */}
                    <div className="relative">
                        <button
                            onClick={() => setShowStageFilters(!showStageFilters)}
                            className={`flex h-10 items-center gap-2 rounded-lg border px-4 text-sm transition-colors hover:bg-accent ${showStageFilters ? 'bg-accent border-primary' : 'bg-background'}`}
                        >
                            <Settings2 className="h-4 w-4" />
                            Стадии воронки
                            <span className="ml-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-bold text-primary">
                                {visibleStages.length}
                            </span>
                        </button>

                        {showStageFilters && (
                            <>
                                <div
                                    className="fixed inset-0 z-10"
                                    onClick={() => setShowStageFilters(false)}
                                />
                                <div className="absolute right-0 top-12 z-20 w-64 rounded-xl border bg-card p-4 shadow-2xl animate-in fade-in zoom-in-95 duration-200">
                                    <h4 className="mb-3 text-xs font-bold uppercase tracking-wider text-muted-foreground text-[10px]">Видимые стадии</h4>
                                    <div className="grid gap-1.5">
                                        {columns.map((col) => (
                                            <label
                                                key={col.id}
                                                className="flex cursor-pointer items-center justify-between rounded-md p-2 transition-colors hover:bg-accent"
                                            >
                                                <div className="flex items-center gap-2.5">
                                                    <div className={`h-2 w-2 rounded-full ${col.color}`} />
                                                    <span className="text-[13px] font-medium">{col.title}</span>
                                                </div>
                                                <input
                                                    type="checkbox"
                                                    checked={visibleStages.includes(col.id)}
                                                    onChange={() => toggleStage(col.id)}
                                                    className="h-3.5 w-3.5 rounded border-slate-300 text-primary focus:ring-primary"
                                                />
                                            </label>
                                        ))}
                                    </div>
                                    <div className="mt-4 border-t pt-3 flex gap-2">
                                        <button
                                            onClick={() => setVisibleStages(columns.map(c => c.id))}
                                            className="flex-1 text-[10px] font-bold uppercase text-primary hover:underline"
                                        >
                                            Все
                                        </button>
                                        <button
                                            onClick={() => setVisibleStages([])}
                                            className="flex-1 text-[10px] font-bold uppercase text-muted-foreground hover:underline"
                                        >
                                            Скрыть
                                        </button>
                                    </div>
                                </div>
                            </>
                        )}
                    </div>

                    {/* Search Input */}
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <input
                            type="text"
                            placeholder="Поиск..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="h-10 w-48 rounded-lg border bg-background pl-10 pr-4 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                        />
                    </div>

                    {/* Source Selection */}
                    <select
                        value={source}
                        onChange={(e) => setSource(e.target.value)}
                        className="h-10 rounded-lg border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                        <option value="">Источники</option>
                        <option value="telegram">Telegram</option>
                        <option value="avito">Avito</option>
                        <option value="website">Сайт</option>
                    </select>
                </div>
            </div>

            {/* Notification Toast */}
            {notification && (
                <div className={`fixed bottom-8 left-1/2 -translate-x-1/2 z-[100] px-6 py-3 rounded-xl shadow-2xl animate-in slide-in-from-bottom-4 duration-300 flex items-center gap-3 border ${notification.type === 'success' ? 'bg-emerald-500 border-emerald-400 text-white' : 'bg-red-500 border-red-400 text-white'
                    }`}>
                    <ShieldCheck className="h-5 w-5" />
                    <span className="font-bold text-sm tracking-wide">{notification.message}</span>
                    <button onClick={() => setNotification(null)} className="ml-2 hover:opacity-70">
                        <X className="h-4 w-4" />
                    </button>
                </div>
            )}

            <div className="flex h-[calc(100vh-12rem)] gap-4 overflow-x-auto pb-4 custom-scrollbar">
                {filteredColumns.map((column) => {
                    const columnLeads = getLeadsByStatus(column.id)

                    return (
                        <div
                            key={column.id}
                            className="flex flex-col rounded-lg border bg-card min-width-[320px] w-[320px] shrink-0"
                            onDragOver={handleDragOver}
                            onDrop={() => handleDrop(column.id)}
                        >
                            <div className="flex items-center justify-between border-b p-4">
                                <div className="flex items-center gap-2">
                                    <div className={`h-2 w-2 rounded-full ${column.color}`} />
                                    <h3 className="font-semibold">{column.title}</h3>
                                </div>
                                <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
                                    {columnLeads.length}
                                </span>
                            </div>

                            <div className="flex-1 space-y-2 overflow-y-auto p-4">
                                {columnLeads.map((lead) => (
                                    <LeadCard
                                        key={lead.id}
                                        lead={lead}
                                        onDragStart={() => handleDragStart(lead)}
                                        onClick={() => setSelectedLead(lead)}
                                    />
                                ))}
                            </div>
                        </div>
                    )
                })}
            </div>

            {/* Lead Workspace Overlay */}
            {selectedLead && (
                <LeadWorkspace
                    lead={selectedLead}
                    customFields={customFields || []}
                    onClose={() => setSelectedLead(null)}
                    onUpdateStatus={(status) => {
                        updateLead.mutate({ id: selectedLead.id, data: { status } })
                        setSelectedLead(prev => prev ? { ...prev, status } : null)

                        // Auto convert if status changed to CONTRACT or WON
                        if (status === LeadStatus.CONTRACT || status === LeadStatus.WON) {
                            convertLead.mutate({ leadId: selectedLead.id }, {
                                onSuccess: () => {
                                    setNotification({ message: 'Объект успешно создан и связан!', type: 'success' })
                                    setTimeout(() => setNotification(null), 5000)
                                },
                                onError: (err: any) => {
                                    setNotification({ message: 'Ошибка при создании объекта: ' + (err.response?.data?.detail || err.message), type: 'error' })
                                    setTimeout(() => setNotification(null), 5000)
                                }
                            })
                        }
                    }}
                />
            )}
        </div>
    )
}

interface LeadWorkspaceProps {
    lead: Lead
    customFields: any[]
    onClose: () => void
    onUpdateStatus: (status: LeadStatus) => void
}

function LeadWorkspace({ lead, customFields, onClose, onUpdateStatus }: LeadWorkspaceProps) {
    const [message, setMessage] = useState('')
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const { data: chatData } = useChatHistory(lead.id, 1)
    const sendMessage = useSendMessage()

    const messages = chatData?.messages || []

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }

    useEffect(() => {
        scrollToBottom()
    }, [messages])

    const handleSendMessage = () => {
        if (!message.trim()) return
        sendMessage.mutate(
            { leadId: lead.id, content: message },
            { onSuccess: () => setMessage('') }
        )
    }

    const getMessageLabel = (msg: any) => {
        if (msg.direction === MessageDirection.INBOUND) return 'Клиент'
        if (msg.sender_name === 'AI' || msg.sender_name === 'Bot') return 'ИИ Ассистент'
        return 'Вы'
    }

    const extractedData = typeof lead.extracted_data === 'string'
        ? JSON.parse(lead.extracted_data)
        : lead.extracted_data || {}

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div className="relative w-full max-w-[1240px] h-[90vh] overflow-hidden rounded-2xl bg-background shadow-2xl flex flex-col scale-in-center">

                {/* Header */}
                <div className="flex items-center justify-between border-b px-6 py-4 bg-card">
                    <div className="flex items-center gap-4">
                        {lead.avatar_url ? (
                            <img
                                src={`${API_URL}${lead.avatar_url}`}
                                alt={lead.full_name || 'U'}
                                className="h-10 w-10 rounded-full object-cover ring-2 ring-primary/20"
                            />
                        ) : (
                            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground font-bold">
                                {lead.full_name?.[0] || 'U'}
                            </div>
                        )}
                        <div>
                            <div className="flex items-center gap-2">
                                <h2 className="text-lg font-bold leading-tight">{lead.full_name || lead.username || 'Неизвестно'}</h2>
                                <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${lead.ai_qualification_status === 'handoff_required' ? 'bg-orange-100 text-orange-700' : 'bg-emerald-100 text-emerald-700'
                                    }`}>
                                    {lead.ai_qualification_status === 'handoff_required' ? 'Готов к работе' : 'ИИ: Квалификация'}
                                </span>
                            </div>
                            <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                <span className="flex items-center gap-1"><Phone className="h-3 w-3" /> {lead.phone || '—'}</span>
                                {lead.username && <span>• @{lead.username}</span>}
                                {lead.source && <span className="flex items-center gap-1">• <MessageSquare className="h-3 w-3" /> {lead.source}</span>}
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <button className="flex h-10 items-center gap-2 rounded-lg border bg-background px-4 text-sm font-medium transition-colors hover:bg-accent ring-1 ring-slate-200">
                            <Calendar className="h-4 w-4" />
                            Замер
                        </button>
                        {lead.converted_to_project_id ? (
                            <a
                                href={`/projects?id=${lead.converted_to_project_id}`}
                                className="flex h-10 items-center gap-2 rounded-lg bg-emerald-600 px-4 text-sm font-medium text-white transition-all hover:bg-emerald-700 shadow-sm"
                            >
                                <Home className="h-4 w-4" />
                                Перейти к объекту
                            </a>
                        ) : (
                            <button
                                onClick={() => {
                                    if (window.confirm('Преобразовать лид в активный проект?')) {
                                        onUpdateStatus(LeadStatus.CONTRACT)
                                    }
                                }}
                                className="flex h-10 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-all hover:opacity-90 shadow-sm"
                            >
                                <ShieldCheck className="h-4 w-4" />
                                Начать проект
                            </button>
                        )}
                        <div className="mx-2 h-6 w-px bg-border" />
                        <button onClick={onClose} className="rounded-full p-2 hover:bg-muted transition-colors">
                            <X className="h-5 w-5" />
                        </button>
                    </div>
                </div>

                {/* Content Workspace */}
                <div className="flex-1 flex overflow-hidden">

                    {/* Left Panel: Info & Status */}
                    <div className="w-[40%] border-r bg-slate-50/50 flex flex-col overflow-y-auto custom-scrollbar">
                        <div className="p-6 space-y-8">

                            {/* Status Section */}
                            <section>
                                <h3 className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                                    <ShieldCheck className="h-3.5 w-3.5" /> Текущая стадия
                                </h3>
                                <div className="grid grid-cols-2 gap-2">
                                    {Object.values(LeadStatus).map((status) => (
                                        <button
                                            key={status}
                                            onClick={() => onUpdateStatus(status)}
                                            className={`flex items-center gap-2 px-3 py-2.5 text-xs font-semibold rounded-xl border transition-all ${lead.status === status
                                                ? 'bg-primary text-primary-foreground border-primary shadow-md'
                                                : 'bg-white hover:bg-slate-50 border-slate-200 text-slate-600'
                                                }`}
                                        >
                                            <div className={`h-1.5 w-1.5 rounded-full ${lead.status === status ? 'bg-white' : 'bg-slate-300'}`} />
                                            {status}
                                        </button>
                                    ))}
                                </div>
                            </section>

                            {/* Client Data Section */}
                            <section className="rounded-2xl border bg-white p-5 shadow-sm">
                                <h3 className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground border-b pb-3">
                                    <ClipboardList className="h-3.5 w-3.5" /> Извлеченные данные
                                </h3>
                                <div className="grid grid-cols-2 gap-y-5 gap-x-4">
                                    <DataField label="Объект" value={extractedData.property_type} icon={<Home className="h-3 w-3" />} />
                                    <DataField label="Площадь" value={extractedData.area_sqm ? `${extractedData.area_sqm} м²` : null} icon={<Ruler className="h-3 w-3" />} />
                                    <DataField label="ЖК / Адрес" value={extractedData.address} icon={<MapPin className="h-3 w-3" />} />
                                    <DataField label="Тип ремонта" value={extractedData.renovation_type} />
                                    <DataField label="Бюджет" value={extractedData.budget} icon={<Wallet className="h-3 w-3" />} />
                                    <DataField label="Сроки" value={extractedData.deadline} icon={<Clock className="h-3 w-3" />} />

                                    {/* Dynamic Custom Fields */}
                                    {customFields.map((field) => {
                                        const value = extractedData[field.field_name];
                                        return (
                                            <DataField
                                                key={field.id}
                                                label={field.field_label}
                                                value={value ? String(value) : null}
                                            />
                                        );
                                    })}
                                </div>

                                {lead.ai_summary && (
                                    <div className="mt-6 pt-5 border-t">
                                        <div className="mb-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">Саммари ИИ</div>
                                        <p className="text-sm leading-relaxed text-slate-600 italic">
                                            "{lead.ai_summary}"
                                        </p>
                                    </div>
                                )}
                            </section>
                        </div>
                    </div>

                    {/* Right Panel: Chat integration */}
                    <div className="flex-1 flex flex-col bg-background relative">
                        {/* Chat Messages */}
                        <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar bg-slate-50/30">
                            {messages.length === 0 ? (
                                <div className="flex h-full items-center justify-center text-muted-foreground flex-col gap-2">
                                    <MessageSquare className="h-8 w-8 opacity-20" />
                                    <p className="text-sm">История диалога пуста</p>
                                </div>
                            ) : (
                                [...messages].reverse().map((msg) => (
                                    <div
                                        key={msg.id}
                                        className={`flex flex-col ${msg.direction === MessageDirection.OUTBOUND ? 'items-end' : 'items-start'}`}
                                    >
                                        <div
                                            className={`max-w-[85%] rounded-2xl px-4 py-2.5 shadow-sm text-[13px] ${msg.direction === MessageDirection.OUTBOUND
                                                ? 'bg-primary text-primary-foreground rounded-br-none'
                                                : 'bg-white border text-slate-900 rounded-bl-none'
                                                }`}
                                        >
                                            <p className="leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                                        </div>

                                        <div className={`flex flex-col mt-1.5 gap-1.5 ${msg.direction === MessageDirection.OUTBOUND ? 'items-end' : 'items-start'}`}>
                                            {/* AI Status Change Indicators */}
                                            {msg.ai_metadata?.status_changed_to && (
                                                <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-primary/10 text-primary rounded-xl text-[11px] font-medium border border-primary/20 shadow-sm animate-in fade-in slide-in-from-bottom-2">
                                                    <ShieldCheck className="h-3.5 w-3.5" />
                                                    ИИ перевел на стадию: {msg.ai_metadata.status_changed_to}
                                                </div>
                                            )}
                                            {msg.ai_metadata?.qualification_changed_to && (
                                                <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-emerald-100 text-emerald-700 rounded-xl text-[11px] font-medium border border-emerald-200 shadow-sm animate-in fade-in slide-in-from-bottom-2">
                                                    <Sparkles className="h-3.5 w-3.5" />
                                                    ИИ квалифицировал лида
                                                </div>
                                            )}
                                            <span className="px-1 text-[9px] font-bold text-muted-foreground uppercase tracking-widest opacity-60">
                                                {getMessageLabel(msg)} • {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                            </span>
                                        </div>
                                    </div>
                                ))
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Input Area */}
                        <div className="border-t p-4 bg-card">
                            <div className="flex gap-2 bg-background rounded-xl border p-1 focus-within:ring-2 focus-within:ring-primary/20 transition-all shadow-inner">
                                <input
                                    type="text"
                                    value={message}
                                    onChange={(e) => setMessage(e.target.value)}
                                    onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                                    placeholder="Напишите ответ клиенту..."
                                    className="flex-1 bg-transparent px-4 py-2.5 text-sm focus:outline-none"
                                />
                                <button
                                    onClick={handleSendMessage}
                                    disabled={!message.trim() || sendMessage.isPending}
                                    className="rounded-lg bg-primary p-2.5 text-primary-foreground hover:opacity-90 disabled:opacity-50 transition-all shadow-sm active:scale-95 flex items-center justify-center"
                                >
                                    <Send className="h-4 w-4" />
                                </button>
                            </div>
                        </div>
                    </div>

                </div>
            </div>
        </div>
    )
}

function LeadCard({ lead, onDragStart, onClick }: { lead: Lead; onDragStart: () => void; onClick: () => void }) {
    return (
        <div
            draggable
            onDragStart={onDragStart}
            onClick={onClick}
            className="group cursor-pointer rounded-lg border bg-background p-3 shadow-sm transition-all hover:border-primary hover:shadow-md"
        >
            <div className="mb-2 flex items-start justify-between">
                <div className="flex items-center gap-2">
                    {lead.avatar_url ? (
                        <img
                            src={`${API_URL}${lead.avatar_url}`}
                            alt={lead.full_name || 'U'}
                            className="h-8 w-8 rounded-full object-cover group-hover:scale-110 transition-transform"
                        />
                    ) : (
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground group-hover:scale-110 transition-transform">
                            {lead.full_name?.[0] || lead.username?.[0] || 'U'}
                        </div>
                    )}
                    <div>
                        <div className="font-medium group-hover:text-primary transition-colors text-[13px]">{lead.full_name || lead.username || 'Неизвестно'}</div>
                        {lead.username && (
                            <div className="text-[10px] text-muted-foreground">@{lead.username}</div>
                        )}
                    </div>
                </div>
                {lead.unread_count > 0 && (
                    <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground animate-pulse">
                        {lead.unread_count}
                    </div>
                )}
            </div>

            {lead.ai_summary && (
                <p className="mb-3 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground italic">
                    {lead.ai_summary}
                </p>
            )}

            <div className="flex items-center justify-between border-t pt-2">
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1 text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
                        <MessageSquare className="h-3 w-3" />
                        {lead.source || 'TG'}
                    </div>
                    {lead.phone && (
                        <div className="flex items-center gap-1 text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
                            <Phone className="h-3 w-3" />
                            OK
                        </div>
                    )}
                </div>
                {lead.last_message_at && (
                    <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                        <Clock className="h-2.5 w-2.5" />
                        {formatTimeAgo(lead.last_message_at)}
                    </div>
                )}
            </div>
        </div>
    )
}

function DataField({ label, value, icon }: { label: string, value: string | null, icon?: React.ReactNode }) {
    return (
        <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-muted-foreground opacity-80">
                {icon} {label}
            </div>
            <div className="text-xs font-medium text-slate-800">
                {value || <span className="text-slate-300 font-normal">Нет данных</span>}
            </div>
        </div>
    )
}
