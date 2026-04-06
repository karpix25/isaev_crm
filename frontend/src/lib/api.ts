import axios from 'axios'
import axiosRetry from 'axios-retry'
import type {
    Lead,
    ChatMessage,
    DashboardMetrics,
    TokenResponse,
    LeadImportResult,
    LeadBulkDeleteResult,
    LeadChangeLogResponse,
    OperatorUser,
    OperatorCreatePayload,
    OperatorUpdatePayload,
    OperatorAccessRequest,
    OperatorAccessApprovePayload,
    OperatorAccessRejectPayload,
} from '@/types'

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || '/api',
    headers: {
        'Content-Type': 'application/json',
    },
})

// Configure robust automatic retries for network and 5xx errors
axiosRetry(api, {
    retries: 3,
    retryDelay: axiosRetry.exponentialDelay,
    retryCondition: (error) => {
        // Retry on network errors or 5xx server errors
        return axiosRetry.isNetworkOrIdempotentRequestError(error) ||
            (error.response?.status !== undefined && error.response.status >= 500);
    }
})

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// Response interceptor for error handling
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('access_token')
            window.location.href = '/login'
        }
        return Promise.reject(error)
    }
)

export const authAPI = {
    telegramLogin: async (data: Record<string, any>): Promise<TokenResponse> => {
        const response = await api.post<TokenResponse>('/auth/telegram', data)
        return response.data
    },
    telegramBotInfo: async (): Promise<{ bot_id: number; username?: string | null }> => {
        const response = await api.get<{ bot_id: number; username?: string | null }>('/auth/telegram/bot')
        return response.data
    },
    telegramBotLoginInit: async (): Promise<{ session_id: string; bot_username: string; expires_in: number }> => {
        const response = await api.post<{ session_id: string; bot_username: string; expires_in: number }>('/auth/telegram/bot/init')
        return response.data
    },
    telegramBotLoginCheck: async (
        sessionId: string
    ): Promise<{
        status: 'pending' | 'pending_approval' | 'rejected' | 'authorized' | 'expired'
        access_token?: string
        refresh_token?: string
        detail?: string | null
    }> => {
        const response = await api.get<{
            status: 'pending' | 'pending_approval' | 'rejected' | 'authorized' | 'expired'
            access_token?: string
            refresh_token?: string
            detail?: string | null
        }>(
            `/auth/telegram/bot/check/${sessionId}`
        )
        return response.data
    },
    getOperators: async (): Promise<OperatorUser[]> => {
        const response = await api.get<OperatorUser[]>('/auth/operators')
        return response.data
    },
    createOperator: async (payload: OperatorCreatePayload): Promise<OperatorUser> => {
        const response = await api.post<OperatorUser>('/auth/operators', payload)
        return response.data
    },
    updateOperator: async (id: string, payload: OperatorUpdatePayload): Promise<OperatorUser> => {
        const response = await api.patch<OperatorUser>(`/auth/operators/${id}`, payload)
        return response.data
    },
    deleteOperator: async (id: string): Promise<void> => {
        await api.delete(`/auth/operators/${id}`)
    },
    getOperatorAccessRequests: async (statusFilter: 'pending' | 'approved' | 'rejected' | 'all' = 'pending'): Promise<OperatorAccessRequest[]> => {
        const response = await api.get<OperatorAccessRequest[]>('/auth/operator-access-requests', {
            params: { status_filter: statusFilter },
        })
        return response.data
    },
    approveOperatorAccessRequest: async (id: string, payload?: OperatorAccessApprovePayload): Promise<OperatorUser> => {
        const response = await api.post<OperatorUser>(`/auth/operator-access-requests/${id}/approve`, payload || {})
        return response.data
    },
    rejectOperatorAccessRequest: async (id: string, payload?: OperatorAccessRejectPayload): Promise<OperatorAccessRequest> => {
        const response = await api.post<OperatorAccessRequest>(`/auth/operator-access-requests/${id}/reject`, payload || {})
        return response.data
    },
}

export const leadsAPI = {
    getAll: async (params?: { status?: string; source?: string; search?: string; page?: number; page_size?: number }) => {
        const response = await api.get<{ leads: Lead[]; total: number; page: number; page_size: number }>('/leads/', { params })
        return response.data
    },

    create: async (data: { full_name?: string; phone?: string; username?: string; source?: string; org_id: string }): Promise<Lead> => {
        const response = await api.post<Lead>('/leads/', data)
        return response.data
    },

    getById: async (id: string): Promise<Lead> => {
        const response = await api.get<Lead>(`/leads/${id}`)
        return response.data
    },

    update: async (id: string, data: Partial<Lead>): Promise<Lead> => {
        const response = await api.patch<Lead>(`/leads/${id}`, data)
        return response.data
    },

    delete: async (id: string): Promise<void> => {
        await api.delete(`/leads/${id}`)
    },

    bulkDelete: async (leadIds: string[]): Promise<LeadBulkDeleteResult> => {
        const response = await api.post<LeadBulkDeleteResult>('/leads/bulk-delete', { lead_ids: leadIds })
        return response.data
    },

    importBulk: async (file: File, source = 'IMPORT'): Promise<LeadImportResult> => {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('source', source)

        const response = await api.post<LeadImportResult>('/leads/import', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        })
        return response.data
    },

    getHistory: async (id: string, limit = 100): Promise<LeadChangeLogResponse> => {
        const response = await api.get<LeadChangeLogResponse>(`/leads/${id}/history`, { params: { limit } })
        return response.data
    },

}

export const chatAPI = {
    getHistory: async (leadId: string, page = 1, pageSize = 50) => {
        const response = await api.get<{ messages: ChatMessage[]; total: number; page: number; page_size: number }>(
            `/chat/${leadId}/history`,
            { params: { page, page_size: pageSize } }
        )
        return response.data
    },

    sendMessage: async (leadId: string, content: string): Promise<ChatMessage> => {
        const response = await api.post<ChatMessage>(`/chat/${leadId}/send`, { content })
        return response.data
    },

    sendBusinessCard: async (leadId: string): Promise<ChatMessage> => {
        const response = await api.post<ChatMessage>(`/chat/${leadId}/send-business-card`)
        return response.data
    },

    getUnreadCount: async (): Promise<number> => {
        const response = await api.get<{ unread_count: number }>('/chat/unread')
        return response.data.unread_count
    },
}

export const dashboardAPI = {
    getMetrics: async (): Promise<DashboardMetrics> => {
        const response = await api.get<DashboardMetrics>('/dashboard/metrics')
        return response.data
    },
}

export default api
