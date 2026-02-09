import React from 'react'
import { Search, Bell, LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

interface HeaderProps {
    title: string
}

export function Header({ title }: HeaderProps) {
    const navigate = useNavigate()

    const handleLogout = () => {
        localStorage.removeItem('access_token')
        navigate('/login')
    }

    return (
        <header className="flex h-16 items-center justify-between border-b bg-card px-6">
            <h1 className="text-xl font-semibold">{title}</h1>

            <div className="flex items-center gap-4">
                {/* Search */}
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <input
                        type="text"
                        placeholder="Поиск по системе..."
                        className="h-10 w-64 rounded-lg border bg-background pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                </div>

                {/* Notifications */}
                <button className="relative rounded-lg p-2 hover:bg-accent">
                    <Bell className="h-5 w-5" />
                    <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-destructive" />
                </button>

                {/* User & Logout */}
                <div className="flex items-center gap-2">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-sm font-medium text-primary-foreground">
                        AD
                    </div>
                    <button
                        onClick={handleLogout}
                        className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-destructive"
                        title="Выйти"
                    >
                        <LogOut className="h-5 w-5" />
                    </button>
                </div>
            </div>
        </header>
    )
}
