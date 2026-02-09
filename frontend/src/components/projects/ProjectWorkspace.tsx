import React, { useState, useEffect } from 'react'
import {
    X, MapPin, Home, DollarSign,
    FileText, ClipboardList, Plus, Send, Image as ImageIcon,
    Clock, User, ShieldCheck, MessageSquare, Settings, Trash2, Edit2, Save
} from 'lucide-react'
import { useUpdateProject, useDeleteProject } from '@/hooks/useProjects'

interface Project {
    id: string
    name: string
    address: string
    description: string | null
    budget_total: number | string
    budget_spent: number | string
    client_id: string | null
    created_at: string
}

interface ProjectWorkspaceProps {
    project: Project
    onClose: () => void
}

export function ProjectWorkspace({ project, onClose }: ProjectWorkspaceProps) {
    const [activeTab, setActiveTab] = useState<'info' | 'reports' | 'settings'>('info')
    const [notification, setNotification] = useState<{ message: string, type: 'success' | 'error' } | null>(null)

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div className="relative w-full max-w-[1240px] h-[90vh] overflow-hidden rounded-2xl bg-background shadow-2xl flex flex-col scale-in-center">

                {/* Header */}
                <div className="flex items-center justify-between border-b px-6 py-4 bg-card">
                    <div className="flex items-center gap-4">
                        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                            <Home className="h-6 w-6" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold leading-tight">{project.name}</h2>
                            <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
                                <span className="flex items-center gap-1"><MapPin className="h-3 w-3" /> {project.address}</span>
                                <span>• ID: {project.id.slice(0, 8)}</span>
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-2 bg-muted/50 p-1 rounded-lg">
                        <button
                            onClick={() => setActiveTab('info')}
                            className={`px-4 py-2 text-sm font-medium rounded-md transition-all ${activeTab === 'info' ? 'bg-background shadow-sm text-primary' : 'text-muted-foreground'
                                }`}
                        >
                            Управление
                        </button>
                        <button
                            onClick={() => setActiveTab('reports')}
                            className={`px-4 py-2 text-sm font-medium rounded-md transition-all ${activeTab === 'reports' ? 'bg-background shadow-sm text-primary' : 'text-muted-foreground'
                                }`}
                        >
                            Отчеты и Чат
                        </button>
                        <button
                            onClick={() => setActiveTab('settings')}
                            className={`px-4 py-2 text-sm font-medium rounded-md transition-all ${activeTab === 'settings' ? 'bg-background shadow-sm text-primary' : 'text-muted-foreground'
                                }`}
                        >
                            <Settings className="h-4 w-4" />
                        </button>
                    </div>

                    <div className="flex items-center gap-3">
                        <button onClick={onClose} className="rounded-full p-2 hover:bg-muted transition-colors">
                            <X className="h-5 w-5" />
                        </button>
                    </div>
                </div>

                {/* Content Workspace */}
                <div className="flex-1 flex overflow-hidden relative">
                    {/* Notification Toast */}
                    {notification && (
                        <div className={`absolute bottom-8 left-1/2 -translate-x-1/2 z-[100] px-6 py-3 rounded-xl shadow-2xl animate-in slide-in-from-bottom-4 duration-300 flex items-center gap-3 border ${notification.type === 'success' ? 'bg-emerald-500 border-emerald-400 text-white' : 'bg-red-500 border-red-400 text-white'
                            }`}>
                            <ShieldCheck className="h-5 w-5" />
                            <span className="font-bold text-sm tracking-wide">{notification.message}</span>
                            <button onClick={() => setNotification(null)} className="ml-2 hover:opacity-70">
                                <X className="h-4 w-4" />
                            </button>
                        </div>
                    )}

                    {activeTab === 'info' ? (
                        <ProjectInfoTab project={project} />
                    ) : activeTab === 'reports' ? (
                        <ProjectReportsTab project={project} />
                    ) : (
                        <ProjectSettingsTab project={project} onClose={onClose} setNotification={setNotification} />
                    )}
                </div>
            </div>
        </div>
    )
}

