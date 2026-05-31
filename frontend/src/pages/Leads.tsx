import React, { useState, useEffect, useRef, useMemo } from 'react'
import { useLeadsInfinite, useLeadHistory, useUpdateLead, useDeleteLead, useCreateLead, useImportLeads, useBulkDeleteLeads, useUploadFinalEstimate, useSendFinalEstimate } from '@/hooks/useLeads'
import { useChatHistory, useSendBusinessCard, useSendMessage } from '@/hooks/useChat'
import { useCustomFields } from '@/hooks/useCustomFields'
import { useConvertLeadToProject } from '@/hooks/useProjects'
import { LeadStatus, MessageDirection, MessageTransport, type Lead } from '@/types'
import { MessageToolCallBadge } from '@/components/chat/MessageToolCallBadge'
import { formatTimeAgo } from '@/lib/utils'
import { toast } from 'sonner'
import {
    X, Phone, MapPin, Ruler, Home, Wallet, MessageSquare,
    Clock, ShieldCheck, Settings2, Search, Send,
    ClipboardList, Sparkles, Trash2, Mic, Plus, Upload, MessageCircle, Square, CheckSquare, History,
    CalendarClock, ChevronDown, FileText
} from 'lucide-react'

const API_URL = (import.meta as any).env.VITE_API_URL || 'http://localhost:8001'

