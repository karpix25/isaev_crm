import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/react-query'
import { leadsAPI } from '@/lib/api'
import type { Lead, LeadStatus } from '@/types'

type LeadsQueryParams = { status?: LeadStatus; source?: string; search?: string; page?: number; page_size?: number }

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

export function useBulkDeleteLeads() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (leadIds: string[]) => leadsAPI.bulkDelete(leadIds),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['leads'] })
            queryClient.invalidateQueries({ queryKey: ['leads-infinite'] })
        },
    })
}

export function useImportLeads() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ file, source }: { file: File; source?: string }) =>
            leadsAPI.importBulk(file, source),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['leads'] })
        },
    })
}