function ProjectInfoTab({ project }: { project: Project }) {
    return (
        <div className="flex-1 flex overflow-hidden">
            {/* Left Column: Management */}
            <div className="w-[40%] border-r bg-slate-50/50 flex flex-col overflow-y-auto custom-scrollbar p-6 space-y-8">
                <section>
                    <h3 className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                        <User className="h-4 w-4" /> Команда объекта
                    </h3>
                    <div className="space-y-3">
                        <div className="flex items-center justify-between p-4 rounded-xl border bg-white shadow-sm transition-all hover:border-primary/30">
                            <div className="flex items-center gap-3">
                                <div className="h-10 w-10 flex items-center justify-center rounded-full bg-slate-100 text-slate-400">
                                    <User className="h-5 w-5" />
                                </div>
                                <div>
                                    <div className="text-sm font-bold">Прораб</div>
                                    <div className="text-xs text-muted-foreground">Не назначен</div>
                                </div>
                            </div>
                            <button className="text-xs font-bold text-primary hover:underline">Назначить</button>
                        </div>

                        <div className="flex items-center justify-between p-4 rounded-xl border bg-white shadow-sm transition-all hover:border-primary/30">
                            <div className="flex items-center gap-3">
                                <div className="h-10 w-10 flex items-center justify-center rounded-full bg-slate-100 text-slate-400">
                                    <Plus className="h-5 w-5" />
                                </div>
                                <div className="text-sm font-bold">Бригада</div>
                            </div>
                            <button className="text-xs font-bold text-primary hover:underline">Добавить рабочих</button>
                        </div>
                    </div>
                </section>

                <section>
                    <h3 className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                        <FileText className="h-4 w-4" /> Документация
                    </h3>
                    <div className="grid grid-cols-2 gap-3">
                        <DocButton label="Договор" icon={<FileText className="h-4 w-4" />} />
                        <DocButton label="Смета" icon={<DollarSign className="h-4 w-4" />} />
                        <DocButton label="Проект" icon={<ImageIcon className="h-4 w-4" />} />
                        <DocButton label="Акты" icon={<ClipboardList className="h-4 w-4" />} />
                    </div>
                </section>
            </div>

            {/* Right Column: Progress & Finance */}
            <div className="flex-1 bg-background p-6 space-y-8 overflow-y-auto custom-scrollbar">
                <section className="rounded-2xl border bg-card p-6 shadow-sm">
                    <h3 className="mb-6 text-sm font-bold flex items-center gap-2">
                        <ShieldCheck className="h-5 w-5 text-primary" /> Состояние проекта
                    </h3>
                    <div className="grid grid-cols-3 gap-6">
                        <div className="space-y-1">
                            <div className="text-[10px] font-bold uppercase text-muted-foreground tracking-widest">Текущий этап</div>
                            <div className="text-base font-bold text-primary">Подготовка объекта</div>
                        </div>
                        <div className="space-y-1">
                            <div className="text-[10px] font-bold uppercase text-muted-foreground tracking-widest">Дней в работе</div>
                            <div className="text-base font-bold">0 / 45</div>
                        </div>
                        <div className="space-y-1">
                            <div className="text-[10px] font-bold uppercase text-muted-foreground tracking-widest">Качество</div>
                            <div className="text-base font-bold text-emerald-500">ОК</div>
                        </div>
                    </div>

                    <div className="mt-8 space-y-4">
                        <div className="flex justify-between items-end">
                            <div className="space-y-1">
                                <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Прогресс работ</span>
                                <div className="text-2xl font-black italic">0%</div>
                            </div>
                            <div className="text-xs text-muted-foreground font-medium">Черновые / Инженерка / Чистовые</div>
                        </div>
                        <div className="h-3 w-full rounded-full bg-slate-100 overflow-hidden">
                            <div className="h-full bg-primary w-[5%] rounded-full" />
                        </div>
                    </div>
                </section>

                <div className="grid grid-cols-2 gap-6">
                    <FinanceCard label="Общий бюджет" amount={project.budget_total} color="text-slate-900" />
                    <FinanceCard label="Оплачено клиентом" amount={0} color="text-emerald-600" />
                    <FinanceCard label="Расходы (материалы)" amount={project.budget_spent} color="text-red-600" />
                    <FinanceCard label="Баланс объекта" amount={0} color="text-primary font-bold" />
                </div>
            </div>
        </div>
    )
}

