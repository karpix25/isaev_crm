'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
    const router = useRouter();
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Check if running in Telegram WebApp
        if (typeof window !== 'undefined') {
            const initData = (window as any).Telegram?.WebApp?.initData;

            if (!initData) {
                setError('Please open this app from Telegram');
                setLoading(false);
                return;
            }

            // Authenticate with backend
            fetch('/api/auth/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ initData }),
            })
                .then((res) => res.json())
                .then((data) => {
                    if (data.token) {
                        // Store token in localStorage
                        localStorage.setItem('token', data.token);
                        localStorage.setItem('user', JSON.stringify(data.user));

                        // Redirect to dashboard
                        router.push('/dashboard');
                    } else {
                        setError(data.error || 'Authentication failed');
                        setLoading(false);
                    }
                })
                .catch((err) => {
                    console.error('Auth error:', err);
                    setError('Network error. Please try again.');
                    setLoading(false);
                });
        }
    }, [router]);

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-900">
            <div className="text-center">
                <h1 className="text-3xl font-bold text-white mb-4">RepairCRM</h1>
                {loading && (
                    <div className="text-gray-400">
                        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
                        <p>Authenticating...</p>
                    </div>
                )}
                {error && (
                    <div className="bg-red-500/10 border border-red-500 text-red-500 px-6 py-4 rounded-lg">
                        {error}
                    </div>
                )}
            </div>
        </div>
    );
}
