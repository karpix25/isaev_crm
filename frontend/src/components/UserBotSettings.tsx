import React, { useState, useEffect } from 'react'
import { Send, CheckCircle2, XCircle, AlertCircle, Phone, Key, ShieldCheck, Power, LogOut } from 'lucide-react'
import { toast } from 'sonner'

interface UserBotStatus {
    org_id: string
    phone: string
    is_authorized: boolean
    is_active: boolean
    status: 'not_configured' | 'connected' | 'disconnected' | 'error'
    last_error?: string
}

export default function UserBotSettings() {
    const [status, setStatus] = useState<UserBotStatus | null>(null)
    const [loading, setLoading] = useState(true)
    const [authStep, setAuthStep] = useState<'none' | 'phone' | 'code' | 'password'>('none')

    // Form states
    const [phone, setPhone] = useState('')
    const [apiId, setApiId] = useState('')
    const [apiHash, setApiHash] = useState('')
    const [code, setCode] = useState('')
    const [password, setPassword] = useState('')
    const [submitting, setSubmitting] = useState(false)

    const [codeType, setCodeType] = useState<string>('')

    useEffect(() => {
        fetchStatus()
    }, [])

    const fetchStatus = async () => {
        try {
            const token = localStorage.getItem('access_token')
            const response = await fetch('/api/userbot/status', {
                headers: { 'Authorization': `Bearer ${token}` }
            })
            if (response.ok) {
                const data = await response.json()
                setStatus(data)
                if (!data.is_authorized && authStep === 'none') {
                    setAuthStep('phone')
                }
            }
        } catch (error) {
            console.error('Failed to fetch user bot status:', error)
        } finally {
            setLoading(false)
        }
    }

    const handleStartAuth = async (e: React.FormEvent) => {
        e.preventDefault()
        setSubmitting(true)
        try {
            const token = localStorage.getItem('access_token')
            const response = await fetch('/api/userbot/auth/start', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ phone, api_id: parseInt(apiId), api_hash: apiHash })
            })

            if (response.ok) {
                const data = await response.json()
                const ct = data.code_type || 'app'
                setCodeType(ct)

                const typeMessages: Record<string, string> = {
                    'app': 'Код отправлен в приложение Telegram (раздел «Избранное» или сообщение от Telegram)',
                    'sms': 'Код отправлен по SMS на указанный номер',
                    'call': 'Вам поступит звонок с кодом',
                    'flash_call': 'Вам поступит звонок — код в последних цифрах номера',
                    'missed_call': 'Вам поступит пропущенный вызов — код в последних цифрах номера',
                    'fragment_sms': 'Код отправлен через Fragment SMS',
                }
                toast.success(typeMessages[ct] || `Код отправлен (тип: ${ct})`)
                setAuthStep('code')
            } else {
                const err = await response.json()
                toast.error(err.detail || 'Ошибка при отправке кода')
            }
        } catch (error) {
            toast.error('Сетевая ошибка')
        } finally {
            setSubmitting(false)
        }
    }

    const handleVerifyCode = async (e: React.FormEvent) => {
        e.preventDefault()
        setSubmitting(true)
        try {
            const token = localStorage.getItem('access_token')
            const response = await fetch('/api/userbot/auth/verify', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ code })
            })

            const data = await response.json()
            if (response.ok) {
                if (data.status === 'password_required') {
                    setAuthStep('password')
                } else {
                    toast.success('Аккаунт успешно подключен!')
                    setAuthStep('none')
                    fetchStatus()
                }
            } else {
                toast.error(data.detail || 'Неверный код')
            }
        } catch (error) {
            toast.error('Ошибка верификации')
        } finally {
            setSubmitting(false)
        }
    }

    const handleSubmitPassword = async (e: React.FormEvent) => {
        e.preventDefault()
        setSubmitting(true)
        try {
            const token = localStorage.getItem('access_token')
            const response = await fetch('/api/userbot/auth/password', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ password })
            })

            if (response.ok) {
                toast.success('Авторизация завершена!')
                setAuthStep('none')
                fetchStatus()
            } else {
                const err = await response.json()
                toast.error(err.detail || 'Неверный пароль')
            }
        } catch (error) {
            toast.error('Ошибка авторизации')
        } finally {
            setSubmitting(false)
        }
    }

    const toggleActive = async () => {
        if (!status) return
        try {
            const token = localStorage.getItem('access_token')
            const response = await fetch('/api/userbot/settings', {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ is_active: !status.is_active })
            })

            if (response.ok) {
                const updated = await response.json()
                setStatus(updated)
                toast.success(updated.is_active ? 'Агент включен' : 'Агент выключен')
            }
        } catch (error) {
            toast.error('Ошибка при обновлении настроек')
        }
    }

    const handleLogout = async () => {
        if (!confirm('Вы уверены, что хотите отключить аккаунт?')) return
        try {
            const token = localStorage.getItem('access_token')
            // Reset bot settings in DB
            const response = await fetch('/api/userbot/settings', {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ is_active: false })
            })

            if (response.ok) {
                toast.success('Аккаунт отключен')
                setStatus(null)
                setAuthStep('phone')
            }
        } catch (error) {
            toast.error('Ошибка при выходе')
        }
    }

    if (loading) return <div className="text-center py-8">Загрузка...</div>

    return (
        <div className="space-y-6 max-w-2xl mx-auto p-4">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Telegram User Bot</h2>
                    <p className="text-muted-foreground">Подключите свой аккаунт, чтобы AI агент мог отвечать клиентам от вашего имени.</p>
                </div>
                {status?.is_authorized && (
                    <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${status.status === 'connected' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                        }`}>
                        {status.status === 'connected' ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                        {status.status === 'connected' ? 'Подключен' : 'Ошибка'}
                    </div>
                )}
            </div>

            {status?.is_authorized ? (
                <div className="bg-card border rounded-xl p-6 shadow-sm space-y-6">
                    <div className="flex items-center justify-between border-b pb-4">
                        <div className="flex items-center gap-4">
                            <div className="h-12 w-12 bg-primary/10 rounded-full flex items-center justify-center text-primary">
                                <Phone className="h-6 w-6" />
                            </div>
                            <div>
                                <p className="font-semibold text-lg">{status.phone}</p>
                                <p className="text-sm text-muted-foreground">Основной аккаунт агента</p>
                            </div>
                        </div>
                        <button
                            onClick={toggleActive}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors font-medium ${status.is_active
                                ? 'bg-red-50 text-red-600 hover:bg-red-100'
                                : 'bg-green-600 text-white hover:bg-green-700'
                                }`}
                        >
                            <Power className="h-4 w-4" />
                            {status.is_active ? 'Выключить агента' : 'Включить агента'}
                        </button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="p-4 bg-muted/30 rounded-lg">
                            <p className="text-sm font-medium mb-1">Статус AI</p>
                            <div className="flex items-center gap-2">
                                <div className={`h-2 w-2 rounded-full ${status.is_active ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
                                <span className="text-sm">{status.is_active ? 'Активен и слушает чаты' : 'В режиме ожидания'}</span>
                            </div>
                        </div>
                        <div className="p-4 bg-muted/30 rounded-lg">
                            <p className="text-sm font-medium mb-1">Последняя активность</p>
                            <span className="text-sm text-muted-foreground">Только что</span>
                        </div>
                    </div>

                    {status.last_error && (
                        <div className="p-4 bg-red-50 border border-red-100 rounded-lg text-red-700 text-sm flex gap-2">
                            <AlertCircle className="h-4 w-4 shrink-0" />
                            <p>{status.last_error}</p>
                        </div>
                    )}

                    <div className="pt-4 flex justify-end">
                        <button
                            onClick={handleLogout}
                            className="text-muted-foreground hover:text-red-500 text-sm flex items-center gap-1 transition-colors"
                        >
                            <LogOut className="h-4 w-4" />
                            Отключить аккаунт
                        </button>
                    </div>
                </div>
            ) : (
                <div className="bg-card border rounded-xl p-6 shadow-sm">
                    {authStep === 'phone' && (
                        <form onSubmit={handleStartAuth} className="space-y-4">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="h-10 w-10 bg-primary/10 rounded-full flex items-center justify-center text-primary">
                                    <Phone className="h-5 w-5" />
                                </div>
                                <h3 className="text-lg font-semibold">Настройка подключения</h3>
                            </div>

                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium mb-1">Номер телефона</label>
                                    <input
                                        type="tel"
                                        placeholder="+7..."
                                        value={phone}
                                        onChange={(e) => setPhone(e.target.value)}
                                        className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary/20 outline-none"
                                        required
                                    />
                                    <p className="text-xs text-muted-foreground mt-1">В формате +79991234567</p>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-sm font-medium mb-1">API ID</label>
                                        <input
                                            type="text"
                                            placeholder="123456"
                                            value={apiId}
                                            onChange={(e) => setApiId(e.target.value)}
                                            className="w-full px-4 py-2 border rounded-lg outline-none"
                                            required
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium mb-1">API Hash</label>
                                        <input
                                            type="text"
                                            placeholder="hash..."
                                            value={apiHash}
                                            onChange={(e) => setApiHash(e.target.value)}
                                            className="w-full px-4 py-2 border rounded-lg outline-none"
                                            required
                                        />
                                    </div>
                                </div>
                                <p className="text-xs text-muted-foreground bg-muted/50 p-3 rounded-lg border border-dashed">
                                    Получить API ID и API Hash можно на <a href="https://my.telegram.org" target="_blank" className="text-primary hover:underline">my.telegram.org</a> в разделе API Development tools.
                                </p>
                            </div>

                            <button
                                type="submit"
                                disabled={submitting}
                                className="w-full bg-primary text-white py-2 rounded-lg hover:bg-primary/90 transition-colors flex items-center justify-center gap-2 font-medium mt-4"
                            >
                                {submitting ? 'Отправка...' : 'Получить код'}
                                <Send className="h-4 w-4" />
                            </button>
                        </form>
                    )}

                    {authStep === 'code' && (
                        <form onSubmit={handleVerifyCode} className="space-y-4">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="h-10 w-10 bg-primary/10 rounded-full flex items-center justify-center text-primary">
                                    <Key className="h-5 w-5" />
                                </div>
                                <h3 className="text-lg font-semibold">Введите код подтверждения</h3>
                            </div>

                            <div>
                                <label className="block text-sm font-medium mb-1">Код из Telegram</label>
                                <input
                                    type="text"
                                    placeholder="12345"
                                    value={code}
                                    onChange={(e) => setCode(e.target.value)}
                                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary/20 outline-none text-center text-2xl tracking-widest"
                                    required
                                    autoFocus
                                />
                                <p className="text-xs text-muted-foreground mt-2 bg-blue-50 p-2 rounded border border-blue-100">
                                    💡 {codeType === 'sms'
                                        ? 'Код отправлен по SMS на указанный номер'
                                        : codeType === 'call'
                                            ? 'Вам поступит звонок с кодом'
                                            : 'Откройте Telegram на телефоне — код придёт как сообщение от «Telegram» (не SMS!)'}
                                </p>
                            </div>

                            <button
                                type="submit"
                                disabled={submitting}
                                className="w-full bg-primary text-white py-2 rounded-lg hover:bg-primary/90 transition-colors font-medium"
                            >
                                {submitting ? 'Проверка...' : 'Подтвердить'}
                            </button>

                            <button
                                type="button"
                                onClick={() => setAuthStep('phone')}
                                className="w-full text-muted-foreground text-sm hover:underline"
                            >
                                Назад к вводу номера
                            </button>
                        </form>
                    )}

                    {authStep === 'password' && (
                        <form onSubmit={handleSubmitPassword} className="space-y-4">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="h-10 w-10 bg-primary/10 rounded-full flex items-center justify-center text-primary">
                                    <ShieldCheck className="h-5 w-5" />
                                </div>
                                <h3 className="text-lg font-semibold">2FA Пароль</h3>
                            </div>

                            <p className="text-sm text-muted-foreground">На вашем аккаунте включена двухфакторная аутентификация. Введите облачный пароль.</p>

                            <div>
                                <label className="block text-sm font-medium mb-1">Пароль</label>
                                <input
                                    type="password"
                                    placeholder="Введите пароль"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary/20 outline-none"
                                    required
                                    autoFocus
                                />
                            </div>

                            <button
                                type="submit"
                                disabled={submitting}
                                className="w-full bg-primary text-white py-2 rounded-lg hover:bg-primary/90 transition-colors font-medium"
                            >
                                {submitting ? 'Загрузка...' : 'Авторизоваться'}
                            </button>
                        </form>
                    )}
                </div>
            )}
        </div>
    )
}
