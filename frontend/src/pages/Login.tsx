import React from 'react'
import { Building2, Send, ShieldCheck } from 'lucide-react'

export function Login() {
    const telegramBotName = String(
        (import.meta as any).env.VITE_TELEGRAM_BOT_NAME || 'isaev_karpix_bot'
    ).replace(/^@/, '')
    // Use deep-linking with a start payload so Telegram can re-run /start flow from the link
    // (the user may still need to tap "Start/Restart" depending on Telegram client behavior).
    const telegramBotUrl = `https://t.me/${telegramBotName}?start=crm`

    return (
        <div className="flex min-h-screen items-center justify-center bg-background px-4">
            <div className="w-full max-w-md space-y-8 rounded-2xl border bg-card p-8 shadow-lg">
                <div className="flex flex-col items-center text-center">
                    <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
                        <Building2 className="h-8 w-8 text-primary" />
                    </div>
                    <h1 className="text-2xl font-bold tracking-tight">Вход в CRM</h1>
                    <p className="mt-2 text-sm text-muted-foreground">
                        Авторизуйтесь через официального бота компании для доступа к системе
                    </p>
                </div>

                <div className="mt-8 flex flex-col items-center justify-center space-y-6">
                    <div className="flex flex-col items-center gap-6">
                        <div className="flex items-center gap-2 rounded-full bg-muted/50 px-4 py-2 text-sm text-muted-foreground">
                            <ShieldCheck className="h-4 w-4 text-green-500" />
                            <span>Вход через Telegram-бота</span>
                        </div>

                        <a
                            href={telegramBotUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="w-full rounded-xl bg-primary px-5 py-3 text-center text-sm font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-90 active:opacity-90 flex items-center justify-center gap-2"
                        >
                            <Send className="h-4 w-4" />
                            <span>Открыть бота в Telegram</span>
                        </a>

                        <p className="text-center text-xs text-muted-foreground leading-relaxed max-w-[320px]">
                            Если Telegram установлен, ссылка откроется в приложении и приведёт в чат с ботом.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    )
} 
