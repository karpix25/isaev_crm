const API_URL = (import.meta as any).env.VITE_API_URL || 'http://localhost:8001'

export function getMediaUrl(url?: string | null): string | null {
    if (!url) return null
    if (/^https?:\/\//i.test(url)) return url
    return `${API_URL}${url.startsWith('/') ? url : `/${url}`}`
}

export function getMediaFileName(url: string): string {
    const cleanUrl = url.split('?')[0]
    const name = cleanUrl.split('/').filter(Boolean).pop()
    return name || 'Файл'
}

export function isImageMediaUrl(url: string): boolean {
    return /\.(avif|gif|jpe?g|png|webp)$/i.test(url.split('?')[0])
}
