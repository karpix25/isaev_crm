import { forwardRef } from 'react'
import { MessageSquare } from 'lucide-react'

import type { ChatMessage } from '@/types'
import { ChatMessageBubble } from './ChatMessageBubble'

type ChatMessageListProps = {
    messages: ChatMessage[]
    leadSource?: string | null
}

export const ChatMessageList = forwardRef<HTMLDivElement, ChatMessageListProps>(
    function ChatMessageList({ messages, leadSource }, messagesEndRef) {
        return (
            <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar bg-slate-50/30">
                {messages.length === 0 ? (
                    <div className="flex h-full items-center justify-center text-muted-foreground flex-col gap-2">
                        <MessageSquare className="h-8 w-8 opacity-20" />
                        <p className="text-sm">История диалога пуста</p>
                    </div>
                ) : (
                    [...messages].reverse().map((message) => (
                        <ChatMessageBubble
                            key={message.id}
                            message={message}
                            leadSource={leadSource}
                        />
                    ))
                )}
                <div ref={messagesEndRef} />
            </div>
        )
    }
)
