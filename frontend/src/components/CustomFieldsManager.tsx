import React, { useState, useEffect } from 'react'
import { Plus, Trash2, Edit2, Save, X, GripVertical } from 'lucide-react'

interface CustomField {
    id: string
    field_name: string
    field_label: string
    field_type: 'text' | 'number' | 'select' | 'boolean'
    options?: string[]
    description?: string
    is_active: boolean
    display_order: string
}

interface CustomFieldsManagerProps {
    onFieldsChange?: () => void
}

export default function CustomFieldsManager({ onFieldsChange }: CustomFieldsManagerProps) {
    const [fields, setFields] = useState<CustomField[]>([])
    const [isAdding, setIsAdding] = useState(false)
    const [editingId, setEditingId] = useState<string | null>(null)
    const [loading, setLoading] = useState(true)

    // Form state
    const [formData, setFormData] = useState({
        field_name: '',
        field_label: '',
        field_type: 'text' as 'text' | 'number' | 'select' | 'boolean',
        options: '',
        description: ''
    })

    useEffect(() => {
        fetchFields()
    }, [])

    const fetchFields = async () => {
        try {
            const token = localStorage.getItem('access_token')
            const response = await fetch('/api/custom-fields?active_only=false', {
                headers: { 'Authorization': `Bearer ${token}` }
            })

            if (response.ok) {
                const data = await response.json()
                setFields(data)
            }
        } catch (error) {
            console.error('Failed to fetch custom fields:', error)
        } finally {
            setLoading(false)
        }
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()

        const token = localStorage.getItem('access_token')
        const payload = {
            field_name: formData.field_name,
            field_label: formData.field_label,
            field_type: formData.field_type,
            options: formData.field_type === 'select' ? formData.options.split(',').map(o => o.trim()) : null,
            description: formData.description || null
        }

        try {
            const response = await fetch('/api/custom-fields', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            })

            if (response.ok) {
                await fetchFields()
                resetForm()
                onFieldsChange?.()
            } else {
                const error = await response.json()
                alert(error.detail || 'Failed to create field')
            }
        } catch (error) {
            console.error('Failed to create field:', error)
            alert('Failed to create field')
        }
    }

    const handleDelete = async (id: string) => {
        if (!confirm('Удалить это поле? Данные в лидах сохранятся, но поле исчезнет из интерфейса.')) {
            return
        }

        const token = localStorage.getItem('access_token')
        try {
            const response = await fetch(`/api/custom-fields/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            })

            if (response.ok) {
                await fetchFields()
                onFieldsChange?.()
            }
        } catch (error) {
            console.error('Failed to delete field:', error)
        }
    }

    const handleToggleActive = async (field: CustomField) => {
        const token = localStorage.getItem('access_token')
        try {
            const response = await fetch(`/api/custom-fields/${field.id}`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ is_active: !field.is_active })
            })

            if (response.ok) {
                await fetchFields()
                onFieldsChange?.()
            }
        } catch (error) {
            console.error('Failed to toggle field:', error)
        }
    }

    const resetForm = () => {
        setFormData({
            field_name: '',
            field_label: '',
            field_type: 'text',
            options: '',
            description: ''
        })
        setIsAdding(false)
        setEditingId(null)
    }

    const toSnakeCase = (str: string) => {
        return str
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '_')
            .replace(/^_+|_+$/g, '')
    }

    if (loading) {
        return <div className="text-center py-8 text-muted-foreground">Загрузка...</div>
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-lg font-semibold">Кастомные поля</h3>
                    <p className="text-sm text-muted-foreground">
                        Добавьте свои поля для квалификации лидов. AI будет автоматически извлекать эти данные.
                    </p>
                </div>
                {!isAdding && (
                    <button
                        onClick={() => setIsAdding(true)}
                        className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
                    >
                        <Plus className="h-4 w-4" />
                        Добавить поле
                    </button>
                )}
            </div>

            {/* Add Field Form */}
            {isAdding && (
                <form onSubmit={handleSubmit} className="border rounded-lg p-4 bg-card space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium mb-1">Название поля (англ.)</label>
                            <input
                                type="text"
                                value={formData.field_name}
                                onChange={(e) => setFormData({ ...formData, field_name: toSnakeCase(e.target.value) })}
                                placeholder="foundation_type"
                                className="w-full px-3 py-2 border rounded-lg"
                                required
                            />
                            <p className="text-xs text-muted-foreground mt-1">Только латиница, цифры и _</p>
                        </div>

                        <div>
                            <label className="block text-sm font-medium mb-1">Отображаемое название</label>
                            <input
                                type="text"
                                value={formData.field_label}
                                onChange={(e) => setFormData({ ...formData, field_label: e.target.value })}
                                placeholder="Тип фундамента"
                                className="w-full px-3 py-2 border rounded-lg"
                                required
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium mb-1">Тип поля</label>
                            <select
                                value={formData.field_type}
                                onChange={(e) => setFormData({ ...formData, field_type: e.target.value as any })}
                                className="w-full px-3 py-2 border rounded-lg"
                            >
                                <option value="text">Текст</option>
                                <option value="number">Число</option>
                                <option value="select">Выбор из списка</option>
                                <option value="boolean">Да/Нет</option>
                            </select>
                        </div>

                        {formData.field_type === 'select' && (
                            <div>
                                <label className="block text-sm font-medium mb-1">Варианты (через запятую)</label>
                                <input
                                    type="text"
                                    value={formData.options}
                                    onChange={(e) => setFormData({ ...formData, options: e.target.value })}
                                    placeholder="лента, плита, сваи"
                                    className="w-full px-3 py-2 border rounded-lg"
                                    required={formData.field_type === 'select'}
                                />
                            </div>
                        )}
                    </div>

                    <div>
                        <label className="block text-sm font-medium mb-1">Описание (опционально)</label>
                        <textarea
                            value={formData.description}
                            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                            placeholder="Дополнительная информация о поле..."
                            className="w-full px-3 py-2 border rounded-lg"
                            rows={2}
                        />
                    </div>

                    <div className="flex gap-2 justify-end">
                        <button
                            type="button"
                            onClick={resetForm}
                            className="px-4 py-2 border rounded-lg hover:bg-muted transition-colors"
                        >
                            <X className="h-4 w-4 inline mr-1" />
                            Отмена
                        </button>
                        <button
                            type="submit"
                            className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
                        >
                            <Save className="h-4 w-4 inline mr-1" />
                            Сохранить
                        </button>
                    </div>
                </form>
            )}

            {/* Fields List */}
            <div className="space-y-2">
                {fields.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground border rounded-lg bg-muted/20">
                        Нет кастомных полей. Добавьте первое поле!
                    </div>
                ) : (
                    fields.map((field) => (
                        <div
                            key={field.id}
                            className={`border rounded-lg p-4 flex items-center justify-between ${!field.is_active ? 'opacity-50 bg-muted/20' : 'bg-card'
                                }`}
                        >
                            <div className="flex items-center gap-4 flex-1">
                                <GripVertical className="h-5 w-5 text-muted-foreground cursor-move" />

                                <div className="flex-1">
                                    <div className="flex items-center gap-2">
                                        <span className="font-mono text-sm bg-muted px-2 py-1 rounded">
                                            {field.field_name}
                                        </span>
                                        <span className="font-medium">{field.field_label}</span>
                                        <span className="text-xs text-muted-foreground px-2 py-1 bg-muted rounded">
                                            {field.field_type}
                                        </span>
                                    </div>
                                    {field.options && (
                                        <div className="text-sm text-muted-foreground mt-1">
                                            Варианты: {field.options.join(', ')}
                                        </div>
                                    )}
                                    {field.description && (
                                        <div className="text-sm text-muted-foreground mt-1">
                                            {field.description}
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => handleToggleActive(field)}
                                    className={`px-3 py-1 rounded text-sm ${field.is_active
                                        ? 'bg-green-100 text-green-700'
                                        : 'bg-gray-100 text-gray-700'
                                        }`}
                                >
                                    {field.is_active ? 'Активно' : 'Неактивно'}
                                </button>

                                <button
                                    onClick={() => handleDelete(field.id)}
                                    className="p-2 hover:bg-red-50 text-red-600 rounded transition-colors"
                                >
                                    <Trash2 className="h-4 w-4" />
                                </button>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    )
}
