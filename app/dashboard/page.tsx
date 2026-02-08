'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { DndContext, DragEndEvent, DragOverlay, DragStartEvent, closestCorners } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { motion } from 'framer-motion';
import { Plus, LogOut, Sparkles } from 'lucide-react';
import { LeadCard } from '@/components/LeadCard';
import { AddLeadModal } from '@/components/AddLeadModal';
import { Skeleton } from '@/components/ui/skeleton';

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
    { key: 'NEW' as const, label: 'Новый', icon: '🆕', gradient: 'gradient-new' },
    { key: 'QUALIFIED' as const, label: 'Квалифицирован', icon: '✅', gradient: 'gradient-qualified' },
    { key: 'CONSULT' as const, label: 'Консультация', icon: '💬', gradient: 'gradient-consult' },
    { key: 'CONTRACT' as const, label: 'Договор', icon: '📄', gradient: 'gradient-contract' },
    { key: 'REPAIR' as const, label: 'Ремонт', icon: '🔧', gradient: 'gradient-repair' },
];

export default function DashboardPage() {
    const router = useRouter();
    const [leads, setLeads] = useState<Lead[]>([]);
    const [loading, setLoading] = useState(true);
    const [user, setUser] = useState<any>(null);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [activeId, setActiveId] = useState<number | null>(null);

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

    const handleDragStart = (event: DragStartEvent) => {
        setActiveId(event.active.id as number);
    };

    const handleDragEnd = (event: DragEndEvent) => {
        const { active, over } = event;
        setActiveId(null);

        if (!over) return;

        const leadId = active.id as number;
        const newStatus = over.id as Lead['status'];

        const lead = leads.find((l) => l.id === leadId);
        if (lead && lead.status !== newStatus) {
            updateLeadStatus(leadId, newStatus);
        }
    };

    const updateLeadStatus = async (leadId: number, newStatus: Lead['status']) => {
        const token = localStorage.getItem('token');
        if (!token) return;

        // Optimistic update
        setLeads((prev) =>
            prev.map((lead) => (lead.id === leadId ? { ...lead, status: newStatus } : lead))
        );

        try {
            const res = await fetch('/api/leads', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ id: leadId, status: newStatus }),
            });

            if (!res.ok) {
                // Revert on error
                fetchLeads(token);
            }
        } catch (error) {
            console.error('Failed to update lead:', error);
            fetchLeads(token);
        }
    };

    const handleAddLead = async (data: any) => {
        const token = localStorage.getItem('token');
        if (!token) return;

        try {
            const res = await fetch('/api/leads', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify(data),
            });

            if (res.ok) {
                fetchLeads(token);
            }
        } catch (error) {
            console.error('Failed to create lead:', error);
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

    const activeLead = leads.find((lead) => lead.id === activeId);

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white">
            {/* Header */}
            <motion.div
                initial={{ y: -20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                className="glass border-b border-white/10 px-6 py-4 flex justify-between items-center sticky top-0 z-40 backdrop-blur-xl"
            >
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                        <Sparkles size={20} />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                            RepairCRM
                        </h1>
                        {user && <p className="text-sm text-gray-400">{user.name}</p>}
                    </div>
                </div>
                <button
                    onClick={handleLogout}
                    className="flex items-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 rounded-lg text-sm transition"
                >
                    <LogOut size={16} />
                    Выйти
                </button>
            </motion.div>

            {/* Kanban Board */}
            <div className="p-6">
                {loading ? (
                    <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                        {[1, 2, 3, 4, 5].map((i) => (
                            <Skeleton key={i} className="h-96 shimmer" />
                        ))}
                    </div>
                ) : (
                    <DndContext
                        collisionDetection={closestCorners}
                        onDragStart={handleDragStart}
                        onDragEnd={handleDragEnd}
                    >
                        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                            {STATUS_COLUMNS.map((column, colIndex) => {
                                const columnLeads = getLeadsByStatus(column.key);
                                return (
                                    <motion.div
                                        key={column.key}
                                        initial={{ opacity: 0, y: 20 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: colIndex * 0.1 }}
                                        className="flex flex-col min-w-[280px]"
                                    >
                                        {/* Column Header */}
                                        <div className={`${column.gradient} px-4 py-3 rounded-t-xl font-semibold flex items-center justify-between shadow-lg`}>
                                            <span className="flex items-center gap-2">
                                                <span className="text-xl">{column.icon}</span>
                                                {column.label}
                                            </span>
                                            <span className="bg-white/20 px-2 py-1 rounded-full text-xs font-bold">
                                                {columnLeads.length}
                                            </span>
                                        </div>

                                        {/* Droppable Area */}
                                        <SortableContext
                                            id={column.key}
                                            items={columnLeads.map((l) => l.id)}
                                            strategy={verticalListSortingStrategy}
                                        >
                                            <div
                                                id={column.key}
                                                className="glass rounded-b-xl p-3 flex-1 space-y-3 min-h-[500px] border border-white/5"
                                            >
                                                {columnLeads.map((lead, idx) => (
                                                    <div key={lead.id} draggable onDragStart={() => setActiveId(lead.id)}>
                                                        <LeadCard
                                                            lead={lead}
                                                            onClick={() => router.push(`/lead/${lead.id}`)}
                                                            index={idx}
                                                        />
                                                    </div>
                                                ))}
                                            </div>
                                        </SortableContext>
                                    </motion.div>
                                );
                            })}
                        </div>

                        {/* Drag Overlay */}
                        <DragOverlay>
                            {activeLead && (
                                <div className="drag-overlay">
                                    <LeadCard lead={activeLead} onClick={() => { }} index={0} />
                                </div>
                            )}
                        </DragOverlay>
                    </DndContext>
                )}
            </div>

            {/* Floating Add Button */}
            <motion.button
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.5, type: 'spring' }}
                onClick={() => setIsModalOpen(true)}
                className="fixed bottom-8 right-8 w-16 h-16 btn-primary rounded-full shadow-2xl flex items-center justify-center group"
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.95 }}
            >
                <Plus size={28} className="group-hover:rotate-90 transition-transform duration-300" />
            </motion.button>

            {/* Add Lead Modal */}
            <AddLeadModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                onSubmit={handleAddLead}
            />
        </div>
    );
}
