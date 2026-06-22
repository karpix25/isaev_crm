import { Mic, ShieldCheck, Sparkles } from 'lucide-react'

import { formatChatMessageDateTime, getChatMessageLabel, getTransportShortLabel } from './chatUtils'
import { MessageDirection, type ChatMessage } from '@/types'
import { MessageMediaAttachment } from './MessageMediaAttachment'
import { MessageToolCallBadge } from './MessageToolCallBadge'

type ChatMessageBubbleProps = {
    message: ChatMessage
    leadSource?: string | null
}

export function ChatMessageBubble({ message, leadSource }: ChatMessageBubbleProps) {
    const isOutbound = message.direction === MessageDirection.OUTBOUND
    const hasContent = Boolean(message.content?.trim())

    return (
        <div className={`flex flex-col ${isOutbound ? 'items-end' : 'items-start'}`}>
            <div
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 shadow-sm text-[13px] relative group ${isOutbound
                        ? 'bg-primary text-primary-foreground rounded-br-none'
                        : 'bg-slate-100 text-slate-900 border rounded-bl-none'
                    }`}
            >
                {message.ai_metadata?.is_voice && (
                    <div className={`flex items-center gap-1 mb-1.5 text-xs font-semibold ${isOutbound ? 'text-primary-foreground/80' : 'text-slate-500'}`}>
                        <Mic className="h-3 w-3" />
                        Голосовое сообщение
                    </div>
                )}
                <MessageMediaAttachment
                    mediaUrl={message.media_url}
                    mediaFilename={message.media_filename}
                    mediaMimetype={message.media_mimetype}
                    isOutbound={isOutbound}
                />
                {hasContent && <p className="leading-relaxed whitespace-pre-wrap">{message.content}</p>}
            </div>

            <div className={`flex flex-col mt-1.5 gap-1.5 ${isOutbound ? 'items-end' : 'items-start'}`}>
                {message.ai_metadata?.status_changed_to && (
                    <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-primary/10 text-primary rounded-xl text-[11px] font-medium border border-primary/20 shadow-sm animate-in fade-in slide-in-from-bottom-2">
                        <ShieldCheck className="h-3.5 w-3.5" />
                        ИИ перевел на стадию: {message.ai_metadata.status_changed_to}
                    </div>
                )}
                {message.ai_metadata?.qualification_changed_to && (
                    <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-emerald-100 text-emerald-700 rounded-xl text-[11px] font-medium border border-emerald-200 shadow-sm animate-in fade-in slide-in-from-bottom-2">
                        <Sparkles className="h-3.5 w-3.5" />
                        ИИ квалифицировал лида
                    </div>
                )}
                {message.ai_metadata?.source === 'CRM' && (
                    <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-100 text-slate-600 rounded-xl text-[11px] font-medium border border-slate-200 shadow-sm animate-in fade-in slide-in-from-bottom-2">
                        Отправлено из CRM
                    </div>
                )}
                <MessageToolCallBadge message={message} leadSource={leadSource} />
                <span className="px-1 text-[9px] font-bold text-muted-foreground uppercase tracking-widest opacity-60">
                    {getChatMessageLabel(message)} • {getTransportShortLabel(message.transport)} • {formatChatMessageDateTime(message.created_at)}
                </span>
            </div>
        </div>
    )
}
