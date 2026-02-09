import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import type { CustomField } from '@/types'

export function useCustomFields(activeOnly: boolean = false) {
    return useQuery({
        queryKey: ['custom-fields', activeOnly],
        queryFn: async () => {
            const { data } = await api.get<CustomField[]>(`/custom-fields?active_only=${activeOnly}`)
            return data
        }
    })
}
