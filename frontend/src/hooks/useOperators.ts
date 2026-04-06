import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { authAPI } from '@/lib/api'
import type {
    OperatorCreatePayload,
    OperatorUpdatePayload,
    OperatorAccessApprovePayload,
    OperatorAccessRejectPayload,
} from '@/types'

export function useOperators() {
    return useQuery({
        queryKey: ['operators'],
        queryFn: () => authAPI.getOperators(),
    })
}

export function useCreateOperator() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (payload: OperatorCreatePayload) => authAPI.createOperator(payload),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['operators'] })
        },
    })
}

export function useUpdateOperator() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ id, payload }: { id: string; payload: OperatorUpdatePayload }) => authAPI.updateOperator(id, payload),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['operators'] })
        },
    })
}

export function useDeleteOperator() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (id: string) => authAPI.deleteOperator(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['operators'] })
        },
    })
}

export function useOperatorAccessRequests(statusFilter: 'pending' | 'approved' | 'rejected' | 'all' = 'pending') {
    return useQuery({
        queryKey: ['operator-access-requests', statusFilter],
        queryFn: () => authAPI.getOperatorAccessRequests(statusFilter),
        refetchInterval: 5000,
    })
}

export function useApproveOperatorAccessRequest() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ id, payload }: { id: string; payload?: OperatorAccessApprovePayload }) =>
            authAPI.approveOperatorAccessRequest(id, payload),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['operators'] })
            queryClient.invalidateQueries({ queryKey: ['operator-access-requests'] })
        },
    })
}

export function useRejectOperatorAccessRequest() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ id, payload }: { id: string; payload?: OperatorAccessRejectPayload }) =>
            authAPI.rejectOperatorAccessRequest(id, payload),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['operator-access-requests'] })
        },
    })
}
