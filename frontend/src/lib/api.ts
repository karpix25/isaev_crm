import axios from 'axios'
import type { Lead, ChatMessage, DashboardMetrics, LoginRequest, TokenResponse } from '@/types'

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || '/api',
    headers: {
        'Content-Type': 'application/json',
    },
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
    login: async (data: LoginRequest): Promise<TokenResponse> => {
        const response = await api.post<TokenResponse>('/auth/login', data)
        return response.data
    },
}

export const leadsAPI = {
    getAll: async (params?: { status?: string; source?: string; search?: string; page?: number; page_size?: number }) => {
        const response = await api.get<{ leads: Lead[]; total: number; page: number; page_size: number }>('/leads/', { params })
        return response.data
    },

    getById: async (id: string): Promise<Lead> => {
        const response = await api.get<Lead>(`/leads/${id}/`)
        return response.data
    },

    update: async (id: string, data: Partial<Lead>): Promise<Lead> => {
        const response = await api.patch<Lead>(`/leads/${id}/`, data)
        return response.data
    },

    delete: async (id: string): Promise<void> => {
        await api.delete(`/leads/${id}`)
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
