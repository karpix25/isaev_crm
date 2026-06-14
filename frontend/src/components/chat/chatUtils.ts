import { MessageDirection, MessageTransport, type ChatMessage, type Lead } from '@/types'

export type MessengerPresence = {
    telegram: boolean
    whatsapp: boolean
}

export function getLeadExtractedData(lead: Lead): Record<string, any> {
    try {
        return typeof lead.extracted_data === 'string'
            ? JSON.parse(lead.extracted_data || '{}')
            : (lead.extracted_data || {})
    } catch {
        return {}
    }
}

export function getMessengerPresence(lead: Lead): MessengerPresence {
    const parsed = getLeadExtractedData(lead)
    const messengers = parsed?.messengers || {}
    return {
        telegram: Boolean(messengers.telegram),
        whatsapp: Boolean(messengers.whatsapp),
    }
}

export function getLeadAvailableTransports(lead: Lead): MessageTransport[] {
    const transports: MessageTransport[] = []
    const presence = getMessengerPresence(lead)

    if (lead.telegram_id) {
        transports.push(MessageTransport.TELEGRAM)
    }
    if (presence.whatsapp) {
        transports.push(MessageTransport.WHATSAPP)
    }
    if (transports.length === 0) {
        transports.push(MessageTransport.TELEGRAM)
    }

    return transports
}

export function getDefaultTransport(lead: Lead): MessageTransport {
    const available = getLeadAvailableTransports(lead)
    const parsed = getLeadExtractedData(lead)
    const preferred = String(parsed?.quiz?.preferred_messenger || '').toLowerCase()

    if (preferred === MessageTransport.WHATSAPP && available.includes(MessageTransport.WHATSAPP)) {
        return MessageTransport.WHATSAPP
    }
    if (preferred === MessageTransport.TELEGRAM && available.includes(MessageTransport.TELEGRAM)) {
        return MessageTransport.TELEGRAM
    }
    if (lead.source === 'quiz_whatsapp' && available.includes(MessageTransport.WHATSAPP)) {
        return MessageTransport.WHATSAPP
    }
    if (available.includes(MessageTransport.TELEGRAM)) return MessageTransport.TELEGRAM
    return available[0]
}

export function getChatMessageLabel(message: ChatMessage): string {
    if (message.direction === MessageDirection.INBOUND) return 'Клиент'
    if (message.sender_name === 'AI' || message.sender_name === 'AI Agent' || message.sender_name === 'Bot') return 'ИИ Ассистент'
    return 'Вы'
}

export function getTransportLabel(transport: MessageTransport): string {
    return transport === MessageTransport.TELEGRAM ? 'Telegram' : 'WhatsApp'
}

export function getTransportShortLabel(transport?: MessageTransport): string {
    if (transport === MessageTransport.WHATSAPP) return 'WA'
    return 'TG'
}

function normalizePhoneDigits(phone?: string | null): string | null {
    const digitsOnly = String(phone || '').replace(/\D/g, '')
    if (!digitsOnly) return null
    if (digitsOnly.length === 11 && digitsOnly.startsWith('8')) return `7${digitsOnly.slice(1)}`
    if (digitsOnly.length === 10) return `7${digitsOnly}`
    return digitsOnly.length >= 10 ? digitsOnly : null
}

export function getTelegramChatUrl(lead: Lead): string | null {
    const username = String(lead.username || '').replace(/^@/, '').trim()
    if (username) return `https://t.me/${username}`

    const telegramId = String((lead as any).telegram_id || '').trim()
    if (telegramId) return `tg://user?id=${telegramId}`
    return null
}

export function getWhatsAppChatUrl(lead: Lead): string | null {
    const extracted = getLeadExtractedData(lead)
    const waId = String(extracted?.whatsapp_wa_id || '').replace(/\D/g, '')
    const phoneDigits = normalizePhoneDigits(lead.phone)
    const target = waId || phoneDigits
    if (!target) return null
    return `https://wa.me/${target}`
}
