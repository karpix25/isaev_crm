import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { leadsAPI } from '@/lib/api'
import type { Lead, LeadStatus } from '@/types'

export function useLeads(params?: { status?: LeadStatus; source?: string; search?: string }) {
    return useQuery({
        queryKey: ['leads', params],
        queryFn: () => leadsAPI.getAll(params),
        refetchInterval: 10000, // Poll every 10 seconds for new leads/unread counts
    })
}

export function useLead(id: string) {
    return useQuery({
        queryKey: ['lead', id],
        queryFn: () => leadsAPI.getById(id),
        enabled: !!id,
    })
}

export function useCreateLead() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: { full_name?: string; phone?: string; username?: string; source?: string; org_id: string }) => leadsAPI.create(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['leads'] })
        },
    })
}

export function useUpdateLead() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: Partial<Lead> }) =>
            leadsAPI.update(id, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['leads'] })
        },
    })
}

export function useDeleteLead() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (id: string) => leadsAPI.delete(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['leads'] })
        },
    })
}
