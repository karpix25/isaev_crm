import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import type {
    PromptConfigResponse, PromptConfigCreate,
    KnowledgeItemResponse, KnowledgeItemCreate,
    KnowledgeSearchRequest,
    TelegramBusinessCardTemplateSettings,
    CompanyFact,
    CompanyFactPayload,
} from '@/types'

export function useAI() {
    const queryClient = useQueryClient()

    const prompts = useQuery({
        queryKey: ['ai', 'prompts'],
        queryFn: async () => {
            const { data } = await api.get<PromptConfigResponse[]>('/ai/prompts')
            return data
        }
    })

    const activePrompt = useQuery({
        queryKey: ['ai', 'prompts', 'active'],
        queryFn: async () => {
            const { data } = await api.get<PromptConfigResponse>('/ai/prompts/active')
            return data
        }
    })

    const createPrompt = useMutation({
        mutationFn: async (newData: PromptConfigCreate) => {
            const { data } = await api.post<PromptConfigResponse>('/ai/prompts', newData)
            return data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['ai', 'prompts'] })
        }
    })

    const knowledge = useQuery({
        queryKey: ['ai', 'knowledge'],
        queryFn: async () => {
            const { data } = await api.get<KnowledgeItemResponse[]>('/ai/knowledge')
            return data
        }
    })

    const addKnowledge = useMutation({
        mutationFn: async (newData: KnowledgeItemCreate) => {
            const { data } = await api.post<KnowledgeItemResponse>('/ai/knowledge', newData)
            return data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['ai', 'knowledge'] })
        }
    })

    const deleteKnowledge = useMutation({
        mutationFn: async (itemId: string) => {
            await api.delete(`/ai/knowledge/${itemId}`)
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['ai', 'knowledge'] })
        }
    })

    const uploadFile = useMutation({
        mutationFn: async ({ file, category }: { file: File, category: string }) => {
            const formData = new FormData()
            formData.append('file', file)
            formData.append('category', category)
            const { data } = await api.post('/ai/knowledge/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            })
            return data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['ai', 'knowledge'] })
        }
    })

    const searchKnowledge = useMutation({
        mutationFn: async (searchData: KnowledgeSearchRequest) => {
            const { data } = await api.post<KnowledgeItemResponse[]>('/ai/knowledge/search', searchData)
            return data
        }
    })

    const clearKnowledge = useMutation({
        mutationFn: async () => {
            const { data } = await api.delete('/ai/knowledge')
            return data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['ai', 'knowledge'] })
            queryClient.setQueryData(['ai', 'knowledge', 'search'], null)
        }
    })

    const telegramBusinessCardTemplate = useQuery({
        queryKey: ['ai', 'telegram-business-card-template'],
        queryFn: async () => {
            const { data } = await api.get<TelegramBusinessCardTemplateSettings>('/ai/telegram-business-card-template')
            return data
        },
    })

    const companyFacts = useQuery({
        queryKey: ['ai', 'company-facts'],
        queryFn: async () => {
            const { data } = await api.get<CompanyFact[]>('/ai/company-facts')
            return data
        },
    })

    const createCompanyFact = useMutation({
        mutationFn: async (payload: CompanyFactPayload) => {
            const { data } = await api.post<CompanyFact>('/ai/company-facts', payload)
            return data
        },
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ai', 'company-facts'] }),
    })

    const updateCompanyFact = useMutation({
        mutationFn: async ({ id, payload }: { id: string; payload: Partial<CompanyFactPayload> }) => {
            const { data } = await api.put<CompanyFact>(`/ai/company-facts/${id}`, payload)
            return data
        },
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ai', 'company-facts'] }),
    })

    const deleteCompanyFact = useMutation({
        mutationFn: async (id: string) => {
            await api.delete(`/ai/company-facts/${id}`)
        },
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ai', 'company-facts'] }),
    })

    const updateTelegramBusinessCardTemplate = useMutation({
        mutationFn: async (payload: { template: string }) => {
            const { data } = await api.put<TelegramBusinessCardTemplateSettings>('/ai/telegram-business-card-template', payload)
            return data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['ai', 'telegram-business-card-template'] })
        },
    })

    return {
        prompts,
        activePrompt,
        createPrompt,
        addKnowledge,
        searchKnowledge,
        clearKnowledge,
        uploadFile,
        deleteKnowledge,
        knowledge,
        telegramBusinessCardTemplate,
        updateTelegramBusinessCardTemplate,
        companyFacts,
        createCompanyFact,
        updateCompanyFact,
        deleteCompanyFact,
    }
}
