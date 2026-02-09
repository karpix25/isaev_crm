import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import React, { useState, useEffect, useRef } from 'react';
import { useLeads, useUpdateLead } from '@/hooks/useLeads';
import { useChatHistory, useSendMessage } from '@/hooks/useChat';
import { useCustomFields } from '@/hooks/useCustomFields';
import { useConvertLeadToProject } from '@/hooks/useProjects';
import { LeadStatus, MessageDirection } from '@/types';
import { formatTimeAgo } from '@/lib/utils';
import { X, Phone, MapPin, Ruler, Home, Wallet, MessageSquare, Clock, ShieldCheck, Settings2, Search, Send, Calendar, ClipboardList } from 'lucide-react';
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
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
];
export function Leads() {
    const [search, setSearch] = useState('');
    const [source, setSource] = useState('');
    const [visibleStages, setVisibleStages] = useState(columns.map(c => c.id));
    const { data } = useLeads({ search: search || undefined, source: source || undefined });
    const { data: customFields } = useCustomFields(true);
    const updateLead = useUpdateLead();
    const convertLead = useConvertLeadToProject();
    const [draggedLead, setDraggedLead] = useState(null);
    const [selectedLead, setSelectedLead] = useState(null);
    const [showStageFilters, setShowStageFilters] = useState(false);
    const [notification, setNotification] = useState(null);
    const leads = data?.leads || [];
    const getLeadsByStatus = (status) => {
        return leads.filter((lead) => lead.status === status);
    };
    const toggleStage = (stage) => {
        setVisibleStages(prev => prev.includes(stage)
            ? prev.filter(s => s !== stage)
            : [...prev, stage]);
    };
    const handleDragStart = (lead) => {
        setDraggedLead(lead);
    };
    const handleDragOver = (e) => {
        e.preventDefault();
    };
    const handleDrop = (status) => {
        if (draggedLead && draggedLead.status !== status) {
            updateLead.mutate({
                id: draggedLead.id,
                data: { status },
            });
            // Auto convert to project if moved to CONTRACT or WON
            if (status === LeadStatus.CONTRACT || status === LeadStatus.WON) {
                convertLead.mutate({ leadId: draggedLead.id }, {
                    onSuccess: () => {
                        setNotification({ message: 'Объект успешно создан и связан!', type: 'success' });
                        setTimeout(() => setNotification(null), 5000);
                    },
                    onError: (err) => {
                        setNotification({ message: 'Ошибка при создании объекта: ' + (err.response?.data?.detail || err.message), type: 'error' });
                        setTimeout(() => setNotification(null), 5000);
                    }
                });
            }
        }
        setDraggedLead(null);
    };
    const filteredColumns = columns.filter(col => visibleStages.includes(col.id));
    return (_jsxs("div", { className: "h-full relative flex flex-col gap-6", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("h2", { className: "text-2xl font-bold", children: "\u0423\u043F\u0440\u0430\u0432\u043B\u0435\u043D\u0438\u0435 \u043B\u0438\u0434\u0430\u043C\u0438" }), _jsxs("div", { className: "flex items-center gap-4", children: [_jsxs("div", { className: "relative", children: [_jsxs("button", { onClick: () => setShowStageFilters(!showStageFilters), className: `flex h-10 items-center gap-2 rounded-lg border px-4 text-sm transition-colors hover:bg-accent ${showStageFilters ? 'bg-accent border-primary' : 'bg-background'}`, children: [_jsx(Settings2, { className: "h-4 w-4" }), "\u0421\u0442\u0430\u0434\u0438\u0438 \u0432\u043E\u0440\u043E\u043D\u043A\u0438", _jsx("span", { className: "ml-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-bold text-primary", children: visibleStages.length })] }), showStageFilters && (_jsxs(_Fragment, { children: [_jsx("div", { className: "fixed inset-0 z-10", onClick: () => setShowStageFilters(false) }), _jsxs("div", { className: "absolute right-0 top-12 z-20 w-64 rounded-xl border bg-card p-4 shadow-2xl animate-in fade-in zoom-in-95 duration-200", children: [_jsx("h4", { className: "mb-3 text-xs font-bold uppercase tracking-wider text-muted-foreground text-[10px]", children: "\u0412\u0438\u0434\u0438\u043C\u044B\u0435 \u0441\u0442\u0430\u0434\u0438\u0438" }), _jsx("div", { className: "grid gap-1.5", children: columns.map((col) => (_jsxs("label", { className: "flex cursor-pointer items-center justify-between rounded-md p-2 transition-colors hover:bg-accent", children: [_jsxs("div", { className: "flex items-center gap-2.5", children: [_jsx("div", { className: `h-2 w-2 rounded-full ${col.color}` }), _jsx("span", { className: "text-[13px] font-medium", children: col.title })] }), _jsx("input", { type: "checkbox", checked: visibleStages.includes(col.id), onChange: () => toggleStage(col.id), className: "h-3.5 w-3.5 rounded border-slate-300 text-primary focus:ring-primary" })] }, col.id))) }), _jsxs("div", { className: "mt-4 border-t pt-3 flex gap-2", children: [_jsx("button", { onClick: () => setVisibleStages(columns.map(c => c.id)), className: "flex-1 text-[10px] font-bold uppercase text-primary hover:underline", children: "\u0412\u0441\u0435" }), _jsx("button", { onClick: () => setVisibleStages([]), className: "flex-1 text-[10px] font-bold uppercase text-muted-foreground hover:underline", children: "\u0421\u043A\u0440\u044B\u0442\u044C" })] })] })] }))] }), _jsxs("div", { className: "relative", children: [_jsx(Search, { className: "absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" }), _jsx("input", { type: "text", placeholder: "\u041F\u043E\u0438\u0441\u043A...", value: search, onChange: (e) => setSearch(e.target.value), className: "h-10 w-48 rounded-lg border bg-background pl-10 pr-4 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary" })] }), _jsxs("select", { value: source, onChange: (e) => setSource(e.target.value), className: "h-10 rounded-lg border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary", children: [_jsx("option", { value: "", children: "\u0418\u0441\u0442\u043E\u0447\u043D\u0438\u043A\u0438" }), _jsx("option", { value: "telegram", children: "Telegram" }), _jsx("option", { value: "avito", children: "Avito" }), _jsx("option", { value: "website", children: "\u0421\u0430\u0439\u0442" })] })] })] }), notification && (_jsxs("div", { className: `fixed bottom-8 left-1/2 -translate-x-1/2 z-[100] px-6 py-3 rounded-xl shadow-2xl animate-in slide-in-from-bottom-4 duration-300 flex items-center gap-3 border ${notification.type === 'success' ? 'bg-emerald-500 border-emerald-400 text-white' : 'bg-red-500 border-red-400 text-white'}`, children: [_jsx(ShieldCheck, { className: "h-5 w-5" }), _jsx("span", { className: "font-bold text-sm tracking-wide", children: notification.message }), _jsx("button", { onClick: () => setNotification(null), className: "ml-2 hover:opacity-70", children: _jsx(X, { className: "h-4 w-4" }) })] })), _jsx("div", { className: "flex h-[calc(100vh-12rem)] gap-4 overflow-x-auto pb-4 custom-scrollbar", children: filteredColumns.map((column) => {
                    const columnLeads = getLeadsByStatus(column.id);
                    return (_jsxs("div", { className: "flex flex-col rounded-lg border bg-card min-width-[320px] w-[320px] shrink-0", onDragOver: handleDragOver, onDrop: () => handleDrop(column.id), children: [_jsxs("div", { className: "flex items-center justify-between border-b p-4", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("div", { className: `h-2 w-2 rounded-full ${column.color}` }), _jsx("h3", { className: "font-semibold", children: column.title })] }), _jsx("span", { className: "rounded-full bg-muted px-2 py-0.5 text-xs font-medium", children: columnLeads.length })] }), _jsx("div", { className: "flex-1 space-y-2 overflow-y-auto p-4", children: columnLeads.map((lead) => (_jsx(LeadCard, { lead: lead, onDragStart: () => handleDragStart(lead), onClick: () => setSelectedLead(lead) }, lead.id))) })] }, column.id));
                }) }), selectedLead && (_jsx(LeadWorkspace, { lead: selectedLead, customFields: customFields || [], onClose: () => setSelectedLead(null), onUpdateStatus: (status) => {
                    updateLead.mutate({ id: selectedLead.id, data: { status } });
                    setSelectedLead(prev => prev ? { ...prev, status } : null);
                    // Auto convert if status changed to CONTRACT or WON
                    if (status === LeadStatus.CONTRACT || status === LeadStatus.WON) {
                        convertLead.mutate({ leadId: selectedLead.id }, {
                            onSuccess: () => {
                                setNotification({ message: 'Объект успешно создан и связан!', type: 'success' });
                                setTimeout(() => setNotification(null), 5000);
                            },
                            onError: (err) => {
                                setNotification({ message: 'Ошибка при создании объекта: ' + (err.response?.data?.detail || err.message), type: 'error' });
                                setTimeout(() => setNotification(null), 5000);
                            }
                        });
                    }
                } }))] }));
}
function LeadWorkspace({ lead, customFields, onClose, onUpdateStatus }) {
    const [message, setMessage] = useState('');
    const messagesEndRef = useRef(null);
    const { data: chatData } = useChatHistory(lead.id, 1);
    const sendMessage = useSendMessage();
    const messages = chatData?.messages || [];
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };
    useEffect(() => {
        scrollToBottom();
    }, [messages]);
    const handleSendMessage = () => {
        if (!message.trim())
            return;
        sendMessage.mutate({ leadId: lead.id, content: message }, { onSuccess: () => setMessage('') });
    };
    const getMessageLabel = (msg) => {
        if (msg.direction === MessageDirection.INBOUND)
            return 'Клиент';
        if (msg.sender_name === 'AI' || msg.sender_name === 'Bot')
            return 'ИИ Ассистент';
        return 'Вы';
    };
    const extractedData = typeof lead.extracted_data === 'string'
        ? JSON.parse(lead.extracted_data)
        : lead.extracted_data || {};
    return (_jsx("div", { className: "fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200", children: _jsxs("div", { className: "relative w-full max-w-[1240px] h-[90vh] overflow-hidden rounded-2xl bg-background shadow-2xl flex flex-col scale-in-center", children: [_jsxs("div", { className: "flex items-center justify-between border-b px-6 py-4 bg-card", children: [_jsxs("div", { className: "flex items-center gap-4", children: [lead.avatar_url ? (_jsx("img", { src: `${API_URL}${lead.avatar_url}`, alt: lead.full_name || 'U', className: "h-10 w-10 rounded-full object-cover ring-2 ring-primary/20" })) : (_jsx("div", { className: "flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground font-bold", children: lead.full_name?.[0] || 'U' })), _jsxs("div", { children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("h2", { className: "text-lg font-bold leading-tight", children: lead.full_name || lead.username || 'Неизвестно' }), _jsx("span", { className: `rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${lead.ai_qualification_status === 'handoff_required' ? 'bg-orange-100 text-orange-700' : 'bg-emerald-100 text-emerald-700'}`, children: lead.ai_qualification_status === 'handoff_required' ? 'Готов к работе' : 'ИИ: Квалификация' })] }), _jsxs("div", { className: "flex items-center gap-3 text-xs text-muted-foreground", children: [_jsxs("span", { className: "flex items-center gap-1", children: [_jsx(Phone, { className: "h-3 w-3" }), " ", lead.phone || '—'] }), lead.username && _jsxs("span", { children: ["\u2022 @", lead.username] }), lead.source && _jsxs("span", { className: "flex items-center gap-1", children: ["\u2022 ", _jsx(MessageSquare, { className: "h-3 w-3" }), " ", lead.source] })] })] })] }), _jsxs("div", { className: "flex items-center gap-3", children: [_jsxs("button", { className: "flex h-10 items-center gap-2 rounded-lg border bg-background px-4 text-sm font-medium transition-colors hover:bg-accent ring-1 ring-slate-200", children: [_jsx(Calendar, { className: "h-4 w-4" }), "\u0417\u0430\u043C\u0435\u0440"] }), lead.converted_to_project_id ? (_jsxs("a", { href: `/projects?id=${lead.converted_to_project_id}`, className: "flex h-10 items-center gap-2 rounded-lg bg-emerald-600 px-4 text-sm font-medium text-white transition-all hover:bg-emerald-700 shadow-sm", children: [_jsx(Home, { className: "h-4 w-4" }), "\u041F\u0435\u0440\u0435\u0439\u0442\u0438 \u043A \u043E\u0431\u044A\u0435\u043A\u0442\u0443"] })) : (_jsxs("button", { onClick: () => {
                                        if (window.confirm('Преобразовать лид в активный проект?')) {
                                            onUpdateStatus(LeadStatus.CONTRACT);
                                        }
                                    }, className: "flex h-10 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-all hover:opacity-90 shadow-sm", children: [_jsx(ShieldCheck, { className: "h-4 w-4" }), "\u041D\u0430\u0447\u0430\u0442\u044C \u043F\u0440\u043E\u0435\u043A\u0442"] })), _jsx("div", { className: "mx-2 h-6 w-px bg-border" }), _jsx("button", { onClick: onClose, className: "rounded-full p-2 hover:bg-muted transition-colors", children: _jsx(X, { className: "h-5 w-5" }) })] })] }), _jsxs("div", { className: "flex-1 flex overflow-hidden", children: [_jsx("div", { className: "w-[40%] border-r bg-slate-50/50 flex flex-col overflow-y-auto custom-scrollbar", children: _jsxs("div", { className: "p-6 space-y-8", children: [_jsxs("section", { children: [_jsxs("h3", { className: "mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground", children: [_jsx(ShieldCheck, { className: "h-3.5 w-3.5" }), " \u0422\u0435\u043A\u0443\u0449\u0430\u044F \u0441\u0442\u0430\u0434\u0438\u044F"] }), _jsx("div", { className: "grid grid-cols-2 gap-2", children: Object.values(LeadStatus).map((status) => (_jsxs("button", { onClick: () => onUpdateStatus(status), className: `flex items-center gap-2 px-3 py-2.5 text-xs font-semibold rounded-xl border transition-all ${lead.status === status
                                                        ? 'bg-primary text-primary-foreground border-primary shadow-md'
                                                        : 'bg-white hover:bg-slate-50 border-slate-200 text-slate-600'}`, children: [_jsx("div", { className: `h-1.5 w-1.5 rounded-full ${lead.status === status ? 'bg-white' : 'bg-slate-300'}` }), status] }, status))) })] }), _jsxs("section", { className: "rounded-2xl border bg-white p-5 shadow-sm", children: [_jsxs("h3", { className: "mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground border-b pb-3", children: [_jsx(ClipboardList, { className: "h-3.5 w-3.5" }), " \u0418\u0437\u0432\u043B\u0435\u0447\u0435\u043D\u043D\u044B\u0435 \u0434\u0430\u043D\u043D\u044B\u0435"] }), _jsxs("div", { className: "grid grid-cols-2 gap-y-5 gap-x-4", children: [_jsx(DataField, { label: "\u041E\u0431\u044A\u0435\u043A\u0442", value: extractedData.property_type, icon: _jsx(Home, { className: "h-3 w-3" }) }), _jsx(DataField, { label: "\u041F\u043B\u043E\u0449\u0430\u0434\u044C", value: extractedData.area_sqm ? `${extractedData.area_sqm} м²` : null, icon: _jsx(Ruler, { className: "h-3 w-3" }) }), _jsx(DataField, { label: "\u0416\u041A / \u0410\u0434\u0440\u0435\u0441", value: extractedData.address, icon: _jsx(MapPin, { className: "h-3 w-3" }) }), _jsx(DataField, { label: "\u0422\u0438\u043F \u0440\u0435\u043C\u043E\u043D\u0442\u0430", value: extractedData.renovation_type }), _jsx(DataField, { label: "\u0411\u044E\u0434\u0436\u0435\u0442", value: extractedData.budget, icon: _jsx(Wallet, { className: "h-3 w-3" }) }), _jsx(DataField, { label: "\u0421\u0440\u043E\u043A\u0438", value: extractedData.deadline, icon: _jsx(Clock, { className: "h-3 w-3" }) }), customFields.map((field) => {
                                                        const value = extractedData[field.field_name];
                                                        return (_jsx(DataField, { label: field.field_label, value: value ? String(value) : null }, field.id));
                                                    })] }), lead.ai_summary && (_jsxs("div", { className: "mt-6 pt-5 border-t", children: [_jsx("div", { className: "mb-2 text-xs font-bold uppercase tracking-widest text-muted-foreground", children: "\u0421\u0430\u043C\u043C\u0430\u0440\u0438 \u0418\u0418" }), _jsxs("p", { className: "text-sm leading-relaxed text-slate-600 italic", children: ["\"", lead.ai_summary, "\""] })] }))] })] }) }), _jsxs("div", { className: "flex-1 flex flex-col bg-background relative", children: [_jsxs("div", { className: "flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar bg-slate-50/30", children: [messages.length === 0 ? (_jsxs("div", { className: "flex h-full items-center justify-center text-muted-foreground flex-col gap-2", children: [_jsx(MessageSquare, { className: "h-8 w-8 opacity-20" }), _jsx("p", { className: "text-sm", children: "\u0418\u0441\u0442\u043E\u0440\u0438\u044F \u0434\u0438\u0430\u043B\u043E\u0433\u0430 \u043F\u0443\u0441\u0442\u0430" })] })) : ([...messages].reverse().map((msg) => (_jsxs("div", { className: `flex flex-col ${msg.direction === MessageDirection.OUTBOUND ? 'items-end' : 'items-start'}`, children: [_jsx("div", { className: `max-w-[85%] rounded-2xl px-4 py-2.5 shadow-sm text-[13px] ${msg.direction === MessageDirection.OUTBOUND
                                                        ? 'bg-primary text-primary-foreground rounded-br-none'
                                                        : 'bg-white border text-slate-900 rounded-bl-none'}`, children: _jsx("p", { className: "leading-relaxed whitespace-pre-wrap", children: msg.content }) }), _jsxs("span", { className: "mt-1 px-1 text-[9px] font-bold text-muted-foreground uppercase tracking-widest opacity-60", children: [getMessageLabel(msg), " \u2022 ", new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })] })] }, msg.id)))), _jsx("div", { ref: messagesEndRef })] }), _jsx("div", { className: "border-t p-4 bg-card", children: _jsxs("div", { className: "flex gap-2 bg-background rounded-xl border p-1 focus-within:ring-2 focus-within:ring-primary/20 transition-all shadow-inner", children: [_jsx("input", { type: "text", value: message, onChange: (e) => setMessage(e.target.value), onKeyPress: (e) => e.key === 'Enter' && handleSendMessage(), placeholder: "\u041D\u0430\u043F\u0438\u0448\u0438\u0442\u0435 \u043E\u0442\u0432\u0435\u0442 \u043A\u043B\u0438\u0435\u043D\u0442\u0443...", className: "flex-1 bg-transparent px-4 py-2.5 text-sm focus:outline-none" }), _jsx("button", { onClick: handleSendMessage, disabled: !message.trim() || sendMessage.isPending, className: "rounded-lg bg-primary p-2.5 text-primary-foreground hover:opacity-90 disabled:opacity-50 transition-all shadow-sm active:scale-95 flex items-center justify-center", children: _jsx(Send, { className: "h-4 w-4" }) })] }) })] })] })] }) }));
}
function LeadCard({ lead, onDragStart, onClick }) {
    return (_jsxs("div", { draggable: true, onDragStart: onDragStart, onClick: onClick, className: "group cursor-pointer rounded-lg border bg-background p-3 shadow-sm transition-all hover:border-primary hover:shadow-md", children: [_jsxs("div", { className: "mb-2 flex items-start justify-between", children: [_jsxs("div", { className: "flex items-center gap-2", children: [lead.avatar_url ? (_jsx("img", { src: `${API_URL}${lead.avatar_url}`, alt: lead.full_name || 'U', className: "h-8 w-8 rounded-full object-cover group-hover:scale-110 transition-transform" })) : (_jsx("div", { className: "flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground group-hover:scale-110 transition-transform", children: lead.full_name?.[0] || lead.username?.[0] || 'U' })), _jsxs("div", { children: [_jsx("div", { className: "font-medium group-hover:text-primary transition-colors text-[13px]", children: lead.full_name || lead.username || 'Неизвестно' }), lead.username && (_jsxs("div", { className: "text-[10px] text-muted-foreground", children: ["@", lead.username] }))] })] }), lead.unread_count > 0 && (_jsx("div", { className: "flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground animate-pulse", children: lead.unread_count }))] }), lead.ai_summary && (_jsx("p", { className: "mb-3 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground italic", children: lead.ai_summary })), _jsxs("div", { className: "flex items-center justify-between border-t pt-2", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsxs("div", { className: "flex items-center gap-1 text-[10px] text-muted-foreground uppercase tracking-wider font-semibold", children: [_jsx(MessageSquare, { className: "h-3 w-3" }), lead.source || 'TG'] }), lead.phone && (_jsxs("div", { className: "flex items-center gap-1 text-[10px] text-muted-foreground uppercase tracking-wider font-semibold", children: [_jsx(Phone, { className: "h-3 w-3" }), "OK"] }))] }), lead.last_message_at && (_jsxs("div", { className: "flex items-center gap-1 text-[10px] text-muted-foreground", children: [_jsx(Clock, { className: "h-2.5 w-2.5" }), formatTimeAgo(lead.last_message_at)] }))] })] }));
}
function DataField({ label, value, icon }) {
    return (_jsxs("div", { className: "space-y-1", children: [_jsxs("div", { className: "flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-muted-foreground opacity-80", children: [icon, " ", label] }), _jsx("div", { className: "text-xs font-medium text-slate-800", children: value || _jsx("span", { className: "text-slate-300 font-normal", children: "\u041D\u0435\u0442 \u0434\u0430\u043D\u043D\u044B\u0445" }) })] }));
}
