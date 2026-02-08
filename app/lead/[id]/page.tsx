'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { ArrowLeft, Phone, DollarSign, Home } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';

type Lead = {
    id: number;
    clientName: string | null;
    phone: string | null;
    areaSq: number | null;
    budget: number | null;
    status: string;
    avitoLink: string | null;
    createdAt: string;
    chats: Array<{
        id: number;
        messages: Array<{
            role: 'user' | 'ai';
            text: string;
            audioUrl?: string;
            transcript?: string;
            ts: string;
        }>;
    }>;
};

export default function LeadDetailPage() {
    const router = useRouter();
    const params = useParams();
    const [lead, setLead] = useState<Lead | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const token = localStorage.getItem('token');
        if (!token) {
            router.push('/login');
            return;
        }

        fetch(`/api/leads/${params.id}`, {
            headers: {
                Authorization: `Bearer ${token}`,
            },
        })
            .then((res) => res.json())
            .then((data) => {
                setLead(data);
                setLoading(false);
            })
            .catch((error) => {
                console.error('Failed to fetch lead:', error);
                setLoading(false);
            });
    }, [params.id, router]);

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-900 text-white p-4">
                <Skeleton className="h-8 w-32 mb-4" />
                <Skeleton className="h-64 mb-4" />
                <Skeleton className="h-96" />
            </div>
        );
    }

    if (!lead) {
        return (
            <div className="min-h-screen bg-gray-900 text-white p-4">
                <p>Lead not found</p>
            </div>
        );
    }

    const chat = lead.chats[0];

    return (
        <div className="min-h-screen bg-gray-900 text-white">
            {/* Header */}
            <div className="bg-gray-800 border-b border-gray-700 px-4 py-3 flex items-center gap-3">
                <button
                    onClick={() => router.push('/dashboard')}
                    className="p-2 hover:bg-gray-700 rounded-lg"
                >
                    <ArrowLeft size={20} />
                </button>
                <h1 className="text-xl font-bold">{lead.clientName || 'Без имени'}</h1>
            </div>

            <div className="p-4 space-y-4">
                {/* Lead Info Card */}
                <div className="bg-gray-800 rounded-lg p-4 space-y-3">
                    <div className="flex items-center justify-between">
                        <h2 className="text-lg font-semibold">Информация о клиенте</h2>
                        <span className="px-3 py-1 bg-blue-600 rounded-full text-sm">
                            {lead.status}
                        </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {lead.phone && (
                            <div className="flex items-center gap-2 text-gray-300">
                                <Phone size={16} />
                                <span>{lead.phone}</span>
                            </div>
                        )}
                        {lead.areaSq && (
                            <div className="flex items-center gap-2 text-gray-300">
                                <Home size={16} />
                                <span>Площадь: {lead.areaSq} м²</span>
                            </div>
                        )}
                        {lead.budget && (
                            <div className="flex items-center gap-2 text-green-400">
                                <DollarSign size={16} />
                                <span>Бюджет: {lead.budget.toLocaleString()} ₽</span>
                            </div>
                        )}
                        {lead.avitoLink && (
                            <a
                                href={lead.avitoLink}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-400 hover:underline text-sm"
                            >
                                Ссылка на Авито →
                            </a>
                        )}
                    </div>
                </div>

                {/* Chat History */}
                <div className="bg-gray-800 rounded-lg p-4">
                    <h2 className="text-lg font-semibold mb-4">История чата</h2>
                    {chat && chat.messages.length > 0 ? (
                        <div className="space-y-3">
                            {chat.messages.map((msg: any, idx: number) => (
                                <div
                                    key={idx}
                                    className={`p-3 rounded-lg ${msg.role === 'user'
                                            ? 'bg-blue-600 ml-auto max-w-[80%]'
                                            : 'bg-gray-700 mr-auto max-w-[80%]'
                                        }`}
                                >
                                    <p className="text-sm">{msg.text}</p>
                                    {msg.audioUrl && (
                                        <audio controls className="mt-2 w-full">
                                            <source src={msg.audioUrl} type="audio/ogg" />
                                        </audio>
                                    )}
                                    {msg.transcript && (
                                        <p className="text-xs text-gray-400 mt-1 italic">
                                            Транскрипт: {msg.transcript}
                                        </p>
                                    )}
                                    <p className="text-xs text-gray-400 mt-1">
                                        {new Date(msg.ts).toLocaleString('ru-RU')}
                                    </p>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-gray-400 text-sm">Нет сообщений</p>
                    )}
                </div>
            </div>
        </div>
    );
}
