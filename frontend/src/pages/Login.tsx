import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, Loader2, ShieldCheck, ShieldAlert } from 'lucide-react'
import { authAPI } from '@/lib/api'

export function Login() {
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const navigate = useNavigate()
    const containerRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        // Expose callback to window for the Telegram script
        ;(window as any).onTelegramAuth = async (user: any) => {
            setLoading(true)
            setError(null)
            try {
                const response = await authAPI.telegramLogin(user)
                localStorage.setItem('access_token', response.access_token)
                navigate('/')
            } catch (err: any) {
                setError(err.response?.data?.detail || 'Ошибка авторизации через Telegram')
            } finally {
                setLoading(false)
            }
        }

        // Create script
        const script = document.createElement('script')
        script.src = 'https://telegram.org/js/telegram-widget.js?22'
        script.setAttribute('data-telegram-login', import.meta.env.VITE_TELEGRAM_BOT_NAME || 'isaev_karpix_bot')
        script.setAttribute('data-size', 'large')
        script.setAttribute('data-radius', '10')
        script.setAttribute('data-request-access', 'write')
        script.setAttribute('data-onauth', 'onTelegramAuth(user)')
        script.async = true

        if (containerRef.current) {
            containerRef.current.innerHTML = ''
            containerRef.current.appendChild(script)
        }

        return () => {
            // Cleanup
            delete (window as any).onTelegramAuth
        }
    }, [navigate])

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

                {error && (
                    <div className="flex items-center gap-2 rounded-lg bg-destructive/10 p-4 text-sm font-medium text-destructive">
                        <ShieldAlert className="h-5 w-5 shrink-0" />
                        <p>{error}</p>
                    </div>
                )}

                <div className="mt-8 flex flex-col items-center justify-center space-y-6">
                    {loading ? (
                        <div className="flex flex-col items-center gap-4 py-8">
                            <Loader2 className="h-8 w-8 animate-spin text-primary" />
                            <p className="text-sm text-muted-foreground">Проверка доступов...</p>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center gap-6">
                            <div className="flex items-center gap-2 text-sm text-muted-foreground bg-muted/50 py-2 px-4 rounded-full">
                                <ShieldCheck className="h-4 w-4 text-green-500" />
                                <span>Безопасный вход без паролей</span>
                            </div>
                            
                            {/* Container for Telegram Widget */}
                            <div ref={containerRef} className="h-[40px] flex items-center justify-center"></div>
                            
                            <p className="text-center text-xs text-muted-foreground mt-4 leading-relaxed max-w-[280px]">
                                Внимание: первый авторизовавшийся пользователь автоматически получит права Администратора.
                            </p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
} 
