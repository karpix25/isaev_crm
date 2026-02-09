import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { chatAPI } from '@/lib/api'

export function useChatHistory(leadId: string, page = 1) {
    return useQuery({
        queryKey: ['chat', leadId, page],
        queryFn: () => chatAPI.getHistory(leadId, page),
        enabled: !!leadId,
        refetchInterval: 3000, // Poll every 3 seconds for real-time updates
    })
}

export function useSendMessage() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ leadId, content }: { leadId: string; content: string }) =>
            chatAPI.sendMessage(leadId, content),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ['chat', variables.leadId] })
            queryClient.invalidateQueries({ queryKey: ['leads'] })
        },
    })
}

export function useUnreadCount() {
    return useQuery({
        queryKey: ['unread-count'],
        queryFn: () => chatAPI.getUnreadCount(),
        refetchInterval: 30000, // Refetch every 30 seconds
    })
}
