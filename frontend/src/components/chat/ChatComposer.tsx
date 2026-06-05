import { Paperclip, Send, X } from 'lucide-react'

import { getTransportLabel } from './chatUtils'
import { MessageTransport } from '@/types'

type ChatComposerProps = {
    message: string
    selectedTransport: MessageTransport
    availableTransports: MessageTransport[]
    sendChannelError: string | null
    isMessageSending: boolean
    selectedFile: File | null
    isBusinessCardSending: boolean
    isBusinessCardAvailable: boolean
    isSelectedTransportSendAvailable: boolean
    onMessageChange: (message: string) => void
    onFileChange: (file: File | null) => void
    onTransportChange: (transport: MessageTransport) => void
    onSendMessage: () => void
    onSendBusinessCard: () => void
}

export function ChatComposer({
    message,
    selectedTransport,
    availableTransports,
    sendChannelError,
    isMessageSending,
    selectedFile,
    isBusinessCardSending,
    isBusinessCardAvailable,
    isSelectedTransportSendAvailable,
    onMessageChange,
    onFileChange,
    onTransportChange,
    onSendMessage,
    onSendBusinessCard,
}: ChatComposerProps) {
    const isWhatsappTransport = selectedTransport === MessageTransport.WHATSAPP

    return (
        <div className="border-t p-4 bg-card">
            <div className="mb-2 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Канал</span>
                    <div className="flex rounded-lg border bg-background p-0.5">
                        {availableTransports.map((transport) => (
                            <button
                                key={transport}
                                onClick={() => onTransportChange(transport)}
                                className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${selectedTransport === transport
                                        ? 'bg-primary text-primary-foreground'
                                        : 'text-muted-foreground hover:bg-accent'
                                    }`}
                            >
                                {getTransportLabel(transport)}
                            </button>
                        ))}
                    </div>
                </div>
                <button
                    onClick={onSendBusinessCard}
                    disabled={!isBusinessCardAvailable || isBusinessCardSending}
                    className="rounded-lg border bg-background px-3 py-1.5 text-xs font-semibold transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
                    title={isBusinessCardAvailable ? 'Отправить шаблон визитки в Telegram' : 'Для отправки нужен Telegram у лида'}
                >
                    {isBusinessCardSending ? 'Отправляем визитку...' : 'Отправить визитку (TG)'}
                </button>
            </div>
            {isWhatsappTransport && (
                <div className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">
                    Канал WhatsApp выбран. Сообщение уйдет через подключенную интеграцию.
                </div>
            )}
            {sendChannelError && (
                <div className="mb-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[11px] text-red-700">
                    {sendChannelError}
                </div>
            )}
            <div className="flex gap-2 bg-background rounded-xl border p-1 focus-within:ring-2 focus-within:ring-primary/20 transition-all shadow-inner">
                <label className="flex cursor-pointer items-center justify-center rounded-lg px-2.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
                    <Paperclip className="h-4 w-4" />
                    <input
                        type="file"
                        className="hidden"
                        onChange={(event) => onFileChange(event.target.files?.[0] || null)}
                    />
                </label>
                <input
                    type="text"
                    value={message}
                    onChange={(event) => onMessageChange(event.target.value)}
                    onKeyDown={(event) => {
                        if (event.key === 'Enter') onSendMessage()
                    }}
                    placeholder="Напишите ответ клиенту..."
                    className="flex-1 bg-transparent px-4 py-2.5 text-sm focus:outline-none"
                />
                <button
                    onClick={onSendMessage}
                    disabled={(!message.trim() && !selectedFile) || isMessageSending || !isSelectedTransportSendAvailable}
                    className="rounded-lg bg-primary p-2.5 text-primary-foreground hover:opacity-90 disabled:opacity-50 transition-all shadow-sm active:scale-95 flex items-center justify-center"
                >
                    <Send className="h-4 w-4" />
                </button>
            </div>
            {selectedFile && (
                <div className="mt-2 flex items-center justify-between gap-2 rounded-lg border bg-background px-3 py-2 text-xs">
                    <span className="truncate">{selectedFile.name}</span>
                    <button
                        type="button"
                        onClick={() => onFileChange(null)}
                        className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                    >
                        <X className="h-3.5 w-3.5" />
                    </button>
                </div>
            )}
        </div>
    )
}
