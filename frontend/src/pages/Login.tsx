import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, Loader2, Send, ShieldAlert, ShieldCheck } from 'lucide-react'
import { authAPI } from '@/lib/api'

export function Login() {
    const navigate = useNavigate()

    const telegramBotName = String(
        (import.meta as any).env.VITE_TELEGRAM_BOT_NAME || 'isaev_karpix_bot'
    ).replace(/^@/, '')

    const [session, setSession] = useState<{ state: string; expiresAt: number } | null>(null)
    const [started, setStarted] = useState(false)
    const [status, setStatus] = useState<'idle' | 'pending' | 'expired'>('idle')
    const [error, setError] = useState<string | null>(null)

    const telegramBotUrl = useMemo(() => {
        if (!session) return null
        return `https://t.me/${telegramBotName}?start=crm_login_${session.state}`
    }, [session, telegramBotName])

    const createSession = useCallback(async () => {
        setError(null)
        setStatus('idle')
        setStarted(false)
        try {
            const res = await authAPI.telegramBotLoginStart()
            const expiresAt = Date.now() + res.expires_in * 1000
            setSession({ state: res.state, expiresAt })
            localStorage.setItem('tg_login_state', res.state)
            localStorage.setItem('tg_login_expires_at', String(expiresAt))
            localStorage.removeItem('tg_login_started')
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Не удалось подготовить вход через Telegram')
        }
    }, [])

    useEffect(() => {
        const savedState = localStorage.getItem('tg_login_state')
        const savedExpiresAt = Number(localStorage.getItem('tg_login_expires_at') || 0)
        const savedStarted = localStorage.getItem('tg_login_started') === '1'

        if (savedState && savedExpiresAt && savedExpiresAt > Date.now()) {
            setSession({ state: savedState, expiresAt: savedExpiresAt })
            setStarted(savedStarted)
            setStatus(savedStarted ? 'pending' : 'idle')
            return
        }

        createSession()
    }, [createSession])

    useEffect(() => {
        if (!started || !session) return

        let stopped = false
        const interval = window.setInterval(async () => {
            if (stopped) return
            try {
                const res = await authAPI.telegramBotLoginStatus(session.state)
                if (res.status === 'approved' && res.access_token) {
                    localStorage.setItem('access_token', res.access_token)
                    if (res.refresh_token) localStorage.setItem('refresh_token', res.refresh_token)
                    localStorage.removeItem('tg_login_state')
                    localStorage.removeItem('tg_login_expires_at')
                    localStorage.removeItem('tg_login_started')
                    navigate('/')
                    return
                }
                if (res.status === 'expired') {
                    setStatus('expired')
                    setStarted(false)
                    localStorage.removeItem('tg_login_started')
                    return
                }
                setStatus('pending')
            } catch {
                // Keep polling; transient network errors happen during app switching
                setStatus('pending')
            }
        }, 1200)

        return () => {
            stopped = true
            window.clearInterval(interval)
        }
    }, [navigate, session, started])

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

                        {error && (
                            <div className="flex w-full items-center gap-2 rounded-lg bg-destructive/10 p-4 text-sm font-medium text-destructive">
                                <ShieldAlert className="h-5 w-5 shrink-0" />
                                <p className="leading-snug">{error}</p>
                            </div>
                        )}

                        <a
                            href={telegramBotUrl || '#'}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => {
                                if (!telegramBotUrl) {
                                    e.preventDefault()
                                    return
                                }
                                setStarted(true)
                                setStatus('pending')
                                localStorage.setItem('tg_login_started', '1')
                            }}
                            className={`w-full rounded-xl bg-primary px-5 py-3 text-center text-sm font-semibold text-primary-foreground shadow-sm transition-opacity flex items-center justify-center gap-2 ${
                                telegramBotUrl ? 'hover:opacity-90 active:opacity-90' : 'opacity-50 pointer-events-none'
                            }`}
                        >
                            <Send className="h-4 w-4" />
                            <span>Открыть бота в Telegram</span>
                        </a>

                        {started && status === 'pending' && (
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                                <span>Ожидаем подтверждение в Telegram…</span>
                            </div>
                        )}

                        {started && status === 'pending' && session && (
                            <div className="w-full rounded-lg bg-muted/50 p-4 text-xs text-muted-foreground">
                                <p>
                                    Если бот уже был запущен и команда не отправляется автоматически, просто отправьте
                                    боту этот код:
                                </p>
                                <div className="mt-2 rounded-md bg-background px-3 py-2 font-mono text-[11px] text-foreground break-all border">
                                    {session.state}
                                </div>
                            </div>
                        )}

                        {status === 'expired' && (
                            <div className="flex flex-col items-center gap-3 text-center">
                                <p className="text-xs text-muted-foreground">
                                    Ссылка для входа истекла. Сгенерируйте новую и откройте бота ещё раз.
                                </p>
                                <button
                                    onClick={createSession}
                                    className="rounded-lg bg-muted px-4 py-2 text-xs font-semibold text-foreground hover:bg-muted/80"
                                >
                                    Сгенерировать новую ссылку
                                </button>
                            </div>
                        )}

                        <p className="text-center text-xs text-muted-foreground leading-relaxed max-w-[320px]">
                            После открытия бота нажмите «Start/Запустить». Затем вернитесь на сайт — вход произойдёт автоматически.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    )
} 
