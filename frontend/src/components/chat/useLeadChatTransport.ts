import { useEffect, useMemo, useRef, useState } from 'react'

import { MessageTransport, type Lead } from '@/types'

import { getDefaultTransport, getLeadAvailableTransports } from './chatUtils'

export function useLeadChatTransport(lead: Lead) {
    const [selectedTransport, setSelectedTransport] = useState<MessageTransport>(() => getDefaultTransport(lead))
    const manuallySelectedRef = useRef(false)
    const previousLeadIdRef = useRef(lead.id)

    const availableTransports = useMemo(() => getLeadAvailableTransports(lead), [
        lead.extracted_data,
        lead.id,
        lead.telegram_id,
    ])

    useEffect(() => {
        const leadChanged = previousLeadIdRef.current !== lead.id
        const nextDefault = getDefaultTransport(lead)

        if (leadChanged) {
            previousLeadIdRef.current = lead.id
            manuallySelectedRef.current = false
            setSelectedTransport(nextDefault)
            return
        }

        setSelectedTransport((current) => {
            if (!availableTransports.includes(current)) {
                manuallySelectedRef.current = false
                return nextDefault
            }
            if (!manuallySelectedRef.current && current !== nextDefault) {
                return nextDefault
            }
            return current
        })
    }, [availableTransports, lead.extracted_data, lead.id, lead.source, lead.telegram_id])

    const selectTransport = (transport: MessageTransport) => {
        manuallySelectedRef.current = true
        setSelectedTransport(transport)
    }

    return {
        selectedTransport,
        availableTransports,
        selectTransport,
    }
}
