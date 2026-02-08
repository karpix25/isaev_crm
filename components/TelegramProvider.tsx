'use client';

import { useEffect } from 'react';

export function TelegramProvider({ children }: { children: React.ReactNode }) {
    useEffect(() => {
        if (typeof window !== 'undefined') {
            const tg = (window as any).Telegram?.WebApp;

            if (tg) {
                // Initialize Telegram WebApp
                tg.ready();
                tg.expand();

                // Apply theme colors
                document.documentElement.style.setProperty(
                    '--tg-theme-bg-color',
                    tg.themeParams.bg_color || '#1a1a1a'
                );
                document.documentElement.style.setProperty(
                    '--tg-theme-text-color',
                    tg.themeParams.text_color || '#ffffff'
                );
                document.documentElement.style.setProperty(
                    '--tg-theme-button-color',
                    tg.themeParams.button_color || '#3b82f6'
                );
            }
        }
    }, []);

    return <>{children}</>;
}
