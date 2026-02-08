'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Skeleton } from '@/components/ui/skeleton';
import { Plus, LogOut } from 'lucide-react';

type Lead = {
    id: number;
    clientName: string | null;
    phone: string | null;
    areaSq: number | null;
    budget: number | null;
    status: 'NEW' | 'QUALIFIED' | 'CONSULT' | 'CONTRACT' | 'REPAIR';
    avitoLink: string | null;
    createdAt: string;
};

const STATUS_COLUMNS = [
    { key: 'NEW', label: 'Новый', color: 'bg-gray-700' },
    { key: 'QUALIFIED', label: 'Квалифицирован', color: 'bg-blue-700' },
    { key: 'CONSULT', label: 'Консультация', color: 'bg-yellow-700' },
    { key: 'CONTRACT', label: 'Договор', color: 'bg-green-700' },
    { key: 'REPAIR', label: 'Ремонт', color: 'bg-purple-700' },
];

export default function DashboardPage() {
    const router = useRouter();
    const [leads, setLeads] = useState<Lead[]>([]);
    const [loading, setLoading] = useState(true);
    const [user, setUser] = useState<any>(null);

    useEffect(() => {
        const token = localStorage.getItem('token');
        const userData = localStorage.getItem('user');

        if (!token) {
            router.push('/login');
            return;
        }

        if (userData) {
            setUser(JSON.parse(userData));
        }

        fetchLeads(token);
    }, [router]);

    const fetchLeads = async (token: string) => {
        try {
            const res = await fetch('/api/leads', {
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            });

            if (res.ok) {
                const data = await res.json();
                setLeads(data);
            } else if (res.status === 401) {
                router.push('/login');
            }
        } catch (error) {
            console.error('Failed to fetch leads:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleStatusChange = async (leadId: number, newStatus: string) => {
        const token = localStorage.getItem('token');
        if (!token) return;

        try {
            const res = await fetch('/api/leads', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ id: leadId, status: newStatus }),
            });

            if (res.ok) {
                fetchLeads(token);
            }
        } catch (error) {
            console.error('Failed to update lead:', error);
        }
    };

    const handleLogout = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        router.push('/login');
    };

    const getLeadsByStatus = (status: string) => {
        return leads.filter((lead) => lead.status === status);
    };

    return (
        <div className="min-h-screen bg-gray-900 text-white">
            {/* Header */}
            <div className="bg-gray-800 border-b border-gray-700 px-4 py-3 flex justify-between items-center">
                <div>
                    <h1 className="text-xl font-bold">RepairCRM</h1>
                    {user && <p className="text-sm text-gray-400">{user.name}</p>}
                </div>
                <button
                    onClick={handleLogout}
                    className="flex items-center gap-2 px-3 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-sm"
                >
                    <LogOut size={16} />
                    Выйти
                </button>
            </div>

            {/* Kanban Board */}
            <div className="p-4">
                {loading ? (
                    <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                        {[1, 2, 3, 4, 5].map((i) => (
                            <Skeleton key={i} className="h-96" />
                        ))}
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-5 gap-4 overflow-x-auto">
                        {STATUS_COLUMNS.map((column) => (
                            <div key={column.key} className="flex flex-col min-w-[280px]">
                                <div className={`${column.color} px-4 py-2 rounded-t-lg font-semibold`}>
                                    {column.label} ({getLeadsByStatus(column.key).length})
                                </div>
                                <div className="bg-gray-800 rounded-b-lg p-2 flex-1 space-y-2 min-h-[400px]">
                                    {getLeadsByStatus(column.key).map((lead) => (
                                        <div
                                            key={lead.id}
                                            onClick={() => router.push(`/lead/${lead.id}`)}
                                            className="bg-gray-700 hover:bg-gray-600 p-3 rounded-lg cursor-pointer transition"
                                        >
                                            <h3 className="font-semibold text-sm mb-1">
                                                {lead.clientName || 'Без имени'}
                                            </h3>
                                            {lead.phone && (
                                                <p className="text-xs text-gray-400 mb-1">{lead.phone}</p>
                                            )}
                                            {lead.areaSq && (
                                                <p className="text-xs text-gray-400">Площадь: {lead.areaSq} м²</p>
                                            )}
                                            {lead.budget && (
                                                <p className="text-xs text-green-400">
                                                    Бюджет: {lead.budget.toLocaleString()} ₽
                                                </p>
                                            )}
                                            <div className="mt-2 flex gap-1">
                                                {column.key !== 'REPAIR' && (
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            const nextStatus = STATUS_COLUMNS[
                                                                STATUS_COLUMNS.findIndex((c) => c.key === column.key) + 1
                                                            ]?.key;
                                                            if (nextStatus) {
                                                                handleStatusChange(lead.id, nextStatus);
                                                            }
                                                        }}
                                                        className="text-xs bg-blue-600 hover:bg-blue-700 px-2 py-1 rounded"
                                                    >
                                                        →
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Floating Add Button */}
            <button
                onClick={() => {
                    const clientName = prompt('Имя клиента:');
                    const phone = prompt('Телефон:');
                    if (clientName || phone) {
                        const token = localStorage.getItem('token');
                        fetch('/api/leads', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                Authorization: `Bearer ${token}`,
                            },
                            body: JSON.stringify({ clientName, phone }),
                        }).then(() => {
                            if (token) fetchLeads(token);
                        });
                    }
                }}
                className="fixed bottom-6 right-6 bg-blue-600 hover:bg-blue-700 text-white rounded-full p-4 shadow-lg"
            >
                <Plus size={24} />
            </button>
        </div>
    );
}
