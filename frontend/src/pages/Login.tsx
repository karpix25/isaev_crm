import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, Lock, Mail, Loader2 } from 'lucide-react'
import { authAPI } from '@/lib/api'

export function Login() {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const navigate = useNavigate()

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setLoading(true)
        setError(null)

        try {
            const response = await authAPI.login({ email, password })
            localStorage.setItem('access_token', response.access_token)
            navigate('/')
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Неверный email или пароль')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="flex min-h-screen items-center justify-center bg-background px-4">
            <div className="w-full max-w-md space-y-8 rounded-2xl border bg-card p-8 shadow-lg">
                <div className="flex flex-col items-center text-center">
                    <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary">
                        <Building2 className="h-7 w-7 text-primary-foreground" />
                    </div>
                    <h1 className="text-2xl font-bold tracking-tight">Вход в RenovaCRM</h1>
                    <p className="mt-2 text-sm text-muted-foreground">
                        Введите свои данные для доступа в систему
                    </p>
                </div>

                {error && (
                    <div className="rounded-lg bg-destructive/10 p-3 text-center text-sm font-medium text-destructive">
                        {error}
                    </div>
                )}

                <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium leading-6 text-foreground">
                                Email адрес
                            </label>
                            <div className="relative mt-2">
                                <Mail className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                                <input
                                    type="email"
                                    required
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="block w-full rounded-lg border bg-background py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                                    placeholder="admin@example.com"
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium leading-6 text-foreground">
                                Пароль
                            </label>
                            <div className="relative mt-2">
                                <Lock className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                                <input
                                    type="password"
                                    required
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="block w-full rounded-lg border bg-background py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                                    placeholder="••••••••"
                                />
                            </div>
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary py-2.5 text-sm font-semibold text-primary-foreground transition-all hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
                    >
                        {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                        {loading ? 'Вход...' : 'Войти в систему'}
                    </button>

                    <div className="text-center text-xs text-muted-foreground">
                        <p>Используйте данные администратора по умолчанию:</p>
                        <p className="mt-1 font-mono">admin@test.com / admin123</p>
                    </div>
                </form>
            </div>
        </div>
    )
}
