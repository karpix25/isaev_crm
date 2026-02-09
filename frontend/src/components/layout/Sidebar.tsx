import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
    LayoutDashboard,
    Users,
    MessageSquare,
    Building2,
    DollarSign,
    FileText,
    Calendar,
    UserCircle,
    Bot,
    Settings,
    HardHat
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navigation = [
    { name: 'Дашборд', href: '/', icon: LayoutDashboard },
    { name: 'Воронка продаж', href: '/leads', icon: Users },
    { name: 'Объекты', href: '/projects', icon: HardHat },
    { name: 'Чат', href: '/chat', icon: MessageSquare },
    { name: 'Финансы', href: '/finance', icon: DollarSign, disabled: true },
    { name: 'Отчеты (Telegram)', href: '/reports', icon: FileText, disabled: true },
    { name: 'Замеры', href: '/measurements', icon: Calendar, disabled: true },
    { name: 'Кабинет Клиента', href: '/client-portal', icon: UserCircle, disabled: true },
    { name: 'Бот Прораба', href: '/worker-bot', icon: Bot, disabled: true },
]

export function Sidebar() {
    const location = useLocation()

    return (
        <div className="flex h-screen w-64 flex-col border-r bg-card">
            {/* Logo */}
            <div className="flex h-16 items-center gap-2 border-b px-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary">
                    <Building2 className="h-6 w-6 text-primary-foreground" />
                </div>
                <div>
                    <div className="font-semibold">RenovaCRM</div>
                    <div className="text-xs text-muted-foreground">ERP SOLUTION</div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 space-y-1 p-4">
                {navigation.map((item) => {
                    const isActive = location.pathname === item.href
                    const Icon = item.icon

                    return (
                        <Link
                            key={item.name}
                            to={item.disabled ? '#' : item.href}
                            className={cn(
                                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                                isActive
                                    ? 'bg-primary text-primary-foreground'
                                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                                item.disabled && 'cursor-not-allowed opacity-50'
                            )}
                            onClick={(e) => item.disabled && e.preventDefault()}
                        >
                            <Icon className="h-5 w-5" />
                            {item.name}
                        </Link>
                    )
                })}
            </nav>

            {/* Settings */}
            <div className="border-t p-4">
                <Link
                    to="/settings"
                    className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                    <Settings className="h-5 w-5" />
                    Настройки AI
                </Link>
            </div>
        </div>
    )
}
