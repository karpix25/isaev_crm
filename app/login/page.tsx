'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Loader2 } from 'lucide-react';

// DEV MODE: Set to true to bypass Telegram auth for local testing
const DEV_MODE = true;

export default function LoginPage() {
    const router = useRouter();
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // DEV MODE: Auto-login with test credentials
        if (DEV_MODE) {
            console.log('🔧 DEV MODE: Bypassing Telegram auth');
            const testToken = 'dev-test-token-' + Date.now();
            const testUser = {
                id: 123456789,
                name: 'Тестовый Менеджер',
                role: 'manager',
            };

            localStorage.setItem('token', testToken);
            localStorage.setItem('user', JSON.stringify(testUser));

            setTimeout(() => {
                router.push('/dashboard');
            }, 500);
            return;
        }

        // PRODUCTION: Telegram WebApp auth
        const initTelegramAuth = async () => {
            try {
                // Check if Telegram WebApp is available
                if (typeof window === 'undefined' || !window.Telegram?.WebApp) {
                    setError('Please open this app from Telegram');
                    setLoading(false);
                    return;
                }

                const tg = window.Telegram.WebApp;
                tg.ready();
                tg.expand();

                const initData = tg.initData;
                if (!initData) {
                    setError('No Telegram data found');
                    setLoading(false);
                    return;
                }

                // Send initData to backend for verification
                const res = await fetch('/api/auth/verify', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ initData }),
                });

                const data = await res.json();

                if (res.ok && data.token) {
                    localStorage.setItem('token', data.token);
                    localStorage.setItem('user', JSON.stringify(data.user));
                    router.push('/dashboard');
                } else {
                    setError(data.error || 'Authentication failed');
                    setLoading(false);
                }
            } catch (err) {
                console.error('Auth error:', err);
                setError('Failed to authenticate');
                setLoading(false);
            }
        };

        initTelegramAuth();
    }, [router]);

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 flex items-center justify-center p-4">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="glass rounded-2xl p-8 max-w-md w-full text-center"
            >
                <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                    <span className="text-4xl">🔧</span>
                </div>

                <h1 className="text-3xl font-bold mb-2 bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                    RepairCRM
                </h1>

                {DEV_MODE && (
                    <div className="mb-4 px-4 py-2 bg-yellow-500/20 border border-yellow-500/30 rounded-lg">
                        <p className="text-sm text-yellow-400">🔧 DEV MODE активен</p>
                    </div>
                )}

                {loading ? (
                    <div className="flex flex-col items-center gap-3 py-8">
                        <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
                        <p className="text-gray-400">
                            {DEV_MODE ? 'Вход в систему...' : 'Authenticating...'}
                        </p>
                    </div>
                ) : error ? (
                    <div className="py-8">
                        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-500/20 flex items-center justify-center">
                            <span className="text-3xl">⚠️</span>
                        </div>
                        <p className="text-red-400 mb-4">{error}</p>
                        <p className="text-sm text-gray-500">
                            This app must be opened from Telegram
                        </p>
                    </div>
                ) : null}
            </motion.div>
        </div>
    );
}
