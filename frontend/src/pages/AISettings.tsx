import React, { useState } from 'react'
import { toast } from 'sonner'
import { useAI } from '@/hooks/useAI'
import {
    useApproveOperatorAccessRequest,
    useCreateOperator,
    useDeleteOperator,
    useOperatorAccessRequests,
    useOperators,
    useRejectOperatorAccessRequest,
    useUpdateOperator,
} from '@/hooks/useOperators'
import UserBotSettings from '@/components/UserBotSettings'
import CustomFieldsManager from '@/components/CustomFieldsManager'
import type {
    OperatorCreatePayload,
    OperatorUpdatePayload,
    OperatorAccessRequest,
} from '@/types'
import {
    Database,
    History,
    Save,
    Plus,
    Search,
    Cpu,
    Sparkles,
    BookOpen,
    Zap,
    Loader2,
    Trash2,
    Settings,
    MessageSquare,
    UserCog
} from 'lucide-react'
import { cn } from '@/lib/utils'

export function AISettings() {
    const [activeTab, setActiveTab] = useState<'config' | 'fields' | 'knowledge' | 'history' | 'userbot' | 'operators'>('config')
    const {
        activePrompt,
        prompts,
        addKnowledge,
        createPrompt,
        searchKnowledge,
        clearKnowledge,
        knowledge,
        uploadFile,
        deleteKnowledge,
    } = useAI()
    const operators = useOperators()
    const createOperator = useCreateOperator()
    const updateOperator = useUpdateOperator()
    const deleteOperator = useDeleteOperator()
    const operatorAccessRequests = useOperatorAccessRequests('pending')
    const approveOperatorAccessRequest = useApproveOperatorAccessRequest()
    const rejectOperatorAccessRequest = useRejectOperatorAccessRequest()

    return (
        <div className="flex h-full flex-col gap-6 p-6 overflow-y-auto">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-black tracking-tight flex items-center gap-3">
                        <Sparkles className="h-8 w-8 text-primary animate-pulse" />
                        ИНТЕЛЛЕКТУАЛЬНЫЙ АССИСТЕНТ
                    </h2>
                    <p className="text-muted-foreground mt-1 text-lg">Управление промптами, моделями и базой знаний RAG</p>
                </div>
            </div>

            {/* Navigation Tabs */}
            <div className="flex gap-2 p-1 bg-muted rounded-2xl w-fit">
                <TabButton
                    active={activeTab === 'config'}
                    onClick={() => setActiveTab('config')}
                    icon={Cpu}
                    label="Конфигурация"
                />
                <TabButton
                    active={activeTab === 'fields'}
                    onClick={() => setActiveTab('fields')}
                    icon={Settings}
                    label="Кастомные поля"
                />
                <TabButton
                    active={activeTab === 'userbot'}
                    onClick={() => setActiveTab('userbot')}
                    icon={MessageSquare}
                    label="User Bot"
                />
                <TabButton
                    active={activeTab === 'operators'}
                    onClick={() => setActiveTab('operators')}
                    icon={UserCog}
                    label="Операторы"
                />
                <TabButton
                    active={activeTab === 'knowledge'}
                    onClick={() => setActiveTab('knowledge')}
                    icon={Database}
                    label="База знаний"
                />
                <TabButton
                    active={activeTab === 'history'}
                    onClick={() => setActiveTab('history')}
                    icon={History}
                    label="История версий"
                />
            </div>

            {/* Content Area */}
            <div className="grid grid-cols-12 gap-6 flex-1">
                <div className="col-span-12 lg:col-span-8 space-y-6">
                    {activeTab === 'config' && (
                        <ConfigurationForm
                            activePrompt={activePrompt.data}
                            onSave={(data) => {
                                createPrompt.mutate(data, {
                                    onSuccess: () => toast.success('Конфигурация успешно сохранена'),
                                    onError: () => toast.error('Ошибка сохранения конфигурации')
                                })
                            }}
                        />
                    )}
                    {activeTab === 'fields' && (
                        <div className="bg-card border rounded-3xl p-8 shadow-xl">
                            <CustomFieldsManager onFieldsChange={() => {
                                // Refresh prompt helpers when fields change
                                toast.success('Поля обновлены! Обновите промпт, чтобы использовать новые поля.')
                            }} />
                        </div>
                    )}
                    {activeTab === 'knowledge' && (
                        <KnowledgeBasePanel
                            items={searchKnowledge.data || knowledge.data || []}
                            isLoading={knowledge.isLoading || searchKnowledge.isPending}
                            isAdding={addKnowledge.isPending || uploadFile.isPending}
                            onAdd={(data) => {
                                addKnowledge.mutate(data, {
                                    onSuccess: () => toast.success('Данные проиндексированы'),
                                    onError: () => toast.error('Ошибка индексации')
                                })
                            }}
                            onUpload={(file, cat) => {
                                uploadFile.mutate({ file, category: cat }, {
                                    onSuccess: () => toast.success('Файл успешно загружен'),
                                    onError: () => toast.error('Ошибка загрузки')
                                })
                            }}
                            onDelete={(id) => {
                                deleteKnowledge.mutate(id, {
                                    onSuccess: () => toast.success('Запись удалена'),
                                    onError: () => toast.error('Ошибка удаления')
                                })
                            }}
                            onSearch={(q) => searchKnowledge.mutate({ query: q })}
                            onClearAll={() => {
                                if (window.confirm('Вы уверены, что хотите полностью очистить базу знаний? Это действие необратимо.')) {
                                    clearKnowledge.mutate(undefined, {
                                        onSuccess: () => toast.success('База знаний очищена'),
                                        onError: () => toast.error('Ошибка при очистке базы')
                                    })
                                }
                            }}
                        />
                    )}
                    {activeTab === 'userbot' && (
                        <div className="bg-card border rounded-3xl p-8 shadow-xl">
                            <UserBotSettings />
                        </div>
                    )}
                    {activeTab === 'operators' && (
                        <OperatorsPanel
                            operators={operators.data || []}
                            isLoading={operators.isLoading}
                            accessRequests={operatorAccessRequests.data || []}
                            isRequestsLoading={operatorAccessRequests.isLoading}
                            isSaving={
                                createOperator.isPending
                                || updateOperator.isPending
                                || deleteOperator.isPending
                                || approveOperatorAccessRequest.isPending
                                || rejectOperatorAccessRequest.isPending
                            }
                            onCreate={(payload) => {
                                createOperator.mutate(payload, {
                                    onSuccess: () => toast.success('Оператор добавлен'),
                                    onError: (error: any) => {
                                        const detail = error?.response?.data?.detail || 'Ошибка создания оператора'
                                        toast.error(String(detail))
                                    },
                                })
                            }}
                            onUpdate={(id, payload) => {
                                updateOperator.mutate({ id, payload }, {
                                    onSuccess: () => toast.success('Оператор обновлён'),
                                    onError: (error: any) => {
                                        const detail = error?.response?.data?.detail || 'Ошибка обновления оператора'
                                        toast.error(String(detail))
                                    },
                                })
                            }}
                            onDelete={(id) => {
                                deleteOperator.mutate(id, {
                                    onSuccess: () => toast.success('Оператор удалён'),
                                    onError: (error: any) => {
                                        const detail = error?.response?.data?.detail || 'Ошибка удаления оператора'
                                        toast.error(String(detail))
                                    },
                                })
                            }}
                            onApproveRequest={(id, payload) => {
                                approveOperatorAccessRequest.mutate({ id, payload }, {
                                    onSuccess: () => toast.success('Заявка одобрена. Оператору отправлено уведомление в Telegram.'),
                                    onError: (error: any) => {
                                        const detail = error?.response?.data?.detail || 'Ошибка одобрения заявки'
                                        toast.error(String(detail))
                                    },
                                })
                            }}
                            onRejectRequest={(id, reason) => {
                                rejectOperatorAccessRequest.mutate(
                                    { id, payload: { reason } },
                                    {
                                        onSuccess: () => toast.success('Заявка отклонена'),
                                        onError: (error: any) => {
                                            const detail = error?.response?.data?.detail || 'Ошибка отклонения заявки'
                                            toast.error(String(detail))
                                        },
                                    }
                                )
                            }}
                        />
                    )}
                    {activeTab === 'history' && (
                        <PromptHistoryList prompts={prompts.data || []} />
                    )}
                </div>

                {/* Right Sidebar - Status & Stats */}
                <div className="col-span-12 lg:col-span-4 space-y-6">
                    <StatusCard />
                    <TipsCard />
                </div>
            </div>
        </div>
    )
}

