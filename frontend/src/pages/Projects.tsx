import React, { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { HardHat, MapPin, User, Plus, Search, X } from 'lucide-react'
import { ProjectWorkspace } from '@/components/projects/ProjectWorkspace'
import { useProjects, useCreateProject } from '@/hooks/useProjects'

interface Project {
    id: string
    name: string
    address: string
    description: string | null
    budget_total: number
    budget_spent: number
    client_id: string | null
    created_at: string
}

export function Projects() {
    const [searchParams] = useSearchParams()
    const [search, setSearch] = useState('')
    const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
    const [showCreateModal, setShowCreateModal] = useState(false)

    const { data: projects, isLoading } = useProjects()

    useEffect(() => {
        const projectId = searchParams.get('id')
        if (projectId) {
            setSelectedProjectId(projectId)
        }
    }, [searchParams])

    const selectedProject = projects?.find((p: Project) => p.id === selectedProjectId) || null

    const filteredProjects = projects?.filter((p: Project) =>
        p.name.toLowerCase().includes(search.toLowerCase()) ||
        p.address.toLowerCase().includes(search.toLowerCase())
    ) || []

    return (
        <div className="h-full flex flex-col gap-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Объекты в работе</h2>
                    <p className="text-sm text-muted-foreground">Управление активными ремонтами и командой</p>
                </div>

                <div className="flex items-center gap-4">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <input
                            type="text"
                            placeholder="Поиск объектов..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="h-10 w-64 rounded-lg border bg-background pl-10 pr-4 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                        />
                    </div>
                    <button
                        onClick={() => setShowCreateModal(true)}
                        className="flex h-10 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-all hover:opacity-90 shadow-sm"
                    >
                        <Plus className="h-4 w-4" />
                        Новый объект
                    </button>
                </div>
            </div>

            {isLoading ? (
                <div className="flex h-64 items-center justify-center">
                    <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                </div>
            ) : filteredProjects.length === 0 ? (
                <div className="flex h-96 flex-col items-center justify-center rounded-2xl border border-dashed bg-card/50 text-center p-12">
                    <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                        <HardHat className="h-8 w-8 text-muted-foreground opacity-20" />
                    </div>
                    <h3 className="text-lg font-semibold">Нет активных объектов</h3>
                    <p className="mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
                        Сюда попадают лиды, которые перешли на этап «Контракт». Начните с конвертации лида или создайте проект вручную.
                    </p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {filteredProjects.map((project: Project) => (
                        <ProjectCard
                            key={project.id}
                            project={project}
                            onClick={() => setSelectedProjectId(project.id)}
                        />
                    ))}
                </div>
            )}

            {selectedProject && (
                <ProjectWorkspace
                    project={selectedProject}
                    onClose={() => setSelectedProjectId(null)}
                />
            )}

            {showCreateModal && (
                <CreateProjectModal onClose={() => setShowCreateModal(false)} />
            )}
        </div>
    )
}

function CreateProjectModal({ onClose }: { onClose: () => void }) {
    const createProject = useCreateProject()
    const [formData, setFormData] = useState({
        name: '',
        address: '',
        description: '',
        budget_total: 0
    })

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        createProject.mutate(formData, {
            onSuccess: () => onClose()
        })
    }

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div className="relative w-full max-w-md rounded-2xl bg-background shadow-2xl scale-in-center">
                <div className="flex items-center justify-between border-b px-6 py-4">
                    <h3 className="text-lg font-bold">Новый объект</h3>
                    <button onClick={onClose} className="rounded-full p-1 hover:bg-muted">
                        <X className="h-5 w-5" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    <div className="space-y-1.5">
                        <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Название объекта</label>
                        <input
                            required
                            type="text"
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            className="w-full rounded-lg border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                            placeholder="Напр: Квартира на Ленина 24"
                        />
                    </div>

                    <div className="space-y-1.5">
                        <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Адрес</label>
                        <input
                            required
                            type="text"
                            value={formData.address}
                            onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                            className="w-full rounded-lg border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                            placeholder="Полный адрес"
                        />
                    </div>

                    <div className="space-y-1.5">
                        <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Бюджет (₽)</label>
                        <input
                            type="number"
                            value={formData.budget_total}
                            onChange={(e) => setFormData({ ...formData, budget_total: Number(e.target.value) })}
                            className="w-full rounded-lg border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                        />
                    </div>

                    <div className="space-y-1.5">
                        <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Описание</label>
                        <textarea
                            value={formData.description}
                            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                            className="w-full rounded-lg border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary h-24 resize-none"
                            placeholder="Дополнительные детали..."
                        />
                    </div>

                    <div className="pt-4 flex gap-3">
                        <button
                            type="button"
                            onClick={onClose}
                            className="flex-1 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                        >
                            Отмена
                        </button>
                        <button
                            disabled={createProject.isPending}
                            type="submit"
                            className="flex-1 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
                        >
                            {createProject.isPending ? 'Создание...' : 'Создать объект'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}

function ProjectCard({ project, onClick }: { project: Project; onClick: () => void }) {
    const progress = project.budget_total > 0
        ? Math.round((project.budget_spent / project.budget_total) * 100)
        : 0

    return (
        <div className="group cursor-pointer rounded-2xl border bg-card p-5 shadow-sm transition-all hover:border-primary/50 hover:shadow-md" onClick={onClick}>
            <div className="mb-4 flex items-start justify-between">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <HardHat className="h-6 w-6" />
                </div>
                <div className="rounded-full bg-emerald-100 px-2.5 py-1 text-[10px] font-bold text-emerald-700 uppercase tracking-wider">
                    Активен
                </div>
            </div>

            <div className="space-y-3">
                <div>
                    <h3 className="font-bold text-lg leading-tight group-hover:text-primary transition-colors">{project.name}</h3>
                    <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
                        <MapPin className="h-3.5 w-3.5" />
                        {project.address}
                    </p>
                </div>

                <div className="space-y-2 pt-2">
                    <div className="flex justify-between text-xs font-medium">
                        <span className="text-muted-foreground uppercase tracking-widest">Прогресс бюджета</span>
                        <span>{progress}%</span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                        <div
                            className="h-full bg-primary transition-all duration-500"
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                </div>

                <div className="flex items-center justify-between pt-4 border-t">
                    <div className="flex items-center gap-2">
                        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-[10px] font-bold">
                            <User className="h-3 w-3" />
                        </div>
                        <span className="text-xs font-medium text-slate-600">Бригада не назначена</span>
                    </div>
                    <span className="text-[10px] font-bold text-muted-foreground uppercase">
                        {new Date(project.created_at).toLocaleDateString()}
                    </span>
                </div>
            </div>
        </div>
    )
}