function getMediaUrl(url?: string | null): string | null {
    if (!url) return null
    if (/^https?:\/\//i.test(url)) return url
    return `${API_URL}${url.startsWith('/') ? url : `/${url}`}`
}

const columns = [
    { id: LeadStatus.NEW, title: 'Новый лид', color: 'bg-sky-500' },
    { id: LeadStatus.QUIZ_COMPLETED, title: 'Квиз пройден', color: 'bg-cyan-500' },
    { id: LeadStatus.MESSENGER_PENDING, title: 'Ждем сообщение', color: 'bg-amber-500' },
    { id: LeadStatus.DESIGN_PENDING, title: 'Ждем проект', color: 'bg-orange-500' },
    { id: LeadStatus.DESIGN_REVIEW, title: 'Проект на разборе', color: 'bg-lime-600' },
    { id: LeadStatus.CONSULTING, title: 'Консультация', color: 'bg-yellow-500' },
    { id: LeadStatus.QUALIFIED, title: 'Квалифицирован', color: 'bg-emerald-500' },
    { id: LeadStatus.MEASUREMENT_PENDING, title: 'Ждем запись', color: 'bg-violet-500' },
    { id: LeadStatus.MEASUREMENT_BOOKED, title: 'Замер назначен', color: 'bg-purple-500' },
    { id: LeadStatus.MEASUREMENT, title: 'Замер', color: 'bg-fuchsia-500' },
    { id: LeadStatus.MEASUREMENT_DONE, title: 'Замер проведен', color: 'bg-rose-500' },
    { id: LeadStatus.ESTIMATE_PREPARING, title: 'Смета готовится', color: 'bg-pink-500' },
    { id: LeadStatus.ESTIMATE_REVIEW, title: 'Смета на проверке', color: 'bg-orange-600' },
    { id: LeadStatus.ESTIMATE_SENT, title: 'Смета отправлена', color: 'bg-indigo-500' },
    { id: LeadStatus.ESTIMATE, title: 'Смета', color: 'bg-blue-500' },
    { id: LeadStatus.FOLLOW_UP, title: 'Дожим / прогрев', color: 'bg-stone-500' },
    { id: LeadStatus.CONTRACT_NEGOTIATION, title: 'Договор на согласовании', color: 'bg-teal-600' },
    { id: LeadStatus.CONTRACT, title: 'Договор подписан', color: 'bg-teal-700' },
    { id: LeadStatus.WON, title: 'Оплачен / в работе', color: 'bg-green-600' },
    { id: LeadStatus.LOST, title: 'Отказ', color: 'bg-red-500' },
    { id: LeadStatus.SPAM, title: 'Спам', color: 'bg-slate-800' },
]

const statusLabels: { [key in LeadStatus]: string } = {
    [LeadStatus.NEW]: 'Новый лид',
    [LeadStatus.QUIZ_COMPLETED]: 'Квиз пройден',
    [LeadStatus.MESSENGER_PENDING]: 'Ждем сообщение',
    [LeadStatus.DESIGN_PENDING]: 'Ждем дизайн-проект',
    [LeadStatus.DESIGN_REVIEW]: 'Проект на разборе',
    [LeadStatus.CONSULTING]: 'Консультация',
    [LeadStatus.QUALIFIED]: 'Квалифицирован',
    [LeadStatus.MEASUREMENT_PENDING]: 'Ждем запись на замер',
    [LeadStatus.MEASUREMENT_BOOKED]: 'Замер назначен',
    [LeadStatus.MEASUREMENT]: 'Замер',
    [LeadStatus.MEASUREMENT_DONE]: 'Замер проведен',
    [LeadStatus.ESTIMATE_PREPARING]: 'Смета готовится',
    [LeadStatus.ESTIMATE_REVIEW]: 'Смета на проверке',
    [LeadStatus.ESTIMATE_SENT]: 'Смета отправлена',
    [LeadStatus.ESTIMATE]: 'Смета',
    [LeadStatus.FOLLOW_UP]: 'Дожим / прогрев',
    [LeadStatus.CONTRACT_NEGOTIATION]: 'Договор на согласовании',
    [LeadStatus.CONTRACT]: 'Договор подписан',
    [LeadStatus.WON]: 'Оплачен / в работе',
    [LeadStatus.LOST]: 'Отказ',
    [LeadStatus.SPAM]: 'Спам',
}

const telegramLookupStatusLabels: Record<string, string> = {
    active: 'Telegram найден',
    inactive: 'Telegram не найден',
    not_checked: 'Не проверяли',
    unavailable: 'Проверка недоступна',
    rate_limited: 'Лимит проверки',
    invalid_phone: 'Невалидный номер',
    error: 'Ошибка проверки',
}

function getTelegramLookupBadgeClass(status: string) {
    if (status === 'active') return 'bg-emerald-500/10 text-emerald-700'
    if (status === 'inactive') return 'bg-slate-500/10 text-slate-700'
    if (status === 'rate_limited' || status === 'unavailable') return 'bg-amber-500/10 text-amber-700'
    if (status === 'error' || status === 'invalid_phone') return 'bg-red-500/10 text-red-700'
    return 'bg-muted text-muted-foreground'
}

const LEADS_PAGE_SIZE = 100

export function Leads() {
    const [search, setSearch] = useState('')
    const [source, setSource] = useState<string>('')
    const [visibleStages, setVisibleStages] = useState<LeadStatus[]>(columns.map(c => c.id))
    const {
        data,
        hasNextPage,
        isFetchingNextPage,
        fetchNextPage,
    } = useLeadsInfinite({
        search: search || undefined,
        source: source || undefined,
        page_size: LEADS_PAGE_SIZE,
    })
    const { data: customFields } = useCustomFields(true)
    const updateLead = useUpdateLead()
    const createLead = useCreateLead()
    const importLeads = useImportLeads()
    const bulkDeleteLeads = useBulkDeleteLeads()
    const convertLead = useConvertLeadToProject()
    const [draggedLead, setDraggedLead] = useState<Lead | null>(null)
    const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
    const [showStageFilters, setShowStageFilters] = useState(false)
    const [showCreateModal, setShowCreateModal] = useState(false)
    const [showImportModal, setShowImportModal] = useState(false)
    const [selectionMode, setSelectionMode] = useState(false)
    const [selectedLeadIds, setSelectedLeadIds] = useState<string[]>([])
    const [draggedOverColumn, setDraggedOverColumn] = useState<LeadStatus | null>(null)
    const [notification, setNotification] = useState<{ message: string, type: 'success' | 'error' } | null>(null)

    const allLoadedLeads = data?.pages.flatMap((pageData) => pageData.leads) || []
    const leads = useMemo(() => {
        const unique = new Map<string, Lead>()
        for (const lead of allLoadedLeads) {
            if (!unique.has(lead.id)) {
                unique.set(lead.id, lead)
            }
        }
        return Array.from(unique.values())
    }, [allLoadedLeads])

    const totalLeads = data?.pages?.[0]?.total || 0
    const loadedLeadsCount = leads.length
    const selectedCount = selectedLeadIds.length
    const isAllLoadedSelected = loadedLeadsCount > 0 && leads.every((lead) => selectedLeadIds.includes(lead.id))

    const getLeadsByStatus = (status: LeadStatus) => {
        return leads.filter((lead) => lead.status === status)
    }

    const loadMoreLeads = () => {
        if (!hasNextPage || isFetchingNextPage) return
        fetchNextPage()
    }

    const handleColumnScroll = (event: React.UIEvent<HTMLDivElement>) => {
        const element = event.currentTarget
        const nearBottom = element.scrollTop + element.clientHeight >= element.scrollHeight - 200
        if (nearBottom) {
            loadMoreLeads()
        }
    }

    const toggleStage = (stage: LeadStatus) => {
        setVisibleStages(prev =>
            prev.includes(stage)
                ? prev.filter(s => s !== stage)
                : [...prev, stage]
        )
    }

    const handleDragStart = (e: React.DragEvent, lead: Lead) => {
        if (selectionMode) return
        e.dataTransfer.setData('leadId', lead.id)
        e.dataTransfer.setData('leadStatus', lead.status)
        setDraggedLead(lead)
    }

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault()
        e.dataTransfer.dropEffect = 'move'
    }

    const handleDragEnter = (e: React.DragEvent, status: LeadStatus) => {
        e.preventDefault()
        setDraggedOverColumn(status)
    }

    const handleDragLeave = (e: React.DragEvent) => {
        const relatedTarget = e.relatedTarget as Node;
        if (e.currentTarget.contains(relatedTarget)) return;
        setDraggedOverColumn(null)
    }

    const handleDrop = (e: React.DragEvent, status: LeadStatus) => {
        if (selectionMode) return
        e.preventDefault()
        const leadId = e.dataTransfer.getData('leadId')
        const oldStatus = e.dataTransfer.getData('leadStatus') as LeadStatus
        if (leadId && oldStatus !== status) {
            updateLead.mutate({
                id: leadId,
                data: { status },
            })

            // Auto convert to project if moved to CONTRACT or WON
            if (status === LeadStatus.CONTRACT || status === LeadStatus.WON) {
                convertLead.mutate({ leadId }, {
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
        setDraggedOverColumn(null)
    }

    const filteredColumns = columns.filter(col => visibleStages.includes(col.id))

    const toggleLeadSelection = (leadId: string) => {
        setSelectedLeadIds(prev =>
            prev.includes(leadId)
                ? prev.filter(id => id !== leadId)
                : [...prev, leadId]
        )
    }

    const toggleSelectAllLoaded = () => {
        if (isAllLoadedSelected) {
            const loadedIds = new Set(leads.map((lead) => lead.id))
            setSelectedLeadIds(prev => prev.filter(id => !loadedIds.has(id)))
            return
        }
        const merged = new Set(selectedLeadIds)
        for (const lead of leads) {
            merged.add(lead.id)
        }
        setSelectedLeadIds(Array.from(merged))
    }

    const handleBulkDelete = () => {
        if (selectedLeadIds.length === 0) return
        if (!window.confirm(`Удалить выбранные лиды (${selectedLeadIds.length})? Это действие необратимо.`)) return

        bulkDeleteLeads.mutate(selectedLeadIds, {
            onSuccess: (result) => {
                if (selectedLead && selectedLeadIds.includes(selectedLead.id)) {
                    setSelectedLead(null)
                }
                setSelectedLeadIds([])
                setSelectionMode(false)
                setNotification({
                    message: `Удалено лидов: ${result.deleted} из ${result.requested}`,
                    type: 'success',
                })
                setTimeout(() => setNotification(null), 7000)
            },
            onError: (err: any) => {
                setNotification({
                    message: 'Ошибка массового удаления: ' + (err.response?.data?.detail || err.message),
                    type: 'error',
                })
                setTimeout(() => setNotification(null), 7000)
            },
        })
    }

    return (
        <div className="h-full relative flex flex-col gap-6">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <h2 className="text-2xl font-bold">Управление лидами</h2>
                    <span className="rounded-full border bg-card px-3 py-1 text-xs font-semibold">
                        Всего лидов: {totalLeads}
                    </span>
                </div>

                <div className="flex items-center gap-4">
                    <button
                        onClick={() => setShowCreateModal(true)}
                        className="flex h-10 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
                    >
                        <Plus className="h-4 w-4" />
                        Добавить лида
                    </button>

                    <button
                        onClick={() => setShowImportModal(true)}
                        className="flex h-10 items-center gap-2 rounded-lg border bg-background px-4 text-sm font-medium shadow-sm transition-colors hover:bg-accent"
                    >
                        <Upload className="h-4 w-4" />
                        Массовый импорт
                    </button>

                    <button
                        onClick={() => {
                            if (selectionMode) {
                                setSelectionMode(false)
                                setSelectedLeadIds([])
                                return
                            }
                            setSelectionMode(true)
                        }}
                        className={`flex h-10 items-center gap-2 rounded-lg border px-4 text-sm font-medium shadow-sm transition-colors ${selectionMode ? 'bg-accent border-primary' : 'bg-background hover:bg-accent'}`}
                    >
                        {selectionMode ? <CheckSquare className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                        Массовое удаление
                    </button>

                    {selectionMode && (
                        <>
                            <button
                                onClick={toggleSelectAllLoaded}
                                className="flex h-10 items-center gap-2 rounded-lg border bg-background px-4 text-sm font-medium shadow-sm transition-colors hover:bg-accent"
                            >
                                {isAllLoadedSelected ? 'Снять все' : 'Выбрать загруженные'}
                            </button>
                            <button
                                onClick={handleBulkDelete}
                                disabled={selectedCount === 0 || bulkDeleteLeads.isPending}
                                className="flex h-10 items-center gap-2 rounded-lg bg-red-600 px-4 text-sm font-medium text-white shadow-sm transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                <Trash2 className="h-4 w-4" />
                                {bulkDeleteLeads.isPending ? 'Удаляем...' : `Удалить (${selectedCount})`}
                            </button>
                        </>
                    )}

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
                            className={`flex w-[320px] min-w-[320px] shrink-0 flex-col rounded-lg border bg-card transition-colors duration-200 ${draggedOverColumn === column.id ? 'ring-2 ring-primary bg-primary/5 border-primary/50' : ''
                                }`}
                            onDragOver={handleDragOver}
                            onDragEnter={(e) => handleDragEnter(e, column.id)}
                            onDragLeave={handleDragLeave}
                            onDrop={(e) => handleDrop(e, column.id)}
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

                            <div className="flex-1 space-y-2 overflow-x-hidden overflow-y-auto p-4" onScroll={handleColumnScroll}>
                                {columnLeads.map((lead) => (
                                    <LeadCard
                                        key={lead.id}
                                        lead={lead}
                                        onDragStart={(e) => handleDragStart(e, lead)}
                                        onClick={() => {
                                            if (selectionMode) {
                                                toggleLeadSelection(lead.id)
                                                return
                                            }
                                            setSelectedLead(lead)
                                        }}
                                        selectionMode={selectionMode}
                                        selected={selectedLeadIds.includes(lead.id)}
                                    />
                                ))}
                            </div>
                        </div>
                    )
                })}
            </div>

            <div className="flex items-center justify-between rounded-xl border bg-card px-4 py-3">
                <div className="text-sm text-muted-foreground">
                    Загружено <span className="font-semibold text-foreground">{loadedLeadsCount}</span> из <span className="font-semibold text-foreground">{totalLeads}</span>
                    {selectionMode && (
                        <span> • Выбрано: <span className="font-semibold text-foreground">{selectedCount}</span></span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={loadMoreLeads}
                        disabled={!hasNextPage || isFetchingNextPage}
                        className="rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-accent transition-colors"
                    >
                        {isFetchingNextPage ? 'Загрузка...' : hasNextPage ? 'Загрузить ещё' : 'Загружено всё'}
                    </button>
                </div>
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

            {showCreateModal && (
                <CreateLeadModal
                    onClose={() => setShowCreateModal(false)}
                    onSubmit={(data) => {
                        createLead.mutate({ ...data, org_id: '00000000-0000-0000-0000-000000000000' }, {
                            onSuccess: () => {
                                setNotification({ message: 'Лид успешно создан!', type: 'success' })
                                setTimeout(() => setNotification(null), 5000)
                                setShowCreateModal(false)
                            },
                            onError: (err: any) => {
                                setNotification({ message: 'Ошибка при создании: ' + (err.response?.data?.detail || err.message), type: 'error' })
                                setTimeout(() => setNotification(null), 5000)
                            }
                        })
                    }}
                    isLoading={createLead.isPending}
                />
            )}

            {showImportModal && (
                <ImportLeadsModal
                    onClose={() => setShowImportModal(false)}
                    onSubmit={(file, sourceValue) => {
                        importLeads.mutate(
                            { file, source: sourceValue },
                            {
                                onSuccess: (result) => {
                                    const hasChanges = result.imported > 0 || result.updated > 0
                                    const baseMessage = `Импорт завершен: новых ${result.imported}, обновлено ${result.updated}, пропущено ${result.skipped}`
                                    const extra = result.errors.length > 0 ? `, ошибок строк: ${result.errors.length}` : ''
                                    setNotification({
                                        message: `${baseMessage}${extra}`,
                                        type: hasChanges ? 'success' : 'error',
                                    })
                                    setTimeout(() => setNotification(null), 7000)
                                    setShowImportModal(false)
                                },
                                onError: (err: any) => {
                                    setNotification({
                                        message: 'Ошибка импорта: ' + (err.response?.data?.detail || err.message),
                                        type: 'error',
                                    })
                                    setTimeout(() => setNotification(null), 7000)
                                },
                            }
                        )
                    }}
                    isLoading={importLeads.isPending}
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

type ExtractedFieldDescriptor = {
    key: string
    label: string
    icon?: React.ReactNode
}

const BASE_EXTRACTED_FIELDS: ExtractedFieldDescriptor[] = [
    { key: 'property_type', label: 'Объект', icon: <Home className="h-3 w-3" /> },
    { key: 'area_sqm', label: 'Площадь', icon: <Ruler className="h-3 w-3" /> },
    { key: 'address', label: 'ЖК / Адрес', icon: <MapPin className="h-3 w-3" /> },
    { key: 'renovation_type', label: 'Тип ремонта' },
    { key: 'budget', label: 'Бюджет', icon: <Wallet className="h-3 w-3" /> },
    { key: 'deadline', label: 'Сроки', icon: <Clock className="h-3 w-3" /> },
]

const QUIZ_FIELD_LABELS: Record<string, string> = {
    type: 'Объект',
    area: 'Площадь',
    rtype: 'Тип ремонта',
    state: 'Состояние',
    rooms: 'Объем',
    design: 'Дизайн',
    deadline: 'Срок',
    budget: 'Бюджет',
}

const QUIZ_VALUE_LABELS: Record<string, Record<string, string>> = {
    type: { flat: 'Квартира', house: 'Дом', commercial: 'Коммерция' },
    area: { xs: 'до 40 м²', sm: '40-70 м²', md: '70-100 м²', lg: '100+ м²' },
    rtype: { cosm: 'Косметический', finish: 'Чистовая отделка', full: 'Под ключ' },
    state: { rough: 'Черновая отделка', lived: 'Жилое, требует обновления', demo: 'Нужен полный снос' },
    rooms: { partial: 'Только санузел / кухня', several: 'Несколько комнат', all: 'Вся квартира целиком' },
    design: { yes: 'Да, уже готов', wip: 'В процессе разработки', no: 'Нет, хочу в подарок' },
    deadline: { asap: 'Как можно скорее', soon: 'В течение 1-3 месяцев', later: 'Не спешу' },
    budget: { b1: 'До 1 млн ₽', b2: '1-2 млн ₽', b3: '2-4 млн ₽', b4: 'От 4 млн ₽' },
}

function parseExtractedData(raw: Lead['extracted_data']): Record<string, any> {
    try {
        return typeof raw === 'string' ? JSON.parse(raw || '{}') : (raw || {})
    } catch {
        return {}
    }
}

function getLeadAvailableTransports(lead: Lead): MessageTransport[] {
    const transports: MessageTransport[] = []
    const presence = getMessengerPresence(lead)
    if (lead.telegram_id) {
        transports.push(MessageTransport.TELEGRAM)
    }
    if (presence.whatsapp) {
        transports.push(MessageTransport.WHATSAPP)
    }
    if (transports.length === 0) {
        transports.push(MessageTransport.TELEGRAM)
    }
    return transports
}

function getDefaultTransport(lead: Lead): MessageTransport {
    const available = getLeadAvailableTransports(lead)
    if (available.includes(MessageTransport.TELEGRAM)) return MessageTransport.TELEGRAM
    return available[0]
}

function getQuizAnswerRows(extractedData: Record<string, any>): Array<{ key: string; label: string; value: string }> {
    const answers = extractedData?.quiz?.answers
    if (!answers || typeof answers !== 'object') return []

    return Object.entries(answers)
        .filter(([, value]) => value !== undefined && value !== null && String(value).trim() !== '')
        .map(([key, value]) => ({
            key,
            label: QUIZ_FIELD_LABELS[key] || key,
            value: QUIZ_VALUE_LABELS[key]?.[String(value)] || String(value),
        }))
}

function formatMeasurementStart(value?: string | null): string | null {
    if (!value) return null
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return String(value)
    return date.toLocaleString('ru-RU', {
        timeZone: 'Europe/Moscow',
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    })
}

function getMeasurementStatusLabel(status?: string | null): string {
    if (status === 'booked') return 'Записан в календарь'
    if (status === 'requested') return 'Ожидает подтверждения'
    if (status === 'awaiting_address') return 'Ждем адрес'
    return 'Не записан'
}

function LeadWorkspace({ lead, customFields, onClose, onUpdateStatus }: LeadWorkspaceProps) {
    const [message, setMessage] = useState('')
    const [selectedTransport, setSelectedTransport] = useState<MessageTransport>(getDefaultTransport(lead))
    const [sendChannelError, setSendChannelError] = useState<string | null>(null)
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const finalEstimateInputRef = useRef<HTMLInputElement>(null)
    const { data: chatData } = useChatHistory(lead.id, 1, selectedTransport)
    const { data: historyData, isLoading: isHistoryLoading } = useLeadHistory(lead.id, 100)
    const sendMessage = useSendMessage()
    const sendBusinessCard = useSendBusinessCard()
    const deleteLead = useDeleteLead()
    const updateLead = useUpdateLead()
    const uploadFinalEstimate = useUploadFinalEstimate()
    const sendFinalEstimate = useSendFinalEstimate()
    const [isEditingExtracted, setIsEditingExtracted] = useState(false)
    const [savedExtractedData, setSavedExtractedData] = useState<Record<string, any>>(parseExtractedData(lead.extracted_data))
    const [extractedDraft, setExtractedDraft] = useState<Record<string, string>>({})
    const [savedOperatorComment, setSavedOperatorComment] = useState(lead.operator_comment || '')
    const [operatorCommentDraft, setOperatorCommentDraft] = useState(lead.operator_comment || '')
    const [showStatusPicker, setShowStatusPicker] = useState(false)

    const messages = chatData?.messages || []
    const historyItems = historyData?.items || []
    const editableFields = useMemo<ExtractedFieldDescriptor[]>(() => {
        const baseKeys = new Set(BASE_EXTRACTED_FIELDS.map((field) => field.key))
        const customDescriptors = customFields
            .filter((field) => field?.field_name && !baseKeys.has(field.field_name))
            .map((field) => ({
                key: field.field_name as string,
                label: (field.field_label || field.field_name) as string,
            }))
        return [...BASE_EXTRACTED_FIELDS, ...customDescriptors]
    }, [customFields])

    const buildExtractedDraft = (data: Record<string, any>) => {
        const draft: Record<string, string> = {}
        for (const field of editableFields) {
            const value = data[field.key]
            draft[field.key] = value === undefined || value === null ? '' : String(value)
        }
        return draft
    }

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }

    useEffect(() => {
        scrollToBottom()
    }, [messages])

    useEffect(() => {
        const parsed = parseExtractedData(lead.extracted_data)
        setSavedExtractedData(parsed)
        setExtractedDraft(buildExtractedDraft(parsed))
        setSavedOperatorComment(lead.operator_comment || '')
        setOperatorCommentDraft(lead.operator_comment || '')
        setIsEditingExtracted(false)
    }, [lead.id, lead.extracted_data, lead.operator_comment, editableFields])

    const handleSendMessage = () => {
        if (!message.trim() || !isSelectedTransportSendAvailable) return
        setSendChannelError(null)
        sendMessage.mutate(
            { leadId: lead.id, content: message, transport: selectedTransport },
            {
                onSuccess: () => setMessage(''),
                onError: (error: any) => {
                    const detail = error?.response?.data?.detail || 'Ошибка отправки сообщения'
                    setSendChannelError(String(detail))
                },
            }
        )
    }

    const handleSendBusinessCard = () => {
        if (!lead.telegram_id || sendBusinessCard.isPending) return
        sendBusinessCard.mutate({ leadId: lead.id })
    }

    const handleExtractedFieldChange = (key: string, value: string) => {
        setExtractedDraft((prev) => ({
            ...prev,
            [key]: value,
        }))
    }

    const handleSaveExtractedData = () => {
        const nextExtractedData: Record<string, any> = { ...savedExtractedData }

        for (const field of editableFields) {
            const value = extractedDraft[field.key]?.trim() || ''
            if (value) {
                nextExtractedData[field.key] = value
            } else {
                delete nextExtractedData[field.key]
            }
        }

        updateLead.mutate(
            {
                id: lead.id,
                data: { extracted_data: JSON.stringify(nextExtractedData) },
            },
            {
                onSuccess: () => {
                    setSavedExtractedData(nextExtractedData)
                    setExtractedDraft(buildExtractedDraft(nextExtractedData))
                    setIsEditingExtracted(false)
                },
            }
        )
    }

    const handleSaveOperatorComment = () => {
        const nextComment = operatorCommentDraft.trim()
        updateLead.mutate(
            {
                id: lead.id,
                data: { operator_comment: nextComment || null },
            },
            {
                onSuccess: () => {
                    setSavedOperatorComment(nextComment)
                    setOperatorCommentDraft(nextComment)
                },
            }
        )
    }

    const handleFinalEstimateFile = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        event.target.value = ''
        if (!file || uploadFinalEstimate.isPending) return

        uploadFinalEstimate.mutate(
            { id: lead.id, file },
            {
                onSuccess: (updatedLead) => {
                    setSavedExtractedData(parseExtractedData(updatedLead.extracted_data))
                    toast.success('Смета загружена')
                },
                onError: (error: any) => {
                    toast.error(error?.response?.data?.detail || 'Не удалось загрузить смету')
                },
            }
        )
    }

    const handleSendFinalEstimate = () => {
        if (sendFinalEstimate.isPending) return
        sendFinalEstimate.mutate(
            { id: lead.id },
            {
                onSuccess: (updatedLead) => {
                    setSavedExtractedData(parseExtractedData(updatedLead.extracted_data))
                    toast.success('Смета отправлена клиенту')
                },
                onError: (error: any) => {
                    toast.error(error?.response?.data?.detail || 'Не удалось отправить смету')
                },
            }
        )
    }

    const getMessageLabel = (msg: any) => {
        if (msg.direction === MessageDirection.INBOUND) return 'Клиент'
        if (msg.sender_name === 'AI' || msg.sender_name === 'Bot') return 'ИИ Ассистент'
        return 'Вы'
    }

    const getHistoryActionLabel = (action?: string) => {
        if (action === 'created') return 'Создание'
        if (action === 'updated') return 'Изменение'
        return action || 'Изменение'
    }

    const getHistoryFieldLabel = (key: string) => {
        const labels: Record<string, string> = {
            full_name: 'ФИО',
            phone: 'Телефон',
            username: 'Username',
            status: 'Стадия',
            ai_summary: 'Саммари ИИ',
            operator_comment: 'Комментарий оператора',
            extracted_data: 'Извлеченные данные',
            telegram_lookup_status: 'Статус Telegram',
            telegram_lookup_error: 'Ошибка Telegram',
            import_sync: 'Импорт',
        }
        return labels[key] || key
    }

    const formatHistorySummary = (changes?: Record<string, { old: any; new: any }>) => {
        if (!changes) return 'Без деталей'
        const entries = Object.entries(changes)
        if (entries.length === 0) return 'Без деталей'
        return entries
            .slice(0, 3)
            .map(([key, value]) => `${getHistoryFieldLabel(key)}: ${value?.new ?? '—'}`)
            .join(' • ')
    }

    const messengerPresence = getMessengerPresence(lead)
    const availableTransports = getLeadAvailableTransports(lead)
    const isWhatsappTransport = selectedTransport === MessageTransport.WHATSAPP
    const isSelectedTransportSendAvailable =
        selectedTransport === MessageTransport.TELEGRAM
            ? Boolean(lead.telegram_id)
            : Boolean(messengerPresence.whatsapp || lead.phone)
    const telegramChatUrl = getTelegramChatUrl(lead)
    const whatsappChatUrl = getWhatsAppChatUrl(lead)
    const quizAnswerRows = getQuizAnswerRows(savedExtractedData)
    const quizPrice = savedExtractedData?.quiz?.price
    const quizPreferredMessenger = savedExtractedData?.quiz?.preferred_messenger
    const estimateRequest = savedExtractedData?.estimate_request && typeof savedExtractedData.estimate_request === 'object'
        ? savedExtractedData.estimate_request
        : null
    const latestEstimateFile = estimateRequest?.latest_file && typeof estimateRequest.latest_file === 'object'
        ? estimateRequest.latest_file
        : null
    const estimateFileUrl = getMediaUrl(latestEstimateFile?.url ? String(latestEstimateFile.url) : null)
    const estimateFileName = latestEstimateFile?.filename ? String(latestEstimateFile.filename) : 'Файл для расчета'
    const finalEstimateFile = estimateRequest?.final_file && typeof estimateRequest.final_file === 'object'
        ? estimateRequest.final_file
        : null
    const finalEstimateUrl = getMediaUrl(finalEstimateFile?.url ? String(finalEstimateFile.url) : null)
    const finalEstimateName = finalEstimateFile?.filename ? String(finalEstimateFile.filename) : 'Готовая смета'
    const canSendFinalEstimate = Boolean(finalEstimateUrl && lead.telegram_id)
    const shouldShowEstimatePanel = Boolean(
        estimateRequest
        || [
            LeadStatus.MEASUREMENT_DONE,
            LeadStatus.ESTIMATE_PREPARING,
            LeadStatus.ESTIMATE_REVIEW,
            LeadStatus.ESTIMATE,
            LeadStatus.ESTIMATE_SENT,
        ].includes(lead.status as LeadStatus)
    )
    const estimateStatusLabel = estimateRequest?.status === 'needs_estimate'
        ? 'Нужен просчет'
        : estimateRequest?.status === 'ready_to_send'
            ? 'Готова к отправке'
            : estimateRequest?.status === 'sent'
                ? 'Отправлена'
        : estimateRequest?.status
            ? String(estimateRequest.status)
            : 'Не запрошен'
    const estimateSlaLabel = estimateRequest?.sla_hours ? `До ${estimateRequest.sla_hours} часов` : 'До 24 часов'
    const measurement = savedExtractedData?.measurement && typeof savedExtractedData.measurement === 'object'
        ? savedExtractedData.measurement
        : null
    const measurementStart = formatMeasurementStart(measurement?.start)
    const measurementSlotLabel = measurement?.selected_slot_label ? String(measurement.selected_slot_label) : null
    const measurementAddress = measurement?.address || savedExtractedData?.measurement_address || savedExtractedData?.address
    const measurementStatus = measurement?.status ? String(measurement.status) : null
    const hasMeasurementData = Boolean(measurementStart || measurementSlotLabel || measurementAddress || measurementStatus || measurement?.booking_uid)

    useEffect(() => {
        const nextAvailable = getLeadAvailableTransports(lead)
        const nextDefault = getDefaultTransport(lead)
        setSelectedTransport((prev) => (nextAvailable.includes(prev) ? prev : nextDefault))
    }, [lead.id, lead.telegram_id, lead.extracted_data])

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
                                <span className="flex items-center gap-1 rounded px-1.5 py-0.5">
                                    <Phone className="h-3 w-3" />
                                    <span>{lead.phone || '—'}</span>
                                </span>
                                <span
                                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${getTelegramLookupBadgeClass(lead.telegram_lookup_status || 'not_checked')}`}
                                    title={lead.telegram_lookup_error || ''}
                                >
                                    {telegramLookupStatusLabels[lead.telegram_lookup_status || 'not_checked'] || (lead.telegram_lookup_status || 'not_checked')}
                                </span>
                                {messengerPresence.telegram && (
                                    telegramChatUrl ? (
                                        <a
                                            href={telegramChatUrl}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            onClick={(e) => e.stopPropagation()}
                                            className="flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-0.5 text-blue-600 transition-colors hover:bg-blue-500/20"
                                            title="Открыть чат в Telegram"
                                        >
                                            <Send className="h-3 w-3" /> TG
                                        </a>
                                    ) : (
                                        <span className="flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-0.5 text-blue-600" title="Telegram активен">
                                            <Send className="h-3 w-3" /> TG
                                        </span>
                                    )
                                )}
                                {messengerPresence.whatsapp && (
                                    whatsappChatUrl ? (
                                        <a
                                            href={whatsappChatUrl}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            onClick={(e) => e.stopPropagation()}
                                            className="flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-600 transition-colors hover:bg-emerald-500/20"
                                            title="Открыть чат в WhatsApp"
                                        >
                                            <MessageCircle className="h-3 w-3" /> WA
                                        </a>
                                    ) : (
                                        <span className="flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-600" title="WhatsApp активен">
                                            <MessageCircle className="h-3 w-3" /> WA
                                        </span>
                                    )
                                )}
                                {lead.username && <span>• @{lead.username}</span>}
                                {lead.source && <span className="flex items-center gap-1">• <MessageSquare className="h-3 w-3" /> {lead.source}</span>}
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
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
                        <button
                            onClick={() => {
                                if (window.confirm('Вы уверены, что хотите удалить этого лида? Это действие необратимо.')) {
                                    deleteLead.mutate(lead.id, {
                                        onSuccess: () => {
                                            onClose()
                                        }
                                    })
                                }
                            }}
                            disabled={deleteLead.isPending}
                            className="flex h-10 items-center gap-2 rounded-lg bg-red-500/10 px-4 text-sm font-medium text-red-600 hover:bg-red-500/20 transition-all shadow-sm ml-2"
                        >
                            <Trash2 className="h-4 w-4" />
                            Удалить
                        </button>
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
                                <div className="rounded-2xl border bg-white p-4 shadow-sm">
                                    <div className="flex items-center justify-between gap-3">
                                        <div className="min-w-0">
                                            <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Сейчас</div>
                                            <div className="mt-1 flex items-center gap-2 text-sm font-bold text-slate-800">
                                                <span className="h-2 w-2 rounded-full bg-primary" />
                                                <span className="truncate">{statusLabels[lead.status]}</span>
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => setShowStatusPicker((value) => !value)}
                                            className="flex h-9 shrink-0 items-center gap-2 rounded-lg border px-3 text-xs font-semibold text-slate-600 transition-colors hover:bg-slate-50"
                                        >
                                            Изменить
                                            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${showStatusPicker ? 'rotate-180' : ''}`} />
                                        </button>
                                    </div>
                                    {showStatusPicker && (
                                        <div className="mt-4 grid grid-cols-2 gap-2 border-t pt-4">
                                            {Object.values(LeadStatus).map((status) => (
                                                <button
                                                    key={status}
                                                    onClick={() => {
                                                        onUpdateStatus(status)
                                                        setShowStatusPicker(false)
                                                    }}
                                                    className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-lg border transition-all ${lead.status === status
                                                        ? 'bg-primary text-primary-foreground border-primary shadow-sm'
                                                        : 'bg-white hover:bg-slate-50 border-slate-200 text-slate-600'
                                                        }`}
                                                >
                                                    <div className={`h-1.5 w-1.5 rounded-full ${lead.status === status ? 'bg-white' : 'bg-slate-300'}`} />
                                                    {statusLabels[status]}
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </section>

                            <section className="rounded-2xl border bg-white p-5 shadow-sm">
                                <h3 className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                                    <CalendarClock className="h-3.5 w-3.5" /> Замер
                                </h3>
                                {hasMeasurementData ? (
                                    <div className="grid grid-cols-2 gap-y-5 gap-x-4">
                                        <DataField label="Время брони" value={measurementStart || measurementSlotLabel} icon={<Clock className="h-3 w-3" />} />
                                        <DataField label="Статус" value={getMeasurementStatusLabel(measurementStatus)} />
                                        <DataField label="Адрес" value={measurementAddress ? String(measurementAddress) : null} icon={<MapPin className="h-3 w-3" />} />
                                        <DataField label="Booking ID" value={measurement?.booking_uid ? String(measurement.booking_uid) : null} />
                                    </div>
                                ) : (
                                    <div className="rounded-xl border border-dashed bg-slate-50 px-4 py-3 text-xs text-muted-foreground">
                                        Запись на замер пока не выбрана.
                                    </div>
                                )}
                            </section>

                            {shouldShowEstimatePanel && (
                                <section className="rounded-2xl border bg-white p-5 shadow-sm">
                                    <div className="mb-4 flex items-center justify-between gap-3">
                                        <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                                            <FileText className="h-3.5 w-3.5" /> Просчет сметы
                                        </h3>
                                        <button
                                            type="button"
                                            onClick={() => finalEstimateInputRef.current?.click()}
                                            disabled={uploadFinalEstimate.isPending}
                                            className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
                                        >
                                            <Upload className="h-3.5 w-3.5" />
                                            {uploadFinalEstimate.isPending ? 'Загрузка...' : 'Загрузить смету'}
                                        </button>
                                    </div>
                                    <div className="grid grid-cols-2 gap-y-5 gap-x-4">
                                        <DataField label="Статус" value={estimateStatusLabel} />
                                        <DataField label="Срок" value={estimateSlaLabel} icon={<Clock className="h-3 w-3" />} />
                                        <input
                                            ref={finalEstimateInputRef}
                                            type="file"
                                            accept=".pdf,.xlsx,.xls,.docx"
                                            onChange={handleFinalEstimateFile}
                                            className="hidden"
                                        />
                                        <div className="col-span-2 space-y-1">
                                            <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-muted-foreground opacity-80">
                                                <FileText className="h-3 w-3" /> Файл клиента
                                            </div>
                                            {estimateFileUrl ? (
                                                <a
                                                    href={estimateFileUrl}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="inline-flex max-w-full items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold text-primary transition-colors hover:bg-primary/5"
                                                >
                                                    <span className="truncate">{estimateFileName}</span>
                                                </a>
                                            ) : (
                                                <div className="text-xs text-slate-400">Файл клиента не прикреплен</div>
                                            )}
                                        </div>
                                        <div className="col-span-2 space-y-2 border-t pt-4">
                                            <div className="flex items-center justify-between gap-3">
                                                <div className="min-w-0">
                                                    <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-muted-foreground opacity-80">
                                                        <FileText className="h-3 w-3" /> Готовая смета
                                                    </div>
                                                    {finalEstimateUrl ? (
                                                        <a
                                                            href={finalEstimateUrl}
                                                            target="_blank"
                                                            rel="noreferrer"
                                                            className="mt-1 block truncate text-xs font-semibold text-primary hover:underline"
                                                        >
                                                            {finalEstimateName}
                                                        </a>
                                                    ) : (
                                                        <div className="mt-1 text-xs text-slate-400">Файл еще не загружен</div>
                                                    )}
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={() => finalEstimateInputRef.current?.click()}
                                                    disabled={uploadFinalEstimate.isPending}
                                                    className="inline-flex shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition-colors hover:bg-slate-50 disabled:opacity-50"
                                                >
                                                    <Upload className="h-3.5 w-3.5" />
                                                    {finalEstimateUrl ? 'Заменить' : 'Выбрать файл'}
                                                </button>
                                            </div>
                                            <button
                                                type="button"
                                                onClick={handleSendFinalEstimate}
                                                disabled={!canSendFinalEstimate || sendFinalEstimate.isPending}
                                                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                                            >
                                                <Send className="h-3.5 w-3.5" />
                                                {sendFinalEstimate.isPending ? 'Отправляем...' : 'Отправить смету клиенту'}
                                            </button>
                                            {!lead.telegram_id && (
                                                <div className="text-[11px] text-amber-600">Для отправки нужен Telegram у лида.</div>
                                            )}
                                        </div>
                                    </div>
                                </section>
                            )}

                            {/* Client Data Section */}
                            <section className="rounded-2xl border bg-white p-5 shadow-sm">
                                <div className="mb-4 flex items-center justify-between border-b pb-3">
                                    <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                                        <ClipboardList className="h-3.5 w-3.5" /> Извлеченные данные
                                    </h3>
                                    <div className="flex items-center gap-2">
                                        {isEditingExtracted ? (
                                            <>
                                                <button
                                                    onClick={() => {
                                                        setExtractedDraft(buildExtractedDraft(savedExtractedData))
                                                        setIsEditingExtracted(false)
                                                    }}
                                                    disabled={updateLead.isPending}
                                                    className="rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors hover:bg-accent disabled:opacity-50"
                                                >
                                                    Отмена
                                                </button>
                                                <button
                                                    onClick={handleSaveExtractedData}
                                                    disabled={updateLead.isPending}
                                                    className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
                                                >
                                                    {updateLead.isPending ? 'Сохраняем...' : 'Сохранить'}
                                                </button>
                                            </>
                                        ) : (
                                            <button
                                                onClick={() => {
                                                    setExtractedDraft(buildExtractedDraft(savedExtractedData))
                                                    setIsEditingExtracted(true)
                                                }}
                                                className="rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors hover:bg-accent"
                                            >
                                                Изменить
                                            </button>
                                        )}
                                    </div>
                                </div>

                                {isEditingExtracted ? (
                                    <div className="grid grid-cols-2 gap-y-4 gap-x-4">
                                        {editableFields.map((field) => (
                                            <div key={field.key} className="space-y-1.5">
                                                <label className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-muted-foreground opacity-80">
                                                    {field.icon}
                                                    {field.label}
                                                </label>
                                                <input
                                                    type="text"
                                                    value={extractedDraft[field.key] || ''}
                                                    onChange={(event) => handleExtractedFieldChange(field.key, event.target.value)}
                                                    className="h-9 w-full rounded-lg border bg-background px-3 text-xs focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                                                />
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-2 gap-y-5 gap-x-4">
                                        <DataField label="Объект" value={savedExtractedData.property_type ? String(savedExtractedData.property_type) : null} icon={<Home className="h-3 w-3" />} />
                                        <DataField label="Площадь" value={savedExtractedData.area_sqm ? `${savedExtractedData.area_sqm} м²` : null} icon={<Ruler className="h-3 w-3" />} />
                                        <DataField label="ЖК / Адрес" value={savedExtractedData.address ? String(savedExtractedData.address) : null} icon={<MapPin className="h-3 w-3" />} />
                                        <DataField label="Тип ремонта" value={savedExtractedData.renovation_type ? String(savedExtractedData.renovation_type) : null} />
                                        <DataField label="Бюджет" value={savedExtractedData.budget ? String(savedExtractedData.budget) : null} icon={<Wallet className="h-3 w-3" />} />
                                        <DataField label="Сроки" value={savedExtractedData.deadline ? String(savedExtractedData.deadline) : null} icon={<Clock className="h-3 w-3" />} />
                                        {customFields.map((field) => {
                                            const value = savedExtractedData[field.field_name]
                                            return (
                                                <DataField
                                                    key={field.id}
                                                    label={field.field_label}
                                                    value={value ? String(value) : null}
                                                />
                                            )
                                        })}
                                    </div>
                                )}

                                {lead.ai_summary && (
                                    <div className="mt-6 pt-5 border-t">
                                        <div className="mb-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">Саммари ИИ</div>
                                        <p className="text-sm leading-relaxed text-slate-600 italic">
                                            "{lead.ai_summary}"
                                        </p>
                                    </div>
                                )}
                            </section>

                            {quizAnswerRows.length > 0 && (
                                <section className="rounded-2xl border bg-white p-5 shadow-sm">
                                    <h3 className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                                        <ClipboardList className="h-3.5 w-3.5" /> Ответы квиза
                                    </h3>
                                    <div className="grid grid-cols-2 gap-y-5 gap-x-4">
                                        {quizAnswerRows.map((row) => (
                                            <DataField key={row.key} label={row.label} value={row.value} />
                                        ))}
                                        {quizPrice?.label && (
                                            <DataField label="Расчет" value={String(quizPrice.label)} icon={<Wallet className="h-3 w-3" />} />
                                        )}
                                        {quizPreferredMessenger && (
                                            <DataField
                                                label="Мессенджер"
                                                value={String(quizPreferredMessenger) === 'telegram' ? 'Telegram' : 'WhatsApp'}
                                                icon={<MessageCircle className="h-3 w-3" />}
                                            />
                                        )}
                                    </div>
                                </section>
                            )}

                            <section className="rounded-2xl border bg-white p-5 shadow-sm">
                                <h3 className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                                    <MessageSquare className="h-3.5 w-3.5" /> Комментарий оператора
                                </h3>
                                <textarea
                                    value={operatorCommentDraft}
                                    onChange={(event) => setOperatorCommentDraft(event.target.value)}
                                    rows={4}
                                    placeholder="Добавьте комментарий для команды по этому лиду..."
                                    className="w-full rounded-xl border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                                />
                                <div className="mt-3 flex items-center justify-end gap-2">
                                    <button
                                        onClick={() => setOperatorCommentDraft(savedOperatorComment)}
                                        disabled={updateLead.isPending || operatorCommentDraft === savedOperatorComment}
                                        className="rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors hover:bg-accent disabled:opacity-50"
                                    >
                                        Отмена
                                    </button>
                                    <button
                                        onClick={handleSaveOperatorComment}
                                        disabled={updateLead.isPending || operatorCommentDraft.trim() === savedOperatorComment}
                                        className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
                                    >
                                        {updateLead.isPending ? 'Сохраняем...' : 'Сохранить'}
                                    </button>
                                </div>
                            </section>

                            <section className="rounded-2xl border bg-white p-5 shadow-sm">
                                <h3 className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                                    <History className="h-3.5 w-3.5" /> История изменений
                                </h3>
                                {isHistoryLoading ? (
                                    <div className="text-xs text-muted-foreground">Загрузка истории...</div>
                                ) : historyItems.length === 0 ? (
                                    <div className="text-xs text-muted-foreground">Изменений пока нет</div>
                                ) : (
                                    <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                                        {historyItems.map((item: any) => (
                                            <div key={item.id} className="rounded-lg border p-2.5 bg-slate-50/80">
                                                <div className="flex items-center justify-between gap-2">
                                                    <span className="text-[11px] font-semibold text-slate-700">
                                                        {item.user_name || 'Система'} • {getHistoryActionLabel(item.action)}
                                                    </span>
                                                    <span className="text-[10px] text-muted-foreground">
                                                        {new Date(item.created_at).toLocaleString()}
                                                    </span>
                                                </div>
                                                <div className="mt-1 text-[11px] text-slate-600">
                                                    {formatHistorySummary(item.changes)}
                                                </div>
                                            </div>
                                        ))}
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
                                            className={`max-w-[85%] rounded-2xl px-4 py-2.5 shadow-sm text-[13px] relative group ${msg.direction === MessageDirection.OUTBOUND
                                                ? 'bg-primary text-primary-foreground rounded-br-none'
                                                : 'bg-slate-100 text-slate-900 border rounded-bl-none'
                                                }`}
                                        >
                                            {msg.ai_metadata?.is_voice && (
                                                <div className={`flex items-center gap-1 mb-1.5 text-xs font-semibold ${msg.direction === MessageDirection.OUTBOUND ? 'text-primary-foreground/80' : 'text-slate-500'}`}>
                                                    <Mic className="h-3 w-3" />
                                                    Голосовое сообщение
                                                </div>
                                            )}
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
                                            {msg.ai_metadata?.source === 'CRM' && (
                                                <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-100 text-slate-600 rounded-xl text-[11px] font-medium border border-slate-200 shadow-sm animate-in fade-in slide-in-from-bottom-2">
                                                    Отправлено из CRM
                                                </div>
                                            )}
                                            <MessageToolCallBadge
                                                message={msg}
                                                leadSource={lead.source}
                                            />
                                            <span className="px-1 text-[9px] font-bold text-muted-foreground uppercase tracking-widest opacity-60">
                                                {getMessageLabel(msg)} • {(msg.transport === MessageTransport.WHATSAPP ? 'WA' : 'TG')} • {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                            </span>
                                        </div>
                                    </div>
                                ))
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Input Area */}
                        <div className="border-t p-4 bg-card">
                            <div className="mb-2 flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Канал</span>
                                    <div className="flex rounded-lg border bg-background p-0.5">
                                        {availableTransports.map((transport) => (
                                            <button
                                                key={transport}
                                                onClick={() => setSelectedTransport(transport)}
                                                className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${selectedTransport === transport
                                                        ? 'bg-primary text-primary-foreground'
                                                        : 'text-muted-foreground hover:bg-accent'
                                                    }`}
                                            >
                                                {transport === MessageTransport.TELEGRAM ? 'Telegram' : 'WhatsApp'}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                                <button
                                    onClick={handleSendBusinessCard}
                                    disabled={!lead.telegram_id || sendBusinessCard.isPending}
                                    className="rounded-lg border bg-background px-3 py-1.5 text-xs font-semibold transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
                                    title={lead.telegram_id ? 'Отправить шаблон визитки в Telegram' : 'Для отправки нужен Telegram у лида'}
                                >
                                    {sendBusinessCard.isPending ? 'Отправляем визитку…' : 'Отправить визитку (TG)'}
                                </button>
                            </div>
                            {isWhatsappTransport && (
                                <div className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">
                                    Канал WhatsApp выбран. Сообщение уйдёт через интеграцию Wazzup.
                                </div>
                            )}
                            {sendChannelError && (
                                <div className="mb-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[11px] text-red-700">
                                    {sendChannelError}
                                </div>
                            )}
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
                                    disabled={!message.trim() || sendMessage.isPending || !isSelectedTransportSendAvailable}
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

function LeadCard({
    lead,
    onDragStart,
    onClick,
    selectionMode = false,
    selected = false,
}: {
    lead: Lead
    onDragStart: (e: React.DragEvent) => void
    onClick: () => void
    selectionMode?: boolean
    selected?: boolean
}) {
    const messengerPresence = getMessengerPresence(lead)
    const telegramChatUrl = getTelegramChatUrl(lead)
    const whatsappChatUrl = getWhatsAppChatUrl(lead)

    return (
        <div
            draggable={!selectionMode}
            onDragStart={onDragStart}
            onClick={onClick}
            className={`group w-full min-w-0 cursor-pointer rounded-lg border bg-background p-3 shadow-sm transition-all hover:border-primary hover:shadow-md ${selected ? 'ring-2 ring-primary border-primary' : ''}`}
        >
            <div className="mb-2 flex min-w-0 items-start justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
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
                    <div className="min-w-0">
                        <div className="flex min-w-0 items-center gap-2">
                            <div className="truncate text-[13px] font-medium transition-colors group-hover:text-primary">{lead.full_name || lead.username || 'Неизвестно'}</div>
                            {lead.readiness_score && (
                                <span className={`inline-flex items-center justify-center h-4 w-4 rounded text-[10px] font-bold ${lead.readiness_score === 'A' ? 'bg-emerald-100 text-emerald-700' :
                                        lead.readiness_score === 'B' ? 'bg-yellow-100 text-yellow-700' :
                                            'bg-red-100 text-red-700'
                                    }`}>
                                    {lead.readiness_score}
                                </span>
                            )}
                        </div>
                        {lead.username && (
                            <div className="truncate text-[10px] text-muted-foreground">@{lead.username}</div>
                        )}
                    </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                    {selectionMode && (
                        <div className={`flex h-5 w-5 items-center justify-center rounded border ${selected ? 'bg-primary border-primary text-primary-foreground' : 'bg-background border-slate-300 text-transparent'}`}>
                            <CheckSquare className="h-3 w-3" />
                        </div>
                    )}
                    {lead.unread_count > 0 && (
                        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground animate-pulse">
                            {lead.unread_count}
                        </div>
                    )}
                </div>
            </div>

            {lead.ai_summary && (
                <p className="mb-3 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground italic">
                    {lead.ai_summary}
                </p>
            )}

            <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 border-t pt-2">
                <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                    <div className="flex min-w-0 items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                        <MessageSquare className="h-3 w-3" />
                        <span className="min-w-0 truncate">{lead.source || 'TG'}</span>
                    </div>
                    <div
                        className={`max-w-full rounded-full px-1.5 py-0.5 text-[9px] font-semibold leading-tight ${getTelegramLookupBadgeClass(lead.telegram_lookup_status || 'not_checked')}`}
                        title={lead.telegram_lookup_error || ''}
                    >
                        {telegramLookupStatusLabels[lead.telegram_lookup_status || 'not_checked'] || (lead.telegram_lookup_status || 'not_checked')}
                    </div>
                    {messengerPresence.telegram && (
                        telegramChatUrl ? (
                            <a
                                href={telegramChatUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/15 text-blue-600 transition-colors hover:bg-blue-500/25"
                                title="Открыть чат в Telegram"
                            >
                                <Send className="h-3 w-3" />
                            </a>
                        ) : (
                            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/15 text-blue-600" title="Telegram активен">
                                <Send className="h-3 w-3" />
                            </div>
                        )
                    )}
                    {messengerPresence.whatsapp && (
                        whatsappChatUrl ? (
                            <a
                                href={whatsappChatUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-600 transition-colors hover:bg-emerald-500/25"
                                title="Открыть чат в WhatsApp"
                            >
                                <MessageCircle className="h-3 w-3" />
                            </a>
                        ) : (
                            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-600" title="WhatsApp активен">
                                <MessageCircle className="h-3 w-3" />
                            </div>
                        )
                    )}
                    {lead.phone && (
                        <div className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                            <Phone className="h-3 w-3" />
                            OK
                        </div>
                    )}
                </div>
                {lead.last_message_at && (
                    <div className="flex shrink-0 items-center gap-1 text-[10px] text-muted-foreground">
                        <Clock className="h-2.5 w-2.5" />
                        {formatTimeAgo(lead.last_message_at)}
                    </div>
                )}
            </div>
        </div >
    )
}

function getMessengerPresence(lead: Lead): { telegram: boolean; whatsapp: boolean } {
    const parsed = getLeadExtractedData(lead)
    const messengers = parsed?.messengers || {}
    return {
        telegram: Boolean(messengers.telegram),
        whatsapp: Boolean(messengers.whatsapp),
    }
}

function getLeadExtractedData(lead: Lead): Record<string, any> {
    try {
        return typeof lead.extracted_data === 'string'
            ? JSON.parse(lead.extracted_data || '{}')
            : (lead.extracted_data || {})
    } catch {
        return {}
    }
}

function normalizePhoneDigits(phone?: string | null): string | null {
    const digitsOnly = String(phone || '').replace(/\D/g, '')
    if (!digitsOnly) return null
    if (digitsOnly.length === 11 && digitsOnly.startsWith('8')) return `7${digitsOnly.slice(1)}`
    if (digitsOnly.length === 10) return `7${digitsOnly}`
    return digitsOnly.length >= 10 ? digitsOnly : null
}

function getTelegramChatUrl(lead: Lead): string | null {
    const username = String(lead.username || '').replace(/^@/, '').trim()
    if (username) return `https://t.me/${username}`

    const telegramId = String((lead as any).telegram_id || '').trim()
    if (telegramId) return `tg://user?id=${telegramId}`
    return null
}

function getWhatsAppChatUrl(lead: Lead): string | null {
    const extracted = getLeadExtractedData(lead)
    const waId = String(extracted?.whatsapp_wa_id || '').replace(/\D/g, '')
    const phoneDigits = normalizePhoneDigits(lead.phone)
    const target = waId || phoneDigits
    if (!target) return null
    return `https://wa.me/${target}`
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

export function CreateLeadModal({ onClose, onSubmit, isLoading }: { onClose: () => void, onSubmit: (data: { full_name: string; phone: string; username?: string; source: string }) => void, isLoading: boolean }) {
    const [name, setName] = useState('')
    const [phone, setPhone] = useState('')
    const [username, setUsername] = useState('')
    const [source, setSource] = useState('CRM')

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        onSubmit({ full_name: name, phone, username, source })
    }

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div className="w-full max-w-sm bg-card border rounded-2xl shadow-2xl p-6 scale-in-center">
                <div className="flex items-center justify-between mb-6">
                    <h3 className="text-xl font-bold">Добавить лида</h3>
                    <button type="button" onClick={onClose} className="p-2 hover:bg-accent rounded-full transition-colors">
                        <X className="h-5 w-5 text-muted-foreground" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="text-sm font-medium mb-1.5 block text-foreground/90">Имя и Фамилия</label>
                        <input
                            type="text"
                            required
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className="w-full h-11 px-4 rounded-xl border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 shadow-sm"
                            placeholder="Иван Иванов"
                        />
                    </div>

                    <div>
                        <label className="text-sm font-medium mb-1.5 block text-foreground/90">Номер телефона</label>
                        <input
                            type="tel"
                            value={phone}
                            onChange={(e) => setPhone(e.target.value)}
                            className="w-full h-11 px-4 rounded-xl border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 shadow-sm"
                            placeholder="+7 999 123 45 67"
                        />
                    </div>

                    <div>
                        <label className="text-sm font-medium mb-1.5 block text-foreground/90">Никнейм (Telegram)</label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            className="w-full h-11 px-4 rounded-xl border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 shadow-sm"
                            placeholder="@username (необязательно)"
                        />
                    </div>

                    <div className="pt-4 flex justify-end gap-3 mt-4">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-5 py-2.5 rounded-xl font-medium border hover:bg-accent transition-colors"
                        >
                            Отмена
                        </button>
                        <button
                            type="submit"
                            disabled={isLoading || !name.trim()}
                            className="px-5 py-2.5 rounded-xl font-medium bg-primary text-primary-foreground hover:opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-sm active:scale-95"
                        >
                            {isLoading ? 'Сохранение...' : 'Создать'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}

function ImportLeadsModal({
    onClose,
    onSubmit,
    isLoading,
}: {
    onClose: () => void
    onSubmit: (file: File, source: string) => void
    isLoading: boolean
}) {
    const [file, setFile] = useState<File | null>(null)
    const [source, setSource] = useState('IMPORT')

    const handleSubmit = (event: React.FormEvent) => {
        event.preventDefault()
        if (!file) return
        onSubmit(file, source.trim() || 'IMPORT')
    }

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div className="w-full max-w-md bg-card border rounded-2xl shadow-2xl p-6 scale-in-center">
                <div className="flex items-center justify-between mb-6">
                    <h3 className="text-xl font-bold">Массовый импорт лидов</h3>
                    <button type="button" onClick={onClose} className="p-2 hover:bg-accent rounded-full transition-colors">
                        <X className="h-5 w-5 text-muted-foreground" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="text-sm font-medium mb-1.5 block text-foreground/90">Файл (.xlsx или .csv)</label>
                        <input
                            type="file"
                            accept=".xlsx,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            onChange={(event) => setFile(event.target.files?.[0] || null)}
                            className="w-full h-11 px-3 rounded-xl border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 shadow-sm file:mr-3 file:border-0 file:bg-transparent file:text-sm file:font-medium"
                        />
                    </div>

                    <div>
                        <label className="text-sm font-medium mb-1.5 block text-foreground/90">Источник для лидов</label>
                        <input
                            type="text"
                            value={source}
                            onChange={(event) => setSource(event.target.value)}
                            className="w-full h-11 px-4 rounded-xl border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 shadow-sm"
                            placeholder="IMPORT"
                        />
                    </div>

                    <div className="rounded-xl border bg-muted/50 px-3 py-2 text-xs text-muted-foreground leading-relaxed">
                        Колонки определяются автоматически по названиям (например: ФИО, Телефон, ЖК, Площадь, Email).
                    </div>

                    <div className="pt-2 flex justify-end gap-3">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-5 py-2.5 rounded-xl font-medium border hover:bg-accent transition-colors"
                        >
                            Отмена
                        </button>
                        <button
                            type="submit"
                            disabled={isLoading || !file}
                            className="px-5 py-2.5 rounded-xl font-medium bg-primary text-primary-foreground hover:opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-sm active:scale-95"
                        >
                            {isLoading ? 'Импорт...' : 'Загрузить'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}
