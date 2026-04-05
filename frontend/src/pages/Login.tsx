import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, Loader2, ShieldAlert, ShieldCheck } from 'lucide-react'
import { authAPI } from '@/lib/api'

export function Login() {
    const navigate = useNavigate()

    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [scriptReady, setScriptReady] = useState(false)
    const [botInfo, setBotInfo] = useState<{ bot_id: number; username?: string | null } | null>(null)

    useEffect(() => {
        let cancelled = false
        const script = document.createElement('script')
        script.src = 'https://telegram.org/js/telegram-widget.js?22'
        script.async = true
        script.onload = () => {
            if (!cancelled) setScriptReady(true)
        }
        script.onerror = () => {
            if (!cancelled) setError('Не удалось загрузить Telegram Login скрипт')
        }
        document.body.appendChild(script)

        return () => {
            cancelled = true
            script.remove()
        }
    }, [])

    useEffect(() => {
        let cancelled = false
        ;(async () => {
            try {
                const info = await authAPI.telegramBotInfo()
                if (!cancelled) setBotInfo(info)
            } catch (e: any) {
                if (!cancelled) setError(e?.response?.data?.detail || 'Не удалось получить параметры Telegram-бота')
            }
        })()
        return () => {
            cancelled = true
        }
    }, [])

    const canLogin = useMemo(() => {
        return Boolean(
            scriptReady &&
                botInfo?.bot_id &&
                (window as any).Telegram?.Login?.auth &&
                typeof (window as any).Telegram?.Login?.auth === 'function'
        )
    }, [botInfo?.bot_id, scriptReady])

    const handleTelegramLogin = () => {
        if (!canLogin || !botInfo) return
        setLoading(true)
        setError(null)

        try {
            ;(window as any).Telegram.Login.auth(
                { bot_id: botInfo.bot_id, request_access: 'write' },
                async (_origin: string, user: any) => {
                    if (!user) {
                        setLoading(false)
                        return
                    }
                    try {
                        const response = await authAPI.telegramLogin(user)
                        localStorage.setItem('access_token', response.access_token)
                        localStorage.setItem('refresh_token', response.refresh_token)
                        navigate('/')
                    } catch (err: any) {
                        setError(err.response?.data?.detail || 'Ошибка авторизации через Telegram')
                    } finally {
                        setLoading(false)
                    }
                }
            )
        } catch (e: any) {
            setLoading(false)
            setError(e?.message || 'Ошибка запуска Telegram авторизации')
        }
    }

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
                            <span>Вход через Telegram</span>
                        </div>

                        {error && (
                            <div className="flex w-full items-center gap-2 rounded-lg bg-destructive/10 p-4 text-sm font-medium text-destructive">
                                <ShieldAlert className="h-5 w-5 shrink-0" />
                                <p className="leading-snug">{error}</p>
                            </div>
                        )}

                        {loading ? (
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                                <span>Ожидаем Telegram…</span>
                            </div>
                        ) : (
                            <button
                                type="button"
                                onClick={handleTelegramLogin}
                                disabled={!canLogin}
                                className="w-full rounded-xl bg-primary px-5 py-3 text-center text-sm font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-90 active:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Войти через Telegram
                            </button>
                        )}

                        <p className="text-center text-xs text-muted-foreground leading-relaxed max-w-[320px]">
                            Если кнопка не открывает Telegram — в @BotFather настройте домен через /setdomain для этого бота.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    )
} 