function TabButton({ active, onClick, icon: Icon, label }: { active: boolean, onClick: () => void, icon: any, label: string }) {
    return (
        <button
            onClick={onClick}
            className={cn(
                "flex items-center gap-2 px-6 py-2.5 rounded-xl font-bold transition-all duration-200",
                active
                    ? "bg-background text-primary shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
            )}
        >
            <Icon className={cn("h-5 w-5", active ? "text-primary" : "text-muted-foreground")} />
            {label}
        </button>
    )
}

function ConfigurationForm({ activePrompt, onSave }: { activePrompt?: any, onSave: (data: any) => void }) {
    const [formData, setFormData] = useState({
        name: activePrompt?.name || '',
        llm_model: activePrompt?.llm_model || 'anthropic/claude-3.5-sonnet',
        embedding_model: activePrompt?.embedding_model || 'openai/text-embedding-3-small',
        system_prompt: activePrompt?.system_prompt || '',
        welcome_message: activePrompt?.welcome_message || '',
        handoff_criteria: activePrompt?.handoff_criteria || '',
        is_active: true
    })

    React.useEffect(() => {
        if (activePrompt) {
            setFormData({
                name: activePrompt.name,
                llm_model: activePrompt.llm_model || 'anthropic/claude-3.5-sonnet',
                embedding_model: activePrompt.embedding_model || 'openai/text-embedding-3-small',
                system_prompt: activePrompt.system_prompt,
                welcome_message: activePrompt.welcome_message || '',
                handoff_criteria: activePrompt.handoff_criteria || '',
                is_active: true
            })
        }
    }, [activePrompt])

    const promptHelpers = [
        { label: 'СТАТУСЫ', tags: ['NEW', 'CONSULTING', 'QUALIFIED', 'MEASUREMENT', 'LOST'], color: 'text-blue-500' },
        { label: 'ПОЛЯ ДАННЫХ', tags: ['message', 'client_name', 'phone', 'property_type', 'area_sqm', 'address', 'renovation_type', 'budget', 'deadline', 'is_hot_lead'], color: 'text-purple-500' }
    ]

    return (
        <div className="bg-card border rounded-3xl p-8 shadow-xl relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full -mr-16 -mt-16 group-hover:bg-primary/10 transition-colors duration-500" />

            <div className="space-y-8">
                <div className="flex items-center justify-between">
                    <h3 className="text-xl font-black flex items-center gap-2">
                        <Cpu className="h-6 w-6 text-primary" />
                        НАСТРОЙКИ МОДЕЛИ
                    </h3>
                    <button
                        onClick={() => onSave(formData)}
                        className="bg-primary text-primary-foreground px-6 py-2 rounded-xl font-bold flex items-center gap-2 hover:opacity-90 transition-all shadow-lg shadow-primary/20"
                    >
                        <Save className="h-5 w-5" />
                        СОХРАНИТЬ ВЕРСИЮ
                    </button>
                </div>

                <div className="grid grid-cols-2 gap-6">
                    <FormField label="НАЗВАНИЕ КОНФИГУРАЦИИ" value={formData.name} onChange={(v) => setFormData({ ...formData, name: v })} placeholder="Напр: Sales Agent v2.1" />
                    <div className="grid grid-cols-2 gap-4">
                        <FormField label="LLM МОДЕЛЬ" value={formData.llm_model} onChange={(v) => setFormData({ ...formData, llm_model: v })} placeholder="openai/gpt-4o" isSelect options={['anthropic/claude-3.5-sonnet', 'openai/gpt-4o', 'google/gemini-2.5-flash', 'meta-llama/llama-3.1-70b']} />
                        <div>
                            <FormField
                                label="EMBEDDING МОДЕЛЬ"
                                value={formData.embedding_model}
                                onChange={(v) => setFormData({ ...formData, embedding_model: v })}
                                placeholder="openai/text-embedding-3-small"
                                isSelect
                                options={[
                                    'openai/text-embedding-3-small',
                                    'openai/text-embedding-3-large',
                                    'openai/text-embedding-ada-002',
                                    'google/gemini-embedding-001'
                                ]}
                            />
                            <p className="text-[10px] text-muted-foreground mt-1 ml-1 italic">
                                * База данных настроена на 1536 измерений (используйте 'small' или 'ada-002').
                                {formData.embedding_model.includes('large') && <span className="text-destructive font-bold block">! Внимание: 'large' имеет 3072 измерения и вызовет ошибку.</span>}
                            </p>
                        </div>
                    </div>
                </div>

                <div className="space-y-6">
                    <TextAreaField
                        label="СИСТЕМНЫЙ ПРОМПТ (LMM)"
                        value={formData.system_prompt}
                        onChange={(v) => setFormData({ ...formData, system_prompt: v })}
                        placeholder="Опишите личность и правила поведения агента..."
                        rows={10}
                        helpers={promptHelpers}
                    />
                    <div className="grid grid-cols-2 gap-6">
                        <TextAreaField
                            label="ПРИВЕТСТВИЕ"
                            value={formData.welcome_message}
                            onChange={(v) => setFormData({ ...formData, welcome_message: v })}
                            placeholder="Первое сообщение лиду..."
                        />
                        <TextAreaField
                            label="КРИТЕРИИ ПЕРЕДАЧИ (HANDOFF)"
                            value={formData.handoff_criteria}
                            onChange={(v) => setFormData({ ...formData, handoff_criteria: v })}
                            placeholder="Когда звать менеджера..."
                        />
                    </div>
                </div>
            </div>
        </div>
    )
}

