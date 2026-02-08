'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { ArrowLeft, Phone, Home, DollarSign, Calendar, ExternalLink } from 'lucide-react';
import { ChatBubble } from '@/components/ChatBubble';
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

const STATUS_INFO = {
    NEW: { label: 'Новый', gradient: 'gradient-new', icon: '🆕' },
    QUALIFIED: { label: 'Квалифицирован', gradient: 'gradient-qualified', icon: '✅' },
    CONSULT: { label: 'Консультация', gradient: 'gradient-consult', icon: '💬' },
    CONTRACT: { label: 'Договор', gradient: 'gradient-contract', icon: '📄' },
    REPAIR: { label: 'Ремонт', gradient: 'gradient-repair', icon: '🔧' },
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
            <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white p-4">
                <Skeleton className="h-8 w-32 mb-4 shimmer" />
                <Skeleton className="h-64 mb-4 shimmer" />
                <Skeleton className="h-96 shimmer" />
            </div>
        );
    }

    if (!lead) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white p-4 flex items-center justify-center">
                <div className="text-center">
                    <p className="text-xl text-gray-400">Лид не найден</p>
                    <button
                        onClick={() => router.push('/dashboard')}
                        className="mt-4 btn-primary"
                    >
                        Вернуться на главную
                    </button>
                </div>
            </div>
        );
    }

    const chat = lead.chats[0];
    const statusInfo = STATUS_INFO[lead.status as keyof typeof STATUS_INFO] || STATUS_INFO.NEW;

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white">
            {/* Header */}
            <motion.div
                initial={{ y: -20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                className="glass border-b border-white/10 px-4 py-3 flex items-center gap-3 sticky top-0 z-40 backdrop-blur-xl"
            >
                <button
                    onClick={() => router.push('/dashboard')}
                    className="p-2 hover:bg-white/10 rounded-lg transition"
                >
                    <ArrowLeft size={20} />
                </button>
                <div className="flex-1">
                    <h1 className="text-lg font-bold">{lead.clientName || 'Без имени'}</h1>
                    <p className="text-xs text-gray-400">ID: {lead.id}</p>
                </div>
                <div className={`status-badge ${statusInfo.gradient}`}>
                    <span>{statusInfo.icon}</span>
                    <span>{statusInfo.label}</span>
                </div>
            </motion.div>

            <div className="p-4 space-y-4 max-w-4xl mx-auto">
                {/* Lead Info Card */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="glass rounded-2xl p-6 space-y-4"
                >
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                        <span className="text-2xl">📋</span>
                        Информация о клиенте
                    </h2>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {lead.phone && (
                            <div className="flex items-center gap-3 p-3 bg-white/5 rounded-xl">
                                <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
                                    <Phone size={18} className="text-blue-400" />
                                </div>
                                <div>
                                    <p className="text-xs text-gray-400">Телефон</p>
                                    <p className="font-medium">{lead.phone}</p>
                                </div>
                            </div>
                        )}

                        {lead.areaSq && (
                            <div className="flex items-center gap-3 p-3 bg-white/5 rounded-xl">
                                <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
                                    <Home size={18} className="text-purple-400" />
                                </div>
                                <div>
                                    <p className="text-xs text-gray-400">Площадь</p>
                                    <p className="font-medium">{lead.areaSq} м²</p>
                                </div>
                            </div>
                        )}

                        {lead.budget && (
                            <div className="flex items-center gap-3 p-3 bg-white/5 rounded-xl">
                                <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
                                    <DollarSign size={18} className="text-green-400" />
                                </div>
                                <div>
                                    <p className="text-xs text-gray-400">Бюджет</p>
                                    <p className="font-medium text-green-400">{lead.budget.toLocaleString()} ₽</p>
                                </div>
                            </div>
                        )}

                        <div className="flex items-center gap-3 p-3 bg-white/5 rounded-xl">
                            <div className="w-10 h-10 rounded-lg bg-orange-500/20 flex items-center justify-center">
                                <Calendar size={18} className="text-orange-400" />
                            </div>
                            <div>
                                <p className="text-xs text-gray-400">Создан</p>
                                <p className="font-medium">
                                    {new Date(lead.createdAt).toLocaleDateString('ru-RU', {
                                        day: 'numeric',
                                        month: 'long',
                                        year: 'numeric',
                                    })}
                                </p>
                            </div>
                        </div>
                    </div>

                    {lead.avitoLink && (
                        <a
                            href={lead.avitoLink}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2 text-blue-400 hover:text-blue-300 transition w-fit"
                        >
                            <ExternalLink size={16} />
                            <span className="text-sm">Открыть объявление на Авито</span>
                        </a>
                    )}
                </motion.div>

                {/* Chat History */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="glass rounded-2xl p-6"
                >
                    <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
                        <span className="text-2xl">💬</span>
                        История чата
                    </h2>

                    {chat && chat.messages.length > 0 ? (
                        <div className="space-y-1">
                            {chat.messages.map((msg: any, idx: number) => (
                                <ChatBubble key={idx} message={msg} index={idx} />
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-12">
                            <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-white/5 flex items-center justify-center">
                                <span className="text-4xl">💭</span>
                            </div>
                            <p className="text-gray-400">Пока нет сообщений</p>
                            <p className="text-sm text-gray-500 mt-2">
                                Чат появится после первого общения с клиентом
                            </p>
                        </div>
                    )}
                </motion.div>
            </div>
        </div>
    );
}
