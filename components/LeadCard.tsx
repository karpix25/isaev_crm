'use client';

import { motion } from 'framer-motion';
import { Phone, Home, DollarSign, Calendar } from 'lucide-react';

type Lead = {
    id: number;
    clientName: string | null;
    phone: string | null;
    areaSq: number | null;
    budget: number | null;
    status: 'NEW' | 'QUALIFIED' | 'CONSULT' | 'CONTRACT' | 'REPAIR';
    createdAt: string;
};

type LeadCardProps = {
    lead: Lead;
    onClick: () => void;
    index: number;
};

const STATUS_GRADIENTS = {
    NEW: 'gradient-new',
    QUALIFIED: 'gradient-qualified',
    CONSULT: 'gradient-consult',
    CONTRACT: 'gradient-contract',
    REPAIR: 'gradient-repair',
};

export function LeadCard({ lead, onClick, index }: LeadCardProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05, duration: 0.3 }}
            onClick={onClick}
            className="glass rounded-xl p-4 cursor-pointer card-hover group"
        >
            {/* Header with gradient accent */}
            <div className={`h-1 w-full rounded-full mb-3 ${STATUS_GRADIENTS[lead.status]}`} />

            {/* Client Name */}
            <h3 className="font-semibold text-base mb-3 text-white group-hover:text-blue-400 transition-colors">
                {lead.clientName || 'Без имени'}
            </h3>

            {/* Info Grid */}
            <div className="space-y-2">
                {lead.phone && (
                    <div className="flex items-center gap-2 text-sm text-gray-300">
                        <Phone size={14} className="text-blue-400" />
                        <span>{lead.phone}</span>
                    </div>
                )}

                {lead.areaSq && (
                    <div className="flex items-center gap-2 text-sm text-gray-300">
                        <Home size={14} className="text-purple-400" />
                        <span>{lead.areaSq} м²</span>
                    </div>
                )}

                {lead.budget && (
                    <div className="flex items-center gap-2 text-sm font-semibold text-green-400">
                        <DollarSign size={14} />
                        <span>{lead.budget.toLocaleString()} ₽</span>
                    </div>
                )}

                {/* Created Date */}
                <div className="flex items-center gap-2 text-xs text-gray-500 pt-2 border-t border-gray-700">
                    <Calendar size={12} />
                    <span>
                        {new Date(lead.createdAt).toLocaleDateString('ru-RU', {
                            day: 'numeric',
                            month: 'short',
                        })}
                    </span>
                </div>
            </div>

            {/* Hover Glow Effect */}
            <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                <div className={`absolute inset-0 rounded-xl blur-xl opacity-30 ${STATUS_GRADIENTS[lead.status]}`} />
            </div>
        </motion.div>
    );
}