function KnowledgeBasePanel({ items, isLoading, isAdding, onAdd, onUpload, onDelete, onSearch, onClearAll }: { items: any[], isLoading: boolean, isAdding: boolean, onAdd: (data: any) => void, onUpload: (f: File, c: string) => void, onDelete: (id: string) => void, onSearch: (q: string) => void, onClearAll: () => void }) {
    const [newItem, setNewItem] = useState({ title: '', content: '', category: 'FAQ' })
    const [searchQuery, setSearchQuery] = useState('')
    const fileInputRef = React.useRef<HTMLInputElement>(null)

    const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) {
            onUpload(file, newItem.category)
        }
    }

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-2 gap-6 h-[600px]">
                {/* Left: Add New & Search & Upload */}
                <div className="space-y-6 flex flex-col">
                    {/* Search Bar */}
                    <div className="bg-card border rounded-2xl p-4 shadow-sm flex items-center gap-4">
                        <Search className="h-5 w-5 text-muted-foreground" />
                        <input
                            type="text"
                            placeholder="Тестировать поиск..."
                            className="flex-1 bg-transparent border-none focus:ring-0 font-medium"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && onSearch(searchQuery)}
                        />
                        <button onClick={() => onSearch(searchQuery)} className="text-primary font-bold text-sm">ПОИСК</button>
                    </div>

                    {/* Add New Item */}
                    <div className="bg-card border rounded-3xl p-6 shadow-xl flex-1 flex flex-col">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-black flex items-center gap-2">
                                <Plus className="h-5 w-5 text-primary" />
                                ДОБАВИТЬ ДАННЫЕ
                            </h3>
                            <div className="flex gap-2">
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    className="hidden"
                                    accept=".pdf,.txt"
                                    onChange={handleFileUpload}
                                />
                                <button
                                    onClick={() => fileInputRef.current?.click()}
                                    disabled={isAdding}
                                    className="bg-primary/10 text-primary px-4 py-1.5 rounded-lg text-xs font-black uppercase hover:bg-primary hover:text-primary-foreground transition-all disabled:opacity-50 flex items-center gap-2"
                                >
                                    {isAdding && <Loader2 className="h-3 w-3 animate-spin" />}
                                    Загрузить PDF/TXT
                                </button>
                            </div>
                        </div>

                        <div className="space-y-4 flex-1 flex flex-col">
                            <input
                                placeholder="Заголовок (для ручного ввода)"
                                className="w-full bg-muted border-none rounded-xl px-4 py-2.5 font-medium"
                                value={newItem.title}
                                onChange={(e) => setNewItem({ ...newItem, title: e.target.value })}
                            />
                            <select
                                className="w-full bg-muted border-none rounded-xl px-4 py-2.5 font-medium"
                                value={newItem.category}
                                onChange={(e) => setNewItem({ ...newItem, category: e.target.value })}
                            >
                                <option value="FAQ">FAQ / Ответы</option>
                                <option value="pricing">Цены / Сметы</option>
                                <option value="portfolio">Портфолио</option>
                                <option value="general">Общая инфо</option>
                            </select>
                            <textarea
                                className="w-full bg-muted border-none rounded-xl px-4 py-2.5 font-medium flex-1 resize-none"
                                placeholder="Текст для индексации или выберите файл выше..."
                                value={newItem.content}
                                onChange={(e) => setNewItem({ ...newItem, content: e.target.value })}
                            />
                            <button
                                onClick={() => {
                                    if (newItem.content && newItem.title) {
                                        onAdd(newItem)
                                        setNewItem({ title: '', content: '', category: 'FAQ' })
                                    }
                                }}
                                disabled={isAdding || !newItem.content || !newItem.title}
                                className="w-full bg-primary text-primary-foreground py-2.5 rounded-xl font-black shadow-lg shadow-primary/20 disabled:opacity-50 flex items-center justify-center gap-2"
                            >
                                {isAdding && <Loader2 className="h-4 w-4 animate-spin" />}
                                ИНДЕКСИРОВАТЬ ТЕКСТ
                            </button>
                        </div>
                    </div>
                </div>

                {/* Right: Existing Items List */}
                <div className="bg-card border rounded-3xl p-6 shadow-sm overflow-hidden flex flex-col">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-black flex items-center gap-2">
                            <Database className="h-5 w-5 text-primary" />
                            БАЗА ЗНАНИЙ ({items.length})
                        </h3>
                        {items.length > 0 && (
                            <button
                                onClick={onClearAll}
                                className="text-[10px] font-black text-destructive/50 hover:text-destructive transition-colors uppercase tracking-widest border-b border-transparent hover:border-destructive"
                            >
                                Очистить всё
                            </button>
                        )}
                    </div>
                    <div className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-thin scrollbar-thumb-primary/10">
                        {isLoading ? (
                            <div className="flex flex-col items-center justify-center h-full gap-4">
                                <Loader2 className="h-8 w-8 text-primary animate-spin" />
                                <span className="text-sm font-bold text-muted-foreground">ЗАГРУЗКА БАЗЫ...</span>
                            </div>
                        ) : items.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-full text-muted-foreground italic gap-4">
                                <Search className="h-12 w-12 opacity-10" />
                                <span>База знаний пуста</span>
                            </div>
                        ) : (
                            items.map((item) => (
                                <div key={item.id} className="p-3 bg-muted/30 rounded-xl border border-transparent hover:border-primary/20 transition-all group relative">
                                    <div className="flex justify-between items-start mb-1">
                                        <span className="font-bold text-sm truncate max-w-[150px]">{item.title}</span>
                                        <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full font-black uppercase">{item.category}</span>
                                    </div>
                                    <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed group-hover:line-clamp-none transition-all">
                                        {item.content}
                                    </p>
                                    <div className="mt-2 flex justify-between items-center">
                                        <div className="text-[9px] text-muted-foreground/50 font-medium">
                                            ID: {item.id.slice(0, 8)}... • {new Date(item.created_at).toLocaleDateString()}
                                        </div>
                                        <button
                                            onClick={() => onDelete(item.id)}
                                            className="opacity-0 group-hover:opacity-100 p-1 text-destructive hover:bg-destructive/10 rounded transition-all"
                                        >
                                            <Trash2 className="h-3 w-3" />
                                        </button>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

function OperatorsPanel({
    operators,
    accessRequests,
    isLoading,
    isRequestsLoading,
    isSaving,
    onCreate,
    onUpdate,
    onDelete,
    onApproveRequest,
    onRejectRequest,
}: {
    operators: any[]
    accessRequests: OperatorAccessRequest[]
    isLoading: boolean
    isRequestsLoading: boolean
    isSaving: boolean
    onCreate: (payload: OperatorCreatePayload) => void
    onUpdate: (id: string, payload: OperatorUpdatePayload) => void
    onDelete: (id: string) => void
    onApproveRequest: (id: string, payload: { role: 'MANAGER' | 'WORKER' }) => void
    onRejectRequest: (id: string, reason?: string) => void
}) {
    const [createForm, setCreateForm] = useState({
        telegram_id: '',
        full_name: '',
        username: '',
        phone: '',
        email: '',
        role: 'MANAGER' as 'MANAGER' | 'WORKER',
    })
    const [drafts, setDrafts] = useState<Record<string, any>>({})
    const [requestRoles, setRequestRoles] = useState<Record<string, 'MANAGER' | 'WORKER'>>({})

    React.useEffect(() => {
        const nextDrafts: Record<string, any> = {}
        for (const user of operators) {
            nextDrafts[user.id] = {
                full_name: user.full_name || '',
                username: user.username || '',
                phone: user.phone || '',
                email: user.email || '',
                role: user.role || 'MANAGER',
            }
        }
        setDrafts(nextDrafts)
    }, [operators])

    const normalize = (value: string) => value.trim() || undefined

    React.useEffect(() => {
        setRequestRoles((prev) => {
            const next: Record<string, 'MANAGER' | 'WORKER'> = {}
            for (const request of accessRequests) {
                next[request.id] = prev[request.id] || 'MANAGER'
            }
            return next
        })
    }, [accessRequests])

    return (
        <div className="space-y-6">
            <div className="bg-card border rounded-3xl p-6 shadow-xl">
                <h3 className="text-lg font-black mb-4">Заявки на доступ ({accessRequests.length})</h3>
                {isRequestsLoading ? (
                    <div className="flex items-center gap-3 text-muted-foreground">
                        <Loader2 className="h-5 w-5 animate-spin text-primary" />
                        <span>Загрузка заявок...</span>
                    </div>
                ) : accessRequests.length === 0 ? (
                    <div className="text-sm text-muted-foreground">Новых заявок нет.</div>
                ) : (
                    <div className="space-y-3">
                        {accessRequests.map((request) => (
                            <div key={request.id} className="border rounded-2xl p-4 space-y-3">
                                <div className="flex items-center justify-between gap-4">
                                    <div>
                                        <div className="font-bold text-sm">{request.full_name || `@${request.username || 'unknown'}`}</div>
                                        <div className="text-xs text-muted-foreground">
                                            Telegram ID: {request.telegram_id}
                                            {request.username ? ` • @${request.username}` : ''}
                                            {` • ${new Date(request.created_at).toLocaleString('ru-RU')}`}
                                        </div>
                                    </div>
                                    <select
                                        className="bg-muted border-none rounded-xl px-3 py-2 text-sm font-medium"
                                        value={requestRoles[request.id] || 'MANAGER'}
                                        onChange={(e) =>
                                            setRequestRoles((prev) => ({
                                                ...prev,
                                                [request.id]: e.target.value as 'MANAGER' | 'WORKER',
                                            }))
                                        }
                                    >
                                        <option value="MANAGER">MANAGER</option>
                                        <option value="WORKER">WORKER</option>
                                    </select>
                                </div>
                                <div className="flex items-center gap-2">
                                    <button
                                        disabled={isSaving}
                                        className="bg-emerald-600 text-white px-4 py-2 rounded-xl text-sm font-bold disabled:opacity-50"
                                        onClick={() =>
                                            onApproveRequest(request.id, { role: requestRoles[request.id] || 'MANAGER' })
                                        }
                                    >
                                        Одобрить
                                    </button>
                                    <button
                                        disabled={isSaving}
                                        className="bg-destructive/10 text-destructive px-4 py-2 rounded-xl text-sm font-bold disabled:opacity-50"
                                        onClick={() => {
                                            const reason = window.prompt('Причина отклонения (необязательно):') || undefined
                                            onRejectRequest(request.id, reason)
                                        }}
                                    >
                                        Отклонить
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div className="bg-card border rounded-3xl p-6 shadow-xl space-y-4">
                <h3 className="text-xl font-black flex items-center gap-2">
                    <UserCog className="h-6 w-6 text-primary" />
                    ДОБАВИТЬ ОПЕРАТОРА
                </h3>
                <div className="grid grid-cols-2 gap-4">
                    <FormField
                        label="Telegram ID"
                        value={createForm.telegram_id}
                        onChange={(v) => setCreateForm((prev) => ({ ...prev, telegram_id: v.replace(/[^\d]/g, '') }))}
                        placeholder="123456789"
                    />
                    <FormField
                        label="Роль"
                        value={createForm.role}
                        onChange={(v) => setCreateForm((prev) => ({ ...prev, role: v as 'MANAGER' | 'WORKER' }))}
                        isSelect
                        options={['MANAGER', 'WORKER']}
                    />
                    <FormField
                        label="ФИО"
                        value={createForm.full_name}
                        onChange={(v) => setCreateForm((prev) => ({ ...prev, full_name: v }))}
                        placeholder="Иванов Иван"
                    />
                    <FormField
                        label="Username"
                        value={createForm.username}
                        onChange={(v) => setCreateForm((prev) => ({ ...prev, username: v }))}
                        placeholder="@username"
                    />
                    <FormField
                        label="Телефон"
                        value={createForm.phone}
                        onChange={(v) => setCreateForm((prev) => ({ ...prev, phone: v }))}
                        placeholder="+79991234567"
                    />
                    <FormField
                        label="Email"
                        value={createForm.email}
                        onChange={(v) => setCreateForm((prev) => ({ ...prev, email: v }))}
                        placeholder="operator@company.com"
                    />
                </div>
                <button
                    disabled={isSaving || !createForm.telegram_id}
                    className="bg-primary text-primary-foreground px-5 py-2 rounded-xl font-bold disabled:opacity-50 flex items-center gap-2"
                    onClick={() => {
                        onCreate({
                            telegram_id: Number(createForm.telegram_id),
                            full_name: normalize(createForm.full_name),
                            username: normalize(createForm.username),
                            phone: normalize(createForm.phone),
                            email: normalize(createForm.email),
                            role: createForm.role,
                        })
                        setCreateForm({
                            telegram_id: '',
                            full_name: '',
                            username: '',
                            phone: '',
                            email: '',
                            role: 'MANAGER',
                        })
                    }}
                >
                    {isSaving && <Loader2 className="h-4 w-4 animate-spin" />}
                    Добавить оператора
                </button>
            </div>

            <div className="bg-card border rounded-3xl p-6 shadow-xl">
                <h3 className="text-lg font-black mb-4">Список операторов ({operators.length})</h3>
                {isLoading ? (
                    <div className="flex items-center gap-3 text-muted-foreground">
                        <Loader2 className="h-5 w-5 animate-spin text-primary" />
                        <span>Загрузка операторов...</span>
                    </div>
                ) : operators.length === 0 ? (
                    <div className="text-sm text-muted-foreground">Операторы ещё не добавлены.</div>
                ) : (
                    <div className="space-y-4">
                        {operators.map((user) => {
                            const draft = drafts[user.id] || {}
                            return (
                                <div key={user.id} className="border rounded-2xl p-4 space-y-3">
                                    <div className="text-xs text-muted-foreground">Telegram ID: {user.telegram_id || '—'}</div>
                                    <div className="grid grid-cols-2 gap-3">
                                        <input
                                            className="w-full bg-muted border-none rounded-xl px-4 py-2.5 text-sm font-medium"
                                            placeholder="ФИО"
                                            value={draft.full_name || ''}
                                            onChange={(e) => setDrafts((prev) => ({ ...prev, [user.id]: { ...prev[user.id], full_name: e.target.value } }))}
                                        />
                                        <input
                                            className="w-full bg-muted border-none rounded-xl px-4 py-2.5 text-sm font-medium"
                                            placeholder="Username"
                                            value={draft.username || ''}
                                            onChange={(e) => setDrafts((prev) => ({ ...prev, [user.id]: { ...prev[user.id], username: e.target.value } }))}
                                        />
                                        <input
                                            className="w-full bg-muted border-none rounded-xl px-4 py-2.5 text-sm font-medium"
                                            placeholder="Телефон"
                                            value={draft.phone || ''}
                                            onChange={(e) => setDrafts((prev) => ({ ...prev, [user.id]: { ...prev[user.id], phone: e.target.value } }))}
                                        />
                                        <input
                                            className="w-full bg-muted border-none rounded-xl px-4 py-2.5 text-sm font-medium"
                                            placeholder="Email"
                                            value={draft.email || ''}
                                            onChange={(e) => setDrafts((prev) => ({ ...prev, [user.id]: { ...prev[user.id], email: e.target.value } }))}
                                        />
                                        <select
                                            className="w-full bg-muted border-none rounded-xl px-4 py-2.5 text-sm font-medium"
                                            value={draft.role || 'MANAGER'}
                                            onChange={(e) => setDrafts((prev) => ({ ...prev, [user.id]: { ...prev[user.id], role: e.target.value } }))}
                                        >
                                            <option value="MANAGER">MANAGER</option>
                                            <option value="WORKER">WORKER</option>
                                        </select>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            disabled={isSaving}
                                            className="bg-primary text-primary-foreground px-4 py-2 rounded-xl text-sm font-bold disabled:opacity-50"
                                            onClick={() =>
                                                onUpdate(user.id, {
                                                    full_name: normalize(draft.full_name || ''),
                                                    username: normalize(draft.username || ''),
                                                    phone: normalize(draft.phone || ''),
                                                    email: normalize(draft.email || ''),
                                                    role: draft.role,
                                                })
                                            }
                                        >
                                            Сохранить
                                        </button>
                                        <button
                                            disabled={isSaving}
                                            className="bg-destructive/10 text-destructive px-4 py-2 rounded-xl text-sm font-bold disabled:opacity-50"
                                            onClick={() => {
                                                if (window.confirm('Удалить оператора?')) onDelete(user.id)
                                            }}
                                        >
                                            Удалить
                                        </button>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                )}
            </div>
        </div>
    )
}

function PromptHistoryList({ prompts }: { prompts: any[] }) {
    return (
        <div className="bg-card border rounded-3xl p-8 shadow-xl">
            <h3 className="text-xl font-black mb-6 flex items-center gap-2">
                <History className="h-6 w-6 text-primary" />
                ИСТОРИЯ ИЗМЕНЕНИЙ
            </h3>
            <div className="space-y-4">
                {prompts.map((p) => (
                    <div key={p.id} className="flex items-center justify-between p-4 bg-muted/50 rounded-2xl border border-transparent hover:border-primary/20 transition-all group">
                        <div className="flex items-center gap-4">
                            <div className={cn(
                                "h-3 w-3 rounded-full",
                                p.is_active ? "bg-green-500 shadow-sm shadow-green-500/50" : "bg-muted-foreground/30"
                            )} />
                            <div>
                                <div className="font-bold">{p.name}</div>
                                <div className="text-xs text-muted-foreground">{new Date(p.created_at).toLocaleString('ru-RU')} • {p.llm_model}</div>
                            </div>
                        </div>
                        <button className="opacity-0 group-hover:opacity-100 bg-background px-4 py-1.5 rounded-lg text-xs font-bold shadow-sm transition-all border">
                            ВОССТАНОВИТЬ
                        </button>
                    </div>
                ))}
            </div>
        </div>
    )
}

function StatusCard() {
    return (
        <div className="bg-primary text-primary-foreground rounded-3xl p-8 shadow-2xl shadow-primary/30 relative overflow-hidden group">
            <Zap className="absolute -bottom-4 -right-4 h-32 w-32 opacity-10 group-hover:scale-110 transition-transform duration-700" />
            <div className="relative space-y-4">
                <div className="flex items-center gap-2 text-xs font-black tracking-widest opacity-70 uppercase">Статус Системы</div>
                <div className="text-4xl font-black leading-none">AI ONLINE</div>
                <div className="space-y-2">
                    <div className="flex justify-between text-sm font-bold">
                        <span>Успешных квалификаций</span>
                        <span>84%</span>
                    </div>
                    <div className="h-2 bg-primary-foreground/20 rounded-full overflow-hidden">
                        <div className="h-full bg-primary-foreground w-[84%] animate-pulse" />
                    </div>
                </div>
            </div>
        </div>
    )
}

function TipsCard() {
    return (
        <div className="bg-card border rounded-3xl p-8 space-y-4 shadow-sm">
            <h3 className="font-black text-lg flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-primary" />
                СОВЕТЫ AI
            </h3>
            <ul className="space-y-3 text-sm text-muted-foreground font-medium">
                <li className="flex gap-2">
                    <div className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 flex-shrink-0" />
                    <span>Используйте <b>Claude 3.5 Sonnet</b> для лучшей точности извлечения данных.</span>
                </li>
                <li className="flex gap-2">
                    <div className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 flex-shrink-0" />
                    <span>Добавляйте реальные диалоги в системный промпт как примеры (Few-shot prompting).</span>
                </li>
                <li className="flex gap-2">
                    <div className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 flex-shrink-0" />
                    <span>Обновляйте базу знаний RAG при изменении цен или условий работ.</span>
                </li>
            </ul>
        </div>
    )
}

function FormField({ label, value, onChange, placeholder, isSelect, options }: { label: string, value: string, onChange: (v: string) => void, placeholder?: string, isSelect?: boolean, options?: string[] }) {
    return (
        <div className="space-y-1.5">
            <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground ml-1">{label}</label>
            {isSelect ? (
                <select
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    className="w-full bg-muted border-none rounded-xl px-4 py-3 focus:ring-2 ring-primary transition-all font-bold"
                >
                    {options?.map((opt: string) => (
                        <option key={opt} value={opt}>{opt}</option>
                    ))}
                </select>
            ) : (
                <input
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    placeholder={placeholder}
                    className="w-full bg-muted border-none rounded-xl px-4 py-3 focus:ring-2 ring-primary transition-all font-bold"
                />
            )}
        </div>
    )
}

function TextAreaField({ label, value, onChange, placeholder, rows = 3, helpers }: { label: string, value: string, onChange: (v: string) => void, placeholder?: string, rows?: number, helpers?: { label: string, tags: string[], color: string }[] }) {
    const textareaRef = React.useRef<HTMLTextAreaElement>(null)

    const insertTag = (tag: string) => {
        if (!textareaRef.current) return
        const start = textareaRef.current.selectionStart
        const end = textareaRef.current.selectionEnd
        const text = value
        const before = text.substring(0, start)
        const after = text.substring(end)
        const wrappedTag = `{${tag}}`
        const newValue = before + wrappedTag + after
        onChange(newValue)

        // Restore focus and selection
        setTimeout(() => {
            if (textareaRef.current) {
                textareaRef.current.focus()
                textareaRef.current.setSelectionRange(start + wrappedTag.length, start + wrappedTag.length)
            }
        }, 0)
    }

    return (
        <div className="space-y-2">
            <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground ml-1">{label}</label>
            <div className="relative group/textarea">
                <textarea
                    ref={textareaRef}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    placeholder={placeholder}
                    rows={rows}
                    className="w-full bg-muted border-none rounded-2xl px-4 py-4 focus:ring-2 ring-primary transition-all font-medium leading-relaxed resize-none shadow-inner"
                />

                {helpers && (
                    <div className="mt-3 flex flex-wrap gap-4">
                        {helpers.map((group, i) => (
                            <div key={i} className="flex flex-col gap-1.5">
                                <span className="text-[9px] font-black text-muted-foreground/60 tracking-tighter uppercase pl-1">{group.label}</span>
                                <div className="flex flex-wrap gap-1.5">
                                    {group.tags.map(tag => (
                                        <button
                                            key={tag}
                                            onClick={() => insertTag(tag)}
                                            className={cn(
                                                "px-2.5 py-1 rounded-lg text-[10px] font-bold border border-transparent hover:border-current transition-all bg-background shadow-sm hover:shadow-md",
                                                group.color
                                            )}
                                        >
                                            {tag}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}
