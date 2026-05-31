import { Wrench } from 'lucide-react'

import type { ChatMessage } from '@/types'

type MessageToolCallBadgeProps = {
    message: ChatMessage
    leadSource?: string | null
}

const toolLabels: Record<string, string> = {
    read_lead_summary: 'прочитал данные лида',
    read_measurement_booking: 'проверил бронь замера',
    read_measurement_booking_empty: 'проверил бронь замера',
    update_measurement_address: 'обновил адрес замера',
    measurement_address_update_request: 'запросил новый адрес замера',
    measurement_address_updated: 'обновил адрес замера',
    measurement_address_directly_updated: 'обновил адрес замера',
    change_measurement_booking: 'открыл изменение замера',
    reschedule_measurement: 'открыл перенос замера',
    cancel_measurement: 'отменил замер',
    show_measurement_slots: 'показал слоты замера',
    read_estimate_status: 'проверил статус сметы',
    send_final_estimate: 'отправил готовую смету',
    final_estimate_resent: 'повторно отправил смету',
    estimate_resend_missing_file: 'проверил файл сметы',
    estimate_resend_file_not_found: 'проверил файл сметы',
    estimate_resend_bot_unavailable: 'проверил отправку сметы',
    handoff_to_manager: 'передал менеджеру',
    measurement_existing_booking_guard: 'проверил текущую запись',
}

export function MessageToolCallBadge({ message, leadSource }: MessageToolCallBadgeProps) {
    const toolName = getToolName(message)
    if (!toolName) return null

    const label = toolLabels[toolName] || toolName
    const actor = isTelegramBusinessMessage(message, leadSource) ? 'business bot' : 'bot'

    return (
        <div className="flex items-center gap-1.5 rounded-xl border border-violet-200 bg-violet-50 px-2.5 py-1.5 text-[11px] font-medium text-violet-700 shadow-sm animate-in fade-in slide-in-from-bottom-2">
            <Wrench className="h-3.5 w-3.5" />
            {actor}: tool `{toolName}` - {label}
        </div>
    )
}

function getToolName(message: ChatMessage): string {
    const metadata = message.ai_metadata || {}
    const explicitTool = metadata.tool_call?.action || metadata.crm_tool_action
    if (typeof explicitTool === 'string' && explicitTool.trim()) {
        return explicitTool.trim()
    }

    const source = String(metadata.source || '')
    const type = typeof metadata.type === 'string' ? metadata.type.trim() : ''
    if (!type) return ''

    if (source === 'crm_safe_tool' || source === 'crm_tool' || source === 'ai_tool') {
        return type
    }

    if (type.startsWith('measurement_') && source.includes('measurement')) {
        return type
    }

    return ''
}

function isTelegramBusinessMessage(message: ChatMessage, leadSource?: string | null): boolean {
    const metadata = message.ai_metadata || {}
    return Boolean(
        metadata.business_connection_id ||
        metadata.tool_call?.channel === 'telegram_business' ||
        metadata.source === 'telegram_business' ||
        leadSource === 'telegram_business'
    )
}
