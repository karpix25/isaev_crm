import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/react-query'
import { leadsAPI } from '@/lib/api'
import type { Lead, LeadStatus } from '@/types'

type LeadsQueryParams = { status?: LeadStatus; source?: string; search?: string; page?: number; page_size?: number }

function invalidateLeadQueries(queryClient: ReturnType<typeof useQueryClient>) {
    queryClient.invalidateQueries({ queryKey: ['leads'] })
    queryClient.invalidateQueries({ queryKey: ['leads-infinite'] })
}

export function useLeads(params?: LeadsQueryParams) {
    return useQuery({
        queryKey: ['leads', params],
        queryFn: () => leadsAPI.getAll(params),
        refetchInterval: 10000, // Poll every 10 seconds for new leads/unread counts
    })
}

export function useLeadsInfinite(params?: Omit<LeadsQueryParams, 'page'>) {
    return useInfiniteQuery({
        queryKey: ['leads-infinite', params],
        queryFn: ({ pageParam }) =>
            leadsAPI.getAll({
                ...params,
                page: Number(pageParam),
                page_size: params?.page_size,
            }),
        refetchInterval: 5000, // Keep kanban in near real-time without manual refresh
        initialPageParam: 1,
        getNextPageParam: (lastPage) => {
            const loaded = lastPage.page * lastPage.page_size
            if (loaded >= lastPage.total) return undefined
            return lastPage.page + 1
        },
    })
}

export function useLead(id: string) {
    return useQuery({
        queryKey: ['lead', id],
        queryFn: () => leadsAPI.getById(id),
        enabled: !!id,
    })
}

export function useLeadHistory(id: string, limit = 100) {
    return useQuery({
        queryKey: ['lead-history', id, limit],
        queryFn: () => leadsAPI.getHistory(id, limit),
        enabled: !!id,
    })
}

export function useCreateLead() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: { full_name?: string; phone?: string; username?: string; source?: string; org_id: string }) => leadsAPI.create(data),
        onSuccess: () => {
            invalidateLeadQueries(queryClient)
        },
    })
}

export function useUpdateLead() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: Partial<Lead> }) =>
            leadsAPI.update(id, data),
        onSuccess: (_data, variables) => {
            invalidateLeadQueries(queryClient)
            queryClient.invalidateQueries({ queryKey: ['lead-history', variables.id] })
        },
    })
}

export function useDeleteLead() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (id: string) => leadsAPI.delete(id),
        onSuccess: (_data, deletedLeadId) => {
            invalidateLeadQueries(queryClient)
            queryClient.removeQueries({ queryKey: ['chat', deletedLeadId] })
        },
    })
}

export function useBulkDeleteLeads() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (leadIds: string[]) => leadsAPI.bulkDelete(leadIds),
        onSuccess: () => {
            invalidateLeadQueries(queryClient)
        },
    })
}

export function useImportLeads() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ file, source }: { file: File; source?: string }) =>
            leadsAPI.importBulk(file, source),
        onSuccess: () => {
            invalidateLeadQueries(queryClient)
        },
    })
}
