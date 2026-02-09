import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Edit2, Save, X, GripVertical } from 'lucide-react';
export default function CustomFieldsManager({ onFieldsChange }) {
    const [fields, setFields] = useState([]);
    const [isAdding, setIsAdding] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [loading, setLoading] = useState(true);
    // Form state
    const [formData, setFormData] = useState({
        field_name: '',
        field_label: '',
        field_type: 'text',
        options: '',
        description: ''
    });
    useEffect(() => {
        fetchFields();
    }, []);
    const fetchFields = async () => {
        try {
            const token = localStorage.getItem('access_token');
            const response = await fetch('/api/custom-fields?active_only=false', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setFields(data);
            }
        }
        catch (error) {
            console.error('Failed to fetch custom fields:', error);
        }
        finally {
            setLoading(false);
        }
    };
    const handleSubmit = async (e) => {
        e.preventDefault();
        const token = localStorage.getItem('access_token');
        const payload = {
            field_name: formData.field_name,
            field_label: formData.field_label,
            field_type: formData.field_type,
            options: formData.field_type === 'select' ? formData.options.split(',').map(o => o.trim()) : null,
            description: formData.description || null
        };
        try {
            const response = await fetch('/api/custom-fields', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                await fetchFields();
                resetForm();
                onFieldsChange?.();
            }
            else {
                const error = await response.json();
                alert(error.detail || 'Failed to create field');
            }
        }
        catch (error) {
            console.error('Failed to create field:', error);
            alert('Failed to create field');
        }
    };
    const handleDelete = async (id) => {
        if (!confirm('Удалить это поле? Данные в лидах сохранятся, но поле исчезнет из интерфейса.')) {
            return;
        }
        const token = localStorage.getItem('access_token');
        try {
            const response = await fetch(`/api/custom-fields/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                await fetchFields();
                onFieldsChange?.();
            }
        }
        catch (error) {
            console.error('Failed to delete field:', error);
        }
    };
    const handleToggleActive = async (field) => {
        const token = localStorage.getItem('access_token');
        try {
            const response = await fetch(`/api/custom-fields/${field.id}`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ is_active: !field.is_active })
            });
            if (response.ok) {
                await fetchFields();
                onFieldsChange?.();
            }
        }
        catch (error) {
            console.error('Failed to toggle field:', error);
        }
    };
    const resetForm = () => {
        setFormData({
            field_name: '',
            field_label: '',
            field_type: 'text',
            options: '',
            description: ''
        });
        setIsAdding(false);
        setEditingId(null);
    };
    const toSnakeCase = (str) => {
        return str
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '_')
            .replace(/^_+|_+$/g, '');
    };
    if (loading) {
        return _jsx("div", { className: "text-center py-8 text-muted-foreground", children: "\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430..." });
    }
    return (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsxs("div", { children: [_jsx("h3", { className: "text-lg font-semibold", children: "\u041A\u0430\u0441\u0442\u043E\u043C\u043D\u044B\u0435 \u043F\u043E\u043B\u044F" }), _jsx("p", { className: "text-sm text-muted-foreground", children: "\u0414\u043E\u0431\u0430\u0432\u044C\u0442\u0435 \u0441\u0432\u043E\u0438 \u043F\u043E\u043B\u044F \u0434\u043B\u044F \u043A\u0432\u0430\u043B\u0438\u0444\u0438\u043A\u0430\u0446\u0438\u0438 \u043B\u0438\u0434\u043E\u0432. AI \u0431\u0443\u0434\u0435\u0442 \u0430\u0432\u0442\u043E\u043C\u0430\u0442\u0438\u0447\u0435\u0441\u043A\u0438 \u0438\u0437\u0432\u043B\u0435\u043A\u0430\u0442\u044C \u044D\u0442\u0438 \u0434\u0430\u043D\u043D\u044B\u0435." })] }), !isAdding && (_jsxs("button", { onClick: () => setIsAdding(true), className: "flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors", children: [_jsx(Plus, { className: "h-4 w-4" }), "\u0414\u043E\u0431\u0430\u0432\u0438\u0442\u044C \u043F\u043E\u043B\u0435"] }))] }), isAdding && (_jsxs("form", { onSubmit: handleSubmit, className: "border rounded-lg p-4 bg-card space-y-4", children: [_jsxs("div", { className: "grid grid-cols-2 gap-4", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-sm font-medium mb-1", children: "\u041D\u0430\u0437\u0432\u0430\u043D\u0438\u0435 \u043F\u043E\u043B\u044F (\u0430\u043D\u0433\u043B.)" }), _jsx("input", { type: "text", value: formData.field_name, onChange: (e) => setFormData({ ...formData, field_name: toSnakeCase(e.target.value) }), placeholder: "foundation_type", className: "w-full px-3 py-2 border rounded-lg", required: true }), _jsx("p", { className: "text-xs text-muted-foreground mt-1", children: "\u0422\u043E\u043B\u044C\u043A\u043E \u043B\u0430\u0442\u0438\u043D\u0438\u0446\u0430, \u0446\u0438\u0444\u0440\u044B \u0438 _" })] }), _jsxs("div", { children: [_jsx("label", { className: "block text-sm font-medium mb-1", children: "\u041E\u0442\u043E\u0431\u0440\u0430\u0436\u0430\u0435\u043C\u043E\u0435 \u043D\u0430\u0437\u0432\u0430\u043D\u0438\u0435" }), _jsx("input", { type: "text", value: formData.field_label, onChange: (e) => setFormData({ ...formData, field_label: e.target.value }), placeholder: "\u0422\u0438\u043F \u0444\u0443\u043D\u0434\u0430\u043C\u0435\u043D\u0442\u0430", className: "w-full px-3 py-2 border rounded-lg", required: true })] })] }), _jsxs("div", { className: "grid grid-cols-2 gap-4", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-sm font-medium mb-1", children: "\u0422\u0438\u043F \u043F\u043E\u043B\u044F" }), _jsxs("select", { value: formData.field_type, onChange: (e) => setFormData({ ...formData, field_type: e.target.value }), className: "w-full px-3 py-2 border rounded-lg", children: [_jsx("option", { value: "text", children: "\u0422\u0435\u043A\u0441\u0442" }), _jsx("option", { value: "number", children: "\u0427\u0438\u0441\u043B\u043E" }), _jsx("option", { value: "select", children: "\u0412\u044B\u0431\u043E\u0440 \u0438\u0437 \u0441\u043F\u0438\u0441\u043A\u0430" }), _jsx("option", { value: "boolean", children: "\u0414\u0430/\u041D\u0435\u0442" })] })] }), formData.field_type === 'select' && (_jsxs("div", { children: [_jsx("label", { className: "block text-sm font-medium mb-1", children: "\u0412\u0430\u0440\u0438\u0430\u043D\u0442\u044B (\u0447\u0435\u0440\u0435\u0437 \u0437\u0430\u043F\u044F\u0442\u0443\u044E)" }), _jsx("input", { type: "text", value: formData.options, onChange: (e) => setFormData({ ...formData, options: e.target.value }), placeholder: "\u043B\u0435\u043D\u0442\u0430, \u043F\u043B\u0438\u0442\u0430, \u0441\u0432\u0430\u0438", className: "w-full px-3 py-2 border rounded-lg", required: formData.field_type === 'select' })] }))] }), _jsxs("div", { children: [_jsx("label", { className: "block text-sm font-medium mb-1", children: "\u041E\u043F\u0438\u0441\u0430\u043D\u0438\u0435 (\u043E\u043F\u0446\u0438\u043E\u043D\u0430\u043B\u044C\u043D\u043E)" }), _jsx("textarea", { value: formData.description, onChange: (e) => setFormData({ ...formData, description: e.target.value }), placeholder: "\u0414\u043E\u043F\u043E\u043B\u043D\u0438\u0442\u0435\u043B\u044C\u043D\u0430\u044F \u0438\u043D\u0444\u043E\u0440\u043C\u0430\u0446\u0438\u044F \u043E \u043F\u043E\u043B\u0435...", className: "w-full px-3 py-2 border rounded-lg", rows: 2 })] }), _jsxs("div", { className: "flex gap-2 justify-end", children: [_jsxs("button", { type: "button", onClick: resetForm, className: "px-4 py-2 border rounded-lg hover:bg-muted transition-colors", children: [_jsx(X, { className: "h-4 w-4 inline mr-1" }), "\u041E\u0442\u043C\u0435\u043D\u0430"] }), _jsxs("button", { type: "submit", className: "px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors", children: [_jsx(Save, { className: "h-4 w-4 inline mr-1" }), "\u0421\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C"] })] })] })), _jsx("div", { className: "space-y-2", children: fields.length === 0 ? (_jsx("div", { className: "text-center py-8 text-muted-foreground border rounded-lg bg-muted/20", children: "\u041D\u0435\u0442 \u043A\u0430\u0441\u0442\u043E\u043C\u043D\u044B\u0445 \u043F\u043E\u043B\u0435\u0439. \u0414\u043E\u0431\u0430\u0432\u044C\u0442\u0435 \u043F\u0435\u0440\u0432\u043E\u0435 \u043F\u043E\u043B\u0435!" })) : (fields.map((field) => (_jsxs("div", { className: `border rounded-lg p-4 flex items-center justify-between ${!field.is_active ? 'opacity-50 bg-muted/20' : 'bg-card'}`, children: [_jsxs("div", { className: "flex items-center gap-4 flex-1", children: [_jsx(GripVertical, { className: "h-5 w-5 text-muted-foreground cursor-move" }), _jsxs("div", { className: "flex-1", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("span", { className: "font-mono text-sm bg-muted px-2 py-1 rounded", children: field.field_name }), _jsx("span", { className: "font-medium", children: field.field_label }), _jsx("span", { className: "text-xs text-muted-foreground px-2 py-1 bg-muted rounded", children: field.field_type })] }), field.options && (_jsxs("div", { className: "text-sm text-muted-foreground mt-1", children: ["\u0412\u0430\u0440\u0438\u0430\u043D\u0442\u044B: ", field.options.join(', ')] })), field.description && (_jsx("div", { className: "text-sm text-muted-foreground mt-1", children: field.description }))] })] }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx("button", { onClick: () => handleToggleActive(field), className: `px-3 py-1 rounded text-sm ${field.is_active
                                        ? 'bg-green-100 text-green-700'
                                        : 'bg-gray-100 text-gray-700'}`, children: field.is_active ? 'Активно' : 'Неактивно' }), _jsx("button", { onClick: () => handleDelete(field.id), className: "p-2 hover:bg-red-50 text-red-600 rounded transition-colors", children: _jsx(Trash2, { className: "h-4 w-4" }) })] })] }, field.id)))) })] }));
}
