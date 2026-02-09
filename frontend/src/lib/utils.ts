import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
}

export function formatTimeAgo(date: Date | string): string {
    const now = new Date()
    const then = typeof date === 'string' ? new Date(date) : date
    const seconds = Math.floor((now.getTime() - then.getTime()) / 1000)

    if (seconds < 60) return 'только что'
    if (seconds < 3600) return `${Math.floor(seconds / 60)} мин. назад`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} ч. назад`
    if (seconds < 604800) return `${Math.floor(seconds / 86400)} дн. назад`

    return then.toLocaleDateString('ru-RU')
}