function ProjectReportsTab({ project }: { project: Project }) {
    return (
        <div className="flex-1 flex overflow-hidden">
            {/* Left: Daily Reports Feed */}
            <div className="flex-1 border-r flex flex-col bg-slate-50/30">
                <div className="p-4 border-b bg-card flex items-center justify-between">
                    <h3 className="font-bold flex items-center gap-2 text-sm">
                        <Clock className="h-4 w-4 text-primary" /> Дневник работ
                    </h3>
                    <button className="text-xs font-bold text-primary bg-primary/10 px-3 py-1.5 rounded-full hover:bg-primary/20">
                        Добавить отчет
                    </button>
                </div>
                <div className="flex-1 overflow-y-auto p-6 flex flex-col items-center justify-center text-center space-y-3 opacity-50">
                    <div className="h-16 w-16 bg-slate-200 rounded-full flex items-center justify-center">
                        <FileText className="h-8 w-8 text-slate-400" />
                    </div>
                    <div>
                        <p className="text-sm font-bold">Отчетов пока нет</p>
                        <p className="text-xs text-muted-foreground max-w-[200px] mx-auto mt-1">Прораб еще не загрузил ни одного ежедневного отчета</p>
                    </div>
                </div>
            </div>

            {/* Right: Client Chat (merged with Lead Chat) */}
            <div className="w-[40%] flex flex-col bg-background">
                <div className="p-4 border-b bg-card">
                    <h3 className="font-bold flex items-center gap-2 text-sm">
                        <MessageSquare className="h-4 w-4 text-primary" /> Чат с клиентом
                    </h3>
                </div>
                <div className="flex-1 bg-slate-50/20 p-4">
                    {/* Reuse Chat implementation here in future */}
                    <div className="h-full flex flex-col items-center justify-center opacity-40">
                        <MessageSquare className="h-12 w-12 text-slate-300" />
                        <p className="text-xs mt-2 italic">История диалога загружается...</p>
                    </div>
                </div>
                <div className="p-4 border-t bg-card">
                    <div className="flex gap-2 bg-background rounded-xl border p-1 shadow-inner">
                        <input type="text" placeholder="Написать клиенту..." className="flex-1 px-4 py-2 text-sm outline-none" />
                        <button className="bg-primary p-2 rounded-lg text-primary-foreground">
                            <Send className="h-4 w-4" />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}

function ProjectSettingsTab({ project, onClose, setNotification }: { project: Project, onClose: () => void, setNotification: (n: any) => void }) {
    const updateProject = useUpdateProject()
    const deleteProject = useDeleteProject()
    const [formData, setFormData] = useState({
        name: project.name,
        address: project.address,
        description: project.description || '',
        budget_total: Number(project.budget_total) || 0
    })

    // Sync state if project prop changes (e.g. after refresh)
    useEffect(() => {
        setFormData({
            name: project.name,
            address: project.address,
            description: project.description || '',
            budget_total: Number(project.budget_total) || 0
        })
    }, [project.id, project.name, project.address, project.description, project.budget_total])

    const handleSave = () => {
        updateProject.mutate({
            id: project.id,
            data: formData
        }, {
            onSuccess: () => {
                setNotification({ message: 'Изменения сохранены!', type: 'success' })
                setTimeout(() => setNotification(null), 5000)
            },
            onError: (err: any) => {
                setNotification({ message: 'Ошибка при сохранении: ' + (err.response?.data?.detail || err.message), type: 'error' })
            }
        })
    }

    const handleDelete = () => {
        if (window.confirm('Вы уверены, что хотите удалить этот объект? Это действие невозможно отменить. Лид останется, но все данные проекта будут удалены.')) {
            deleteProject.mutate(project.id, {
                onSuccess: () => onClose()
            })
        }
    }

    return (
        <div className="flex-1 overflow-y-auto p-12 bg-slate-50/30">
            <div className="mx-auto max-w-2xl space-y-12">
                <section className="space-y-6">
                    <div>
                        <h3 className="text-xl font-bold flex items-center gap-2">
                            <Edit2 className="h-5 w-5 text-primary" /> Настройки объекта
                        </h3>
                        <p className="text-sm text-muted-foreground mt-1">Редактирование основных данных и бюджета</p>
                    </div>

                    <div className="grid gap-6 rounded-2xl border bg-card p-8 shadow-sm">
                        <div className="space-y-1.5">
                            <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Название объекта</label>
                            <input
                                type="text"
                                value={formData.name}
                                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                className="w-full rounded-lg border bg-background px-4 py-2.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Адрес</label>
                            <input
                                type="text"
                                value={formData.address}
                                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                                className="w-full rounded-lg border bg-background px-4 py-2.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Бюджет (₽)</label>
                            <input
                                type="number"
                                value={formData.budget_total}
                                onChange={(e) => setFormData({ ...formData, budget_total: Number(e.target.value) })}
                                className="w-full rounded-lg border bg-background px-4 py-2.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Описание</label>
                            <textarea
                                value={formData.description}
                                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                className="w-full rounded-lg border bg-background px-4 py-2.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary h-32 resize-none"
                            />
                        </div>

                        <button
                            onClick={handleSave}
                            disabled={updateProject.isPending}
                            className="flex w-full h-11 items-center justify-center gap-2 rounded-xl bg-primary px-6 text-sm font-bold text-primary-foreground transition-all hover:opacity-90 disabled:opacity-50 shadow-md"
                        >
                            <Save className="h-4 w-4" />
                            {updateProject.isPending ? 'Сохранение...' : 'Сохранить изменения'}
                        </button>
                    </div>
                </section>

                <section className="pt-8 border-t border-red-100">
                    <div className="rounded-2xl border border-red-100 bg-red-50/30 p-8">
                        <div className="flex items-center gap-4 mb-4">
                            <div className="h-10 w-10 flex items-center justify-center rounded-xl bg-red-100 text-red-600">
                                <Trash2 className="h-5 w-5" />
                            </div>
                            <div>
                                <h4 className="text-sm font-bold text-red-900">Опасная зона</h4>
                                <p className="text-xs text-red-600">Удаление объекта безвозвратно сотрет всю историю работ</p>
                            </div>
                        </div>
                        <button
                            onClick={handleDelete}
                            disabled={deleteProject.isPending}
                            className="flex items-center gap-2 rounded-lg border border-red-200 bg-white px-4 py-2 text-xs font-bold text-red-600 hover:bg-red-50 transition-colors"
                        >
                            {deleteProject.isPending ? 'Удаление...' : 'Удалить объект'}
                        </button>
                    </div>
                </section>
            </div>
        </div>
    )
}

function DocButton({ label, icon }: { label: string, icon: React.ReactNode }) {
    return (
        <button className="flex flex-col items-center justify-center gap-2 p-4 rounded-xl border bg-white shadow-sm hover:border-primary/50 hover:bg-slate-50 transition-all">
            <div className="h-10 w-10 flex items-center justify-center rounded-full bg-slate-50 text-slate-400 group-hover:text-primary transition-colors">
                {icon}
            </div>
            <span className="text-xs font-bold text-slate-600">{label}</span>
        </button>
    )
}

function FinanceCard({ label, amount, color }: { label: string, amount: number | string, color: string }) {
    const numericAmount = typeof amount === 'string' ? parseFloat(amount) : amount
    return (
        <div className="bg-card border rounded-2xl p-5 shadow-sm">
            <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-1">{label}</div>
            <div className={`text-xl font-black ${color}`}>
                {isNaN(numericAmount) ? '0' : numericAmount.toLocaleString('ru-RU')} <span className="text-xs font-normal opacity-60">₽</span>
            </div>
        </div>
    )
}
