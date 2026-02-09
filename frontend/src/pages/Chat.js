import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useLeads } from '@/hooks/useLeads';
import { useChatHistory, useSendMessage } from '@/hooks/useChat';
import { useCustomFields } from '@/hooks/useCustomFields';
import { MessageDirection } from '@/types';
import { formatTimeAgo } from '@/lib/utils';
import { Send, Phone, Settings2, CheckCircle2, Sparkles, Info, X } from 'lucide-react';
export function Chat() {
    const { leadId } = useParams();
    const { data } = useLeads();
    const { data: customFields } = useCustomFields(true);
    const [selectedLead, setSelectedLead] = useState(null);
    const [message, setMessage] = useState('');
    const [activeTrace, setActiveTrace] = useState(null);
    const messagesEndRef = useRef(null);
    const { data: chatData } = useChatHistory(selectedLead?.id || '', 1);
    const sendMessage = useSendMessage();
    const leads = data?.leads || [];
    const messages = chatData?.messages || [];
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };
    useEffect(() => {
        scrollToBottom();
    }, [messages]);
    // Select lead from URL
    useEffect(() => {
        if (leadId && leads.length > 0) {
            const lead = leads.find(l => l.id === leadId);
            if (lead) {
                setSelectedLead(lead);
            }
        }
    }, [leadId, leads]);
    const handleSendMessage = () => {
        if (!selectedLead || !message.trim())
            return;
        sendMessage.mutate({ leadId: selectedLead.id, content: message }, {
            onSuccess: () => setMessage(''),
        });
    };
    const getMessageLabel = (msg) => {
        if (msg.direction === MessageDirection.INBOUND)
            return 'Клиент';
        if (msg.sender_name === 'AI' || msg.sender_name === 'Bot')
            return 'ИИ Ассистент';
        return 'Вы';
    };
    return (_jsxs("div", { className: "grid h-full grid-cols-12 gap-4 overflow-hidden", children: [_jsxs("div", { className: "col-span-3 flex flex-col rounded-lg border bg-card overflow-hidden", children: [_jsx("div", { className: "border-b p-4", children: _jsx("h3", { className: "font-semibold", children: "\u0414\u0438\u0430\u043B\u043E\u0433\u0438" }) }), _jsx("div", { className: "flex-1 overflow-y-auto", children: leads.map((lead) => (_jsx("button", { onClick: () => setSelectedLead(lead), className: `w-full border-b p-4 text-left transition-colors hover:bg-accent ${selectedLead?.id === lead.id ? 'bg-accent' : ''}`, children: _jsxs("div", { className: "flex items-start gap-3", children: [_jsx("div", { className: "flex h-10 w-10 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground", children: lead.full_name?.[0] || 'U' }), _jsxs("div", { className: "flex-1 overflow-hidden", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("div", { className: "font-medium", children: lead.full_name || lead.username || 'Неизвестно' }), lead.last_message_at && (_jsx("span", { className: "text-xs text-muted-foreground", children: formatTimeAgo(lead.last_message_at) }))] }), lead.ai_summary && (_jsx("p", { className: "truncate text-sm text-muted-foreground", children: lead.ai_summary })), lead.unread_count > 0 && (_jsxs("div", { className: "mt-1 flex items-center gap-1 text-xs font-medium text-primary", children: [_jsx("div", { className: "h-2 w-2 rounded-full bg-primary" }), lead.unread_count] }))] })] }) }, lead.id))) })] }), _jsx("div", { className: "col-span-6 flex flex-col rounded-lg border bg-card overflow-hidden", children: selectedLead ? (_jsxs(_Fragment, { children: [_jsxs("div", { className: "flex items-center justify-between border-b p-4", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx("div", { className: "flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground", children: selectedLead.full_name?.[0] || 'U' }), _jsxs("div", { children: [_jsx("div", { className: "font-semibold", children: selectedLead.full_name || selectedLead.username }), _jsx("div", { className: "text-sm text-green-500", children: "AI \u041A\u0412\u0410\u041B\u0418\u0424\u0418\u041A\u0410\u0426\u0418\u042F: \u0412 \u041F\u0420\u041E\u0426\u0415\u0421\u0421\u0415" })] })] }), _jsxs("div", { className: "flex gap-2", children: [_jsx("button", { className: "rounded-lg p-2 hover:bg-accent", children: _jsx(Phone, { className: "h-5 w-5" }) }), _jsx("button", { className: "rounded-lg p-2 hover:bg-accent", children: _jsx(Settings2, { className: "h-5 w-5" }) })] })] }), _jsxs("div", { className: "flex-1 space-y-4 overflow-y-auto p-4 flex flex-col", children: [messages.length === 0 ? (_jsx("div", { className: "flex h-full items-center justify-center text-muted-foreground", children: "\u0418\u0441\u0442\u043E\u0440\u0438\u044F \u0434\u0438\u0430\u043B\u043E\u0433\u0430 \u043F\u0443\u0441\u0442\u0430. \u041D\u0430\u0447\u043D\u0438\u0442\u0435 \u043E\u0431\u0449\u0435\u043D\u0438\u0435." })) : ([...messages].reverse().map((msg) => (_jsxs("div", { className: `flex flex-col ${msg.direction === MessageDirection.OUTBOUND ? 'items-end' : 'items-start'}`, children: [_jsxs("div", { className: `max-w-[80%] rounded-2xl px-4 py-2 relative group ${msg.direction === MessageDirection.OUTBOUND
                                                ? 'bg-blue-600 text-white rounded-br-none shadow-sm'
                                                : 'bg-slate-100 text-slate-900 rounded-bl-none border shadow-sm'}`, children: [_jsx("p", { className: "text-[14px] leading-relaxed whitespace-pre-wrap", children: msg.content }), msg.sender_name === 'AI' && msg.ai_metadata && (_jsx("button", { onClick: () => setActiveTrace(msg.ai_metadata), className: "absolute -left-8 top-1/2 -translate-y-1/2 p-1.5 bg-background border rounded-full text-primary opacity-0 group-hover:opacity-100 transition-all shadow-sm hover:scale-110", title: "AI Reasoning Log", children: _jsx(Sparkles, { className: "h-4 w-4" }) }))] }), _jsxs("span", { className: "mt-1 px-1 text-[10px] font-medium text-muted-foreground uppercase opacity-70", children: [getMessageLabel(msg), " \u2022 ", new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })] })] }, msg.id)))), _jsx("div", { ref: messagesEndRef })] }), activeTrace && (_jsx("div", { className: "fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4", children: _jsxs("div", { className: "bg-card w-full max-w-lg rounded-3xl shadow-2xl overflow-hidden border", children: [_jsxs("div", { className: "bg-primary p-6 text-primary-foreground flex justify-between items-center", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx(Sparkles, { className: "h-6 w-6" }), _jsx("h3", { className: "font-black tracking-tight", children: "AI LOG: RETRIEVED CONTEXT" })] }), _jsx("button", { onClick: () => setActiveTrace(null), className: "hover:rotate-90 transition-transform", children: _jsx(X, { className: "h-6 w-6" }) })] }), _jsx("div", { className: "p-6 space-y-4 max-h-[70vh] overflow-y-auto", children: activeTrace.retrieved_context?.length > 0 ? (activeTrace.retrieved_context.map((doc, i) => (_jsxs("div", { className: "bg-muted p-4 rounded-2xl space-y-2 border border-primary/10", children: [_jsxs("div", { className: "flex items-center gap-2 text-xs font-black text-primary uppercase tracking-widest", children: [_jsx(Info, { className: "h-3 w-3" }), doc.title] }), _jsxs("p", { className: "text-sm text-muted-foreground leading-relaxed italic", children: ["\"", doc.content, "\""] })] }, i)))) : (_jsx("div", { className: "text-center py-10 text-muted-foreground", children: "No specific knowledge base context was retrieved for this message." })) })] }) })), _jsx("div", { className: "border-t p-4", children: _jsxs("div", { className: "flex gap-2", children: [_jsx("input", { type: "text", value: message, onChange: (e) => setMessage(e.target.value), onKeyPress: (e) => e.key === 'Enter' && handleSendMessage(), placeholder: "\u041E\u0442\u0432\u0435\u0442\u044C\u0442\u0435 \u043A\u043B\u0438\u0435\u043D\u0442\u0443 \u0438\u043B\u0438 \u0441\u043F\u0440\u043E\u0441\u0438\u0442\u0435 AI...", className: "flex-1 rounded-lg border bg-background px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary" }), _jsx("button", { onClick: handleSendMessage, disabled: !message.trim(), className: "rounded-lg bg-primary px-4 py-2 text-primary-foreground hover:opacity-90 disabled:opacity-50", children: _jsx(Send, { className: "h-5 w-5" }) })] }) })] })) : (_jsx("div", { className: "flex h-full items-center justify-center text-muted-foreground", children: "\u0412\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \u0434\u0438\u0430\u043B\u043E\u0433 \u0434\u043B\u044F \u043D\u0430\u0447\u0430\u043B\u0430" })) }), _jsx("div", { className: "col-span-3 rounded-lg border bg-card p-4", children: selectedLead ? (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx(CheckCircle2, { className: "h-5 w-5 text-primary" }), _jsx("h3", { className: "font-semibold", children: "\u041A\u0432\u0430\u043B\u0438\u0444\u0438\u043A\u0430\u0446\u0438\u044F \u043B\u0438\u0434\u0430" })] }), _jsxs("div", { className: "space-y-3", children: [_jsx(QualificationField, { label: "\u0418\u041C\u042F \u041A\u041B\u0418\u0415\u041D\u0422\u0410", value: selectedLead.full_name }), _jsx(QualificationField, { label: "\u0422\u0415\u041B\u0415\u0424\u041E\u041D", value: selectedLead.phone || 'Не указано' }), _jsx(QualificationField, { label: "TELEGRAM", value: selectedLead.username ? `@${selectedLead.username}` : '', verified: true }), _jsx("div", { className: "border-t pt-3", children: _jsx("div", { className: "text-sm font-medium text-muted-foreground", children: "\u041E\u0411\u042A\u0415\u041A\u0422" }) }), (() => {
                                    const extractedData = typeof selectedLead.extracted_data === 'string'
                                        ? JSON.parse(selectedLead.extracted_data)
                                        : selectedLead.extracted_data || {};
                                    const standardFields = ['property_type', 'area_sqm', 'address', 'renovation_type', 'budget', 'deadline', 'client_name', 'phone', 'message', 'status', 'is_hot_lead'];
                                    return (_jsxs(_Fragment, { children: [_jsx(QualificationField, { label: "\u0422\u0418\u041F \u041E\u0411\u042A\u0415\u041A\u0422\u0410", value: extractedData.property_type || 'Не указано' }), _jsx(QualificationField, { label: "\u0410\u0414\u0420\u0415\u0421 / \u0416\u041A", value: extractedData.address || 'Не указано' }), _jsx(QualificationField, { label: "\u041F\u041B\u041E\u0429\u0410\u0414\u042C", value: extractedData.area_sqm ? `${extractedData.area_sqm} м²` : 'Не указано' }), _jsx(QualificationField, { label: "\u0422\u0418\u041F \u0420\u0415\u041C\u041E\u041D\u0422\u0410", value: extractedData.renovation_type || 'Не указано' }), _jsx(QualificationField, { label: "\u0411\u042E\u0414\u0416\u0415\u0422", value: extractedData.budget || 'Не указано' }), _jsx(QualificationField, { label: "\u0421\u0420\u041E\u041A\u0418", value: extractedData.deadline || 'Не указано' }), (customFields || []).map((field) => {
                                                const value = extractedData[field.field_name];
                                                return (_jsx(QualificationField, { label: field.field_label.toUpperCase(), value: value ? String(value) : 'Не указано' }, field.id));
                                            })] }));
                                })()] })] })) : (_jsx("div", { className: "flex h-full items-center justify-center text-muted-foreground", children: "\u0412\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \u043B\u0438\u0434\u0430" })) })] }));
}
function QualificationField({ label, value, verified }) {
    return (_jsxs("div", { children: [_jsxs("div", { className: "mb-1 flex items-center gap-2 text-xs font-medium text-muted-foreground", children: [label, verified && _jsx(CheckCircle2, { className: "h-3 w-3 text-green-500" })] }), _jsx("div", { className: "text-sm", children: value || 'Не указано' })] }));
}
