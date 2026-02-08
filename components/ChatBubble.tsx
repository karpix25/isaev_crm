'use client';

import { motion } from 'framer-motion';
import { User, Bot } from 'lucide-react';

type Message = {
    role: 'user' | 'ai';
    text: string;
    audioUrl?: string;
    transcript?: string;
    ts: string;
};

type ChatBubbleProps = {
    message: Message;
    index: number;
};

export function ChatBubble({ message, index }: ChatBubbleProps) {
    const isUser = message.role === 'user';

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05, duration: 0.3 }}
            className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} items-end mb-4`}
        >
            {/* Avatar */}
            <div
                className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${isUser ? 'bg-blue-600' : 'bg-gray-700'
                    }`}
            >
                {isUser ? <User size={16} /> : <Bot size={16} />}
            </div>

            {/* Message Bubble */}
            <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-[75%]`}>
                <div className={`chat-bubble ${isUser ? 'chat-bubble-user' : 'chat-bubble-ai'}`}>
                    <p className="text-sm leading-relaxed">{message.text}</p>

                    {/* Audio Player */}
                    {message.audioUrl && (
                        <audio controls className="mt-3 w-full max-w-xs">
                            <source src={message.audioUrl} type="audio/ogg" />
                        </audio>
                    )}

                    {/* Transcript */}
                    {message.transcript && (
                        <p className="text-xs text-gray-300 mt-2 italic opacity-70">
                            🎤 {message.transcript}
                        </p>
                    )}
                </div>

                {/* Timestamp */}
                <span className="text-xs text-gray-500 mt-1 px-2">
                    {new Date(message.ts).toLocaleTimeString('ru-RU', {
                        hour: '2-digit',
                        minute: '2-digit',
                    })}
                </span>
            </div>
        </motion.div>
    );
}
