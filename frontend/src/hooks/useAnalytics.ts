import { useQuery } from '@tanstack/react-query'
import { analyticsAPI } from '@/lib/api'
import type { AnalyticsSummaryParams } from '@/types'

export function useAnalyticsSummary(params?: AnalyticsSummaryParams) {
    return useQuery({
        queryKey: ['analytics-summary', params],
        queryFn: () => analyticsAPI.getSummary(params),
        refetchInterval: 30000,
    })
}
