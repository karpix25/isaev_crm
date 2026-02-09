import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { useLeads } from '@/hooks/useLeads'
import { useChatHistory, useSendMessage } from '@/hooks/useChat'
import { useCustomFields } from '@/hooks/useCustomFields'
import { MessageDirection, type Lead } from '@/types'
import { formatTimeAgo } from '@/lib/utils'
import { Send, Phone, Settings2, CheckCircle2, Sparkles, Info, X } from 'lucide-react'

export function Chat() {
    const { leadId } = useParams()
    const { data } = useLeads()
    const { data: customFields } = useCustomFields(true)
    const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
    const [message, setMessage] = useState('')
    const [activeTrace, setActiveTrace] = useState<any>(null)
    const messagesEndRef = useRef<HTMLDivElement>(null)

    const { data: chatData } = useChatHistory(selectedLead?.id || '', 1)
    const sendMessage = useSendMessage()

    const leads = data?.leads || []
    const messages = chatData?.messages || []

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }

    useEffect(() => {
        scrollToBottom()
    }, [messages])

    // Select lead from URL
    useEffect(() => {
        if (leadId && leads.length > 0) {
            const lead = leads.find(l => l.id === leadId)
            if (lead) {
                setSelectedLead(lead)
            }
        }
    }, [leadId, leads])

    const handleSendMessage = () => {
        if (!selectedLead || !message.trim()) return

        sendMessage.mutate(
            { leadId: selectedLead.id, content: message },
            {
                onSuccess: () => setMessage(''),
            }
        )
    }

    const getMessageLabel = (msg: any) => {
        if (msg.direction === MessageDirection.INBOUND) return 'Клиент'
        if (msg.sender_name === 'AI' || msg.sender_name === 'Bot') return 'ИИ Ассистент'
        return 'Вы'
    }

    return (
        <div className="grid h-full grid-cols-12 gap-4 overflow-hidden">
            {/* Lead List */}
            <div className="col-span-3 flex flex-col rounded-lg border bg-card overflow-hidden">
                <div className="border-b p-4">
                    <h3 className="font-semibold">Диалоги</h3>
                </div>
                <div className="flex-1 overflow-y-auto">
                    {leads.map((lead) => (
                        <button
                            key={lead.id}
                            onClick={() => setSelectedLead(lead)}
                            className={`w-full border-b p-4 text-left transition-colors hover:bg-accent ${selectedLead?.id === lead.id ? 'bg-accent' : ''
                                }`}
                        >
                            <div className="flex items-start gap-3">
                                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground">
                                    {lead.full_name?.[0] || 'U'}
                                </div>
                                <div className="flex-1 overflow-hidden">
                                    <div className="flex items-center justify-between">
                                        <div className="font-medium">{lead.full_name || lead.username || 'Неизвестно'}</div>
                                        {lead.last_message_at && (
                                            <span className="text-xs text-muted-foreground">
                                                {formatTimeAgo(lead.last_message_at)}
                                            </span>
                                        )}
                                    </div>
                                    {lead.ai_summary && (
                                        <p className="truncate text-sm text-muted-foreground">{lead.ai_summary}</p>
                                    )}
                                    {lead.unread_count > 0 && (
                                        <div className="mt-1 flex items-center gap-1 text-xs font-medium text-primary">
                                            <div className="h-2 w-2 rounded-full bg-primary" />
                                            {lead.unread_count}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </button>
                    ))}
                </div>
            </div>

            {/* Chat Window */}
            <div className="col-span-6 flex flex-col rounded-lg border bg-card overflow-hidden">
                {selectedLead ? (
                    <>
                        {/* Chat Header */}
                        <div className="flex items-center justify-between border-b p-4">
                            <div className="flex items-center gap-3">
                                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
                                    {selectedLead.full_name?.[0] || 'U'}
                                </div>
                                <div>
                                    <div className="font-semibold">{selectedLead.full_name || selectedLead.username}</div>
                                    <div className="text-sm text-green-500">AI КВАЛИФИКАЦИЯ: В ПРОЦЕССЕ</div>
                                </div>
                            </div>
                            <div className="flex gap-2">
                                <button className="rounded-lg p-2 hover:bg-accent">
                                    <Phone className="h-5 w-5" />
                                </button>
                                <button className="rounded-lg p-2 hover:bg-accent">
                                    <Settings2 className="h-5 w-5" />
                                </button>
                            </div>
                        </div>

                        {/* Messages */}
                        <div className="flex-1 space-y-4 overflow-y-auto p-4 flex flex-col">
                            {messages.length === 0 ? (
                                <div className="flex h-full items-center justify-center text-muted-foreground">
                                    История диалога пуста. Начните общение.
                                </div>
                            ) : (
                                [...messages].reverse().map((msg) => (
                                    <div
                                        key={msg.id}
                                        className={`flex flex-col ${msg.direction === MessageDirection.OUTBOUND ? 'items-end' : 'items-start'}`}
                                    >
                                        <div
                                            className={`max-w-[80%] rounded-2xl px-4 py-2 relative group ${msg.direction === MessageDirection.OUTBOUND
                                                ? 'bg-blue-600 text-white rounded-br-none shadow-sm'
                                                : 'bg-slate-100 text-slate-900 rounded-bl-none border shadow-sm'
                                                }`}
                                        >
                                            <p className="text-[14px] leading-relaxed whitespace-pre-wrap">{msg.content}</p>

                                            {/* AI Trace Icon */}
                                            {msg.sender_name === 'AI' && msg.ai_metadata && (
                                                <button
                                                    onClick={() => setActiveTrace(msg.ai_metadata)}
                                                    className="absolute -left-8 top-1/2 -translate-y-1/2 p-1.5 bg-background border rounded-full text-primary opacity-0 group-hover:opacity-100 transition-all shadow-sm hover:scale-110"
                                                    title="AI Reasoning Log"
                                                >
                                                    <Sparkles className="h-4 w-4" />
                                                </button>
                                            )}
                                        </div>
                                        <span className="mt-1 px-1 text-[10px] font-medium text-muted-foreground uppercase opacity-70">
                                            {getMessageLabel(msg)} • {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                        </span>
                                    </div>
                                ))
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* AI Trace Modal */}
                        {activeTrace && (
                            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
                                <div className="bg-card w-full max-w-lg rounded-3xl shadow-2xl overflow-hidden border">
                                    <div className="bg-primary p-6 text-primary-foreground flex justify-between items-center">
                                        <div className="flex items-center gap-2">
                                            <Sparkles className="h-6 w-6" />
                                            <h3 className="font-black tracking-tight">AI LOG: RETRIEVED CONTEXT</h3>
                                        </div>
                                        <button onClick={() => setActiveTrace(null)} className="hover:rotate-90 transition-transform">
                                            <X className="h-6 w-6" />
                                        </button>
                                    </div>
                                    <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
                                        {activeTrace.retrieved_context?.length > 0 ? (
                                            activeTrace.retrieved_context.map((doc: any, i: number) => (
                                                <div key={i} className="bg-muted p-4 rounded-2xl space-y-2 border border-primary/10">
                                                    <div className="flex items-center gap-2 text-xs font-black text-primary uppercase tracking-widest">
                                                        <Info className="h-3 w-3" />
                                                        {doc.title}
                                                    </div>
                                                    <p className="text-sm text-muted-foreground leading-relaxed italic">
                                                        "{doc.content}"
                                                    </p>
                                                </div>
                                            ))
                                        ) : (
                                            <div className="text-center py-10 text-muted-foreground">
                                                No specific knowledge base context was retrieved for this message.
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Input */}
                        <div className="border-t p-4">
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={message}
                                    onChange={(e) => setMessage(e.target.value)}
                                    onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                                    placeholder="Ответьте клиенту или спросите AI..."
                                    className="flex-1 rounded-lg border bg-background px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
                                />
                                <button
                                    onClick={handleSendMessage}
                                    disabled={!message.trim()}
                                    className="rounded-lg bg-primary px-4 py-2 text-primary-foreground hover:opacity-90 disabled:opacity-50"
                                >
                                    <Send className="h-5 w-5" />
                                </button>
                            </div>
                        </div>
                    </>
                ) : (
                    <div className="flex h-full items-center justify-center text-muted-foreground">
                        Выберите диалог для начала
                    </div>
                )}
            </div>

            {/* Lead Qualification Panel */}
            <div className="col-span-3 rounded-lg border bg-card p-4">
                {selectedLead ? (
                    <div className="space-y-4">
                        <div className="flex items-center gap-2">
                            <CheckCircle2 className="h-5 w-5 text-primary" />
                            <h3 className="font-semibold">Квалификация лида</h3>
                        </div>

                        <div className="space-y-3">
                            <QualificationField label="ИМЯ КЛИЕНТА" value={selectedLead.full_name} />
                            <QualificationField label="ТЕЛЕФОН" value={selectedLead.phone || 'Не указано'} />
                            <QualificationField label="TELEGRAM" value={selectedLead.username ? `@${selectedLead.username}` : ''} verified />

                            <div className="border-t pt-3">
                                <div className="text-sm font-medium text-muted-foreground">ОБЪЕКТ</div>
                            </div>

                            {(() => {
                                const extractedData = typeof selectedLead.extracted_data === 'string'
                                    ? JSON.parse(selectedLead.extracted_data)
                                    : selectedLead.extracted_data || {}

                                const standardFields = ['property_type', 'area_sqm', 'address', 'renovation_type', 'budget', 'deadline', 'client_name', 'phone', 'message', 'status', 'is_hot_lead'];

                                return (
                                    <>
                                        <QualificationField label="ТИП ОБЪЕКТА" value={extractedData.property_type || 'Не указано'} />
                                        <QualificationField label="АДРЕС / ЖК" value={extractedData.address || 'Не указано'} />
                                        <QualificationField label="ПЛОЩАДЬ" value={extractedData.area_sqm ? `${extractedData.area_sqm} м²` : 'Не указано'} />
                                        <QualificationField label="ТИП РЕМОНТА" value={extractedData.renovation_type || 'Не указано'} />
                                        <QualificationField label="БЮДЖЕТ" value={extractedData.budget || 'Не указано'} />
                                        <QualificationField label="СРОКИ" value={extractedData.deadline || 'Не указано'} />

                                        {/* Dynamic Custom Fields */}
                                        {(customFields || []).map((field) => {
                                            const value = extractedData[field.field_name];
                                            return (
                                                <QualificationField
                                                    key={field.id}
                                                    label={field.field_label.toUpperCase()}
                                                    value={value ? String(value) : 'Не указано'}
                                                />
                                            );
                                        })}
                                    </>
                                )
                            })()}
                        </div>
                    </div>
                ) : (
                    <div className="flex h-full items-center justify-center text-muted-foreground">
                        Выберите лида
                    </div>
                )}
            </div>
        </div>
    )
}

interface QualificationFieldProps {
    label: string
    value: string | null
    verified?: boolean
}

function QualificationField({ label, value, verified }: QualificationFieldProps) {
    return (
        <div>
            <div className="mb-1 flex items-center gap-2 text-xs font-medium text-muted-foreground">
                {label}
                {verified && <CheckCircle2 className="h-3 w-3 text-green-500" />}
            </div>
            <div className="text-sm">{value || 'Не указано'}</div>
        </div>
    )
}
