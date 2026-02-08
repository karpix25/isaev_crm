'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, User, Phone, Home, DollarSign } from 'lucide-react';

type AddLeadModalProps = {
    isOpen: boolean;
    onClose: () => void;
    onSubmit: (data: { clientName: string; phone: string; areaSq?: number; budget?: number }) => void;
};

export function AddLeadModal({ isOpen, onClose, onSubmit }: AddLeadModalProps) {
    const [formData, setFormData] = useState({
        clientName: '',
        phone: '',
        areaSq: '',
        budget: '',
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onSubmit({
            clientName: formData.clientName,
            phone: formData.phone,
            areaSq: formData.areaSq ? parseFloat(formData.areaSq) : undefined,
            budget: formData.budget ? parseFloat(formData.budget) : undefined,
        });
        setFormData({ clientName: '', phone: '', areaSq: '', budget: '' });
        onClose();
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="fixed inset-0 z-50 modal-backdrop flex items-center justify-center p-4"
                    >
                        {/* Modal */}
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95, y: 20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: 20 }}
                            transition={{ type: 'spring', duration: 0.3 }}
                            onClick={(e) => e.stopPropagation()}
                            className="glass rounded-2xl p-6 w-full max-w-md relative"
                        >
                            {/* Close Button */}
                            <button
                                onClick={onClose}
                                className="absolute top-4 right-4 p-2 hover:bg-white/10 rounded-lg transition"
                            >
                                <X size={20} />
                            </button>

                            {/* Header */}
                            <h2 className="text-2xl font-bold mb-6 bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                                Новый лид
                            </h2>

                            {/* Form */}
                            <form onSubmit={handleSubmit} className="space-y-4">
                                {/* Client Name */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-300 mb-2">
                                        <User size={16} className="inline mr-2" />
                                        Имя клиента *
                                    </label>
                                    <input
                                        type="text"
                                        required
                                        value={formData.clientName}
                                        onChange={(e) => setFormData({ ...formData, clientName: e.target.value })}
                                        className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                                        placeholder="Иван Петров"
                                    />
                                </div>

                                {/* Phone */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-300 mb-2">
                                        <Phone size={16} className="inline mr-2" />
                                        Телефон *
                                    </label>
                                    <input
                                        type="tel"
                                        required
                                        value={formData.phone}
                                        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                                        className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                                        placeholder="+7 900 123 45 67"
                                    />
                                </div>

                                {/* Area */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-300 mb-2">
                                        <Home size={16} className="inline mr-2" />
                                        Площадь (м²)
                                    </label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        value={formData.areaSq}
                                        onChange={(e) => setFormData({ ...formData, areaSq: e.target.value })}
                                        className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                                        placeholder="45.5"
                                    />
                                </div>

                                {/* Budget */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-300 mb-2">
                                        <DollarSign size={16} className="inline mr-2" />
                                        Бюджет (₽)
                                    </label>
                                    <input
                                        type="number"
                                        value={formData.budget}
                                        onChange={(e) => setFormData({ ...formData, budget: e.target.value })}
                                        className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                                        placeholder="250000"
                                    />
                                </div>

                                {/* Buttons */}
                                <div className="flex gap-3 pt-4">
                                    <button
                                        type="button"
                                        onClick={onClose}
                                        className="flex-1 px-4 py-3 bg-white/5 hover:bg-white/10 rounded-lg font-medium transition"
                                    >
                                        Отмена
                                    </button>
                                    <button
                                        type="submit"
                                        className="flex-1 btn-primary"
                                    >
                                        Создать
                                    </button>
                                </div>
                            </form>
                        </motion.div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
}
