import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, Loader2, Send, ShieldAlert, ShieldCheck } from 'lucide-react'
import { authAPI } from '@/lib/api'

export function Login() {
    const navigate = useNavigate()

    const [error, setError] = useState<string | null>(null)
    const [loading, setLoading] = useState(true)
    const [sessionId, setSessionId] = useState<string | null>(null)
    const [botUsername, setBotUsername] = useState<string | null>(null)
    const [isPolling, setIsPolling] = useState(false)
    const [waitingConfirm, setWaitingConfirm] = useState(false)

    useEffect(() => {
        let cancelled = false
        ;(async () => {
            setLoading(true)
            setError(null)
            try {
                const res = await authAPI.telegramBotLoginInit()
                if (cancelled) return
                setSessionId(res.session_id)
                setBotUsername(String(res.bot_username || '').replace(/^@/, ''))
                setIsPolling(true)
            } catch (e: any) {
                if (!cancelled) setError(e?.response?.data?.detail || 'Не удалось инициализировать вход через Telegram')
            } finally {
                if (!cancelled) setLoading(false)
            }
        })()
        return () => {
            cancelled = true
        }
    }, [])

    useEffect(() => {
        if (!sessionId || !isPolling) return

        let stopped = false
        const interval = window.setInterval(async () => {
            if (stopped) return
            try {
                const res = await authAPI.telegramBotLoginCheck(sessionId)
                if (res.status === 'authorized' && res.access_token) {
                    localStorage.setItem('access_token', res.access_token)
                    if (res.refresh_token) localStorage.setItem('refresh_token', res.refresh_token)
                    setIsPolling(false)
                    navigate('/')
                    return
                }
                if (res.status === 'expired') {
                    setIsPolling(false)
                    setWaitingConfirm(false)
                    setError('Сессия входа истекла. Обновите страницу и попробуйте снова.')
                    return
                }
            } catch {
                // ignore transient network errors during telegram switching
            }
        }, 2000)

        return () => {
            stopped = true
            window.clearInterval(interval)
        }
    }, [isPolling, navigate, sessionId])

    const telegramDeepLink = useMemo(() => {
        if (!botUsername || !sessionId) return null
        return `https://t.me/${botUsername}?start=login_${sessionId}`
    }, [botUsername, sessionId])

    const handleOpenTelegram = () => {
        if (!telegramDeepLink) return
        setWaitingConfirm(true)
        window.open(telegramDeepLink, '_blank', 'noopener,noreferrer')
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
                                <span>Подготовка входа…</span>
                            </div>
                        ) : (
                            <button
                                type="button"
                                onClick={handleOpenTelegram}
                                disabled={!telegramDeepLink}
                                className="w-full rounded-xl bg-primary px-5 py-3 text-center text-sm font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-90 active:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <span className="inline-flex items-center justify-center gap-2">
                                    <Send className="h-4 w-4" />
                                    <span>Открыть бота в Telegram</span>
                                </span>
                            </button>
                        )}

                        {waitingConfirm && (
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                                <span>Ждём подтверждения в Telegram…</span>
                            </div>
                        )}

                        <p className="text-center text-xs text-muted-foreground leading-relaxed max-w-[320px]">
                            Откройте бота и нажмите «Start/Запустить». После подтверждения вернитесь на сайт — вход произойдёт автоматически.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    )
} 
